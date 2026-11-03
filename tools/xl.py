#!/usr/bin/env python
"""Drive the running xLights through its automation API (xlDo), so a file changed on disk
is force-closed, reopened and rendered without anyone touching the GUI -- and without the
stale in-memory copy ever being saved over it.

One-time setup in xLights:  Preferences -> Output -> "API Port" -> "Port A (49913)".
(Or launch xLights with -a.)  Source: documentation/xlDo Commands.txt in the xLights repo.

  xl.py status                 what xLights has open
  xl.py close [--discard]      force-close the open sequence; REFUSES while its .xbkp is newer than the .xsq
                               (unsaved edits -- save first), --discard throws them away
  xl.py open  <file.xsq>       load a sequence from disk
  xl.py save                   API saveSequence (2026.17+), then wait for the .fseq to settle
  xl.py render                 one renderAll, serialised -- nothing may touch the sequence
                               while it runs (see the render rule below)
  xl.py reload <file.xsq>      BANNED: it is close+open+renderAll, i.e. churn under a render
  xl.py check  <file.xsq>      BANNED -- was in the 09-02 crash chain; validate.py covers it
"""
from __future__ import annotations
import argparse, json, sys, urllib.request, urllib.error
from pathlib import Path
import sys as _sys; from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from tc import mmss, mmss_ms, dur   # positions are m:ss; durations stay in seconds

PORT = 49913
URL = f"http://127.0.0.1:{PORT}/xlDoAutomation"

# The render rule, rewritten 2026-09-06 on the owner's evidence.
#
# The old rule was "never render from automation". It was wrong, and the owner designed the
# experiment that showed it: one API renderAll, warm cache, nothing else touching the
# sequence -- no crash. What actually crashed the Vega 16 was churn and queue depth:
#   09-02  renderAll + close/open + checkSequence inside 90s      -> 4 GPU resets
#          (`reload` was literally close+open+renderAll)             shader validation PASSED,
#                                                                    hung at execution point 0
#   09-04  a cold full headless -r, whole 94,080-channel sequence -> 1 GPU reset
#   09-06  ONE API renderAll, warm cache, nothing else            -> fine
# Both crash reports show WindowServer holding pending command buffers on the same GPU, so
# the display and the render were contending for one card.
#
# So: ONE render at a time, and NOTHING touches the sequence while it is in flight. That is
# what _RENDER_LOCK below enforces -- close/open refuse to run during a render, and a second
# render refuses to start. The COLD case is tested too: 09-06 18:44, straight after a
# regeneration, renderAll returned in 23.4s with no GPU event. See CLAUDE.md, docs/hardware.md.
_BANNED = {"reload": "close+open+renderAll -- churn under a live render, the 09-02 crash",
           "check": "checkSequence"}
for _a in sys.argv[1:]:
    if _a in _BANNED:
        raise SystemExit(f"REFUSING `xl.py {_a}` ({_BANNED[_a]}): automation-started renders "
                         "have crashed the GPU twice. Ask the owner to render and save in the GUI, "
                         "then decode the .fseq with tools/fseq.py.")


def call(cmd: dict, timeout=600) -> dict:
    req = urllib.request.Request(URL, data=json.dumps(cmd).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode()
    except urllib.error.HTTPError as e:
        # xLights answers 503 with a JSON body that says why (e.g. "Sequence not open.").
        # Report that verbatim instead of guessing.
        try:
            msg = json.loads(e.read().decode()).get("msg", "")
        except Exception:
            msg = ""
        if cmd.get("cmd") == "getOpenSequence" and "not open" in msg.lower():
            return {"res": "200", "seq": ""}          # a normal state, not an error
        raise SystemExit(f"xLights answered HTTP {e.code} to {cmd.get('cmd')}: {msg or '(no message)'}")
    except urllib.error.URLError as e:
        raise SystemExit(
            f"xLights automation is not reachable on port {PORT} ({e.reason}).\n"
            "  Is xLights running?  If so, enable it once:  Preferences -> Output -> API Port -> Port A (49913)\n"
            "  (or start xLights with the -a flag)")
    try:
        res = json.loads(body)
    except json.JSONDecodeError:
        res = {"raw": body}
    if str(res.get("res", "200")) != "200":
        raise SystemExit(f"xLights refused {cmd.get('cmd')}: {res}")
    return res


def show_folder():
    """The SHOW FOLDER xLights currently has loaded (`getShowFolder`)."""
    return Path(call({"cmd": "getShowFolder"}).get("folder", "")).resolve()


def _show_of(xsq: Path):
    """Walk up from a sequence to the folder holding its `xlights_rgbeffects.xml`."""
    for d in [xsq.resolve(), *xsq.resolve().parents]:
        if (d / "xlights_rgbeffects.xml").exists(): return d
    raise SystemExit(f"no xlights_rgbeffects.xml above {xsq}")


def assert_layout(xsq: Path, what: str):
    """REFUSE to touch a sequence while xLights has a DIFFERENT show folder loaded.

    The owner, 2026-09-19: *xLights had the Christmas layout loaded; make that a check, or it will ruin a lot of
    things, because the props change with the show folder*. The owner had opened a Christmas sequence so the
    agent could read how the Hattitudes are driven there, which
    switched xLights to the Christmas show folder; the next `open` + `render` ran a HALLOWEEN
    sequence against the CHRISTMAS layout, took 17s instead of 10, threw a dialog and wedged the
    API for 15 minutes. Nothing was lost only because the save never completed -- had it, every
    model that does not exist in the other layout could have been written out of the file.

    Models, groups and submodels are per show folder, so the layout is part of a sequence's
    identity, not an environment detail.
    """
    loaded, want = show_folder(), _show_of(xsq)
    if loaded != want:
        raise SystemExit(
            f"REFUSING {what}: xLights has the show folder {loaded} loaded, but "
            f"{xsq.name} belongs to {want}.\n"
            f"  Models and groups are per show folder -- rendering or saving across layouts can "
            f"drop every model the other layout does not have.\n"
            f"  In xLights: File -> Select Show Folder -> {want}, then re-run.")


def status():
    r = call({"cmd": "getOpenSequence"})
    if r.get("seq"):
        print(f"open: {r.get('fullseq') or r.get('seq')}   media: {Path(r.get('media','')).name}   len {mmss_ms(r.get('len',0))}")
    else:
        print("no sequence open")
    return r


def close(quiet=True, discard=False):
    _guard_not_rendering("closeSequence")   # tearing the sequence down under a live render
    # The owner's edits live in xLights' memory (10-01 #hand-edits-overwritten; 10-15 #wednesday-snowflakes: a close straight after
    # the owner's look dropped a Snowflakes the owner had placed -- it survived only in the .xbkp). xLights writes `<seq>.xbkp` only while the
    # sequence holds unsaved changes, so an autosave NEWER than the saved .xsq means edits a close would throw away.
    if not discard:
        seq = Path(call({"cmd": "getOpenSequence"}).get("fullseq") or "")
        bk = seq.with_suffix(".xbkp") if seq.name else None     # nothing open -> Path('.') -> with_suffix raises
        if bk is not None and seq.exists() and bk.exists() and bk.stat().st_mtime > seq.stat().st_mtime + 1:
            import time as _t
            hm = lambda p: _t.strftime("%H:%M:%S", _t.localtime(p.stat().st_mtime))
            raise SystemExit(f"REFUSING close: {bk.name} (autosave {hm(bk)}) is newer than the saved {seq.name} ({hm(seq)}) -- "
                             "xLights holds UNSAVED edits (the owner's, during a look?). `xl.py save` first and diff against our last "
                             "write (effects_diff.py), or `xl.py close --discard` only if they are ours to throw away.")
    # force=true is the point: the in-memory copy is stale once we've written the file.
    r = call({"cmd": "closeSequence", "quiet": "true" if quiet else "false", "force": "true"})
    print(f"closed: {r.get('msg')}")


def open_(xsq: Path):
    _guard_not_rendering("loadSequence")
    assert_layout(xsq, "loadSequence")
    r = call({"cmd": "loadSequence", "seq": str(xsq.resolve()), "promptIssues": "false"})
    print(f"opened: {r.get('msg', r)}")


STAMP = Path.home() / ".xlights-skill" / "last_render"
COOLDOWN_S = 180


_RENDER_LOCK = Path.home() / ".xlights-skill" / "render.lock"

def _render_in_flight():
    """True if a render is running. Stale locks (>20 min) are ignored -- a crash leaves one."""
    import time
    if not _RENDER_LOCK.exists(): return False
    if time.time() - _RENDER_LOCK.stat().st_mtime > 1200:
        _RENDER_LOCK.unlink(missing_ok=True); return False
    return True

def _guard_not_rendering(what):
    if _render_in_flight():
        raise SystemExit(f"REFUSING {what}: a render is in flight. Nothing may touch the sequence "
                         f"while it runs -- that is the 09-02 crash (close+open+checkSequence under "
                         f"a live renderAll, 4 GPU resets). Wait for it to return.")

def render(force=False):
    """ONE renderAll, serialised. Never chained, never concurrent with anything else."""
    import time
    if _render_in_flight() and not force:
        raise SystemExit("REFUSING renderAll: a render is already in flight. Two GPU jobs queued "
                         "together is the 09-02 failure. Wait for the first to return.")
    # and never render a sequence against someone else's layout (2026-09-19 #wrong-layout)
    _st = call({"cmd": "getOpenSequence"})
    if _st.get("fullseq"): assert_layout(Path(_st["fullseq"]), "renderAll")
    _RENDER_LOCK.parent.mkdir(exist_ok=True); _RENDER_LOCK.write_text(str(time.time()))
    try:
        t0 = time.time()
        r = call({"cmd": "renderAll"}, timeout=1800)
        print(f"renderAll returned after {time.time()-t0:.1f}s: {r}")
        return r
    finally:
        _RENDER_LOCK.unlink(missing_ok=True)

def _unused_old_render():
    raise SystemExit("REFUSING renderAll: automation-started renders have crashed the GPU twice. "
                     "The owner renders and saves in the GUI; decode the .fseq with tools/fseq.py.")
    print("rendering... (this is the ~45s part)")
    r = call({"cmd": "renderAll", "highdef": "false"}, timeout=1800)
    STAMP.touch()
    print(f"render: {r.get('msg')}")


def save(timeout=180):
    """Save via the API: `{"cmd": "saveSequence"}`.

    New in 2026.17 (Scott: "Added an MCP server alongside the existing REST Automation API";
    `saveSequence` is on BOTH `/mcp` and `/xlDoAutomation`, probed 2026-09-11 -- with nothing
    open it answers {"msg": "No sequence open."} and writes nothing). Until then the only save
    was a Cmd+S sent through System Events (kept below as `save_keystroke`, used only if the
    verb is missing on an older build). A render does not write the `.fseq`; a save does -- so
    this closes the last manual step in the loop.

    Same guards as before, because a save is still a write:
      * refuses while a render is in flight (nothing touches the sequence then);
      * refuses unless a sequence is open;
      * confirms by the .fseq mtime and reports honestly if it did not change.
    """
    import time
    _guard_not_rendering("save")
    st = call({"cmd": "getOpenSequence"})
    full = st.get("fullseq") or ""
    if not full:
        raise SystemExit("REFUSING save: xLights has no sequence open.")
    assert_layout(Path(full), "save")
    fseq = Path(full).with_suffix(".fseq")
    before = fseq.stat().st_mtime if fseq.exists() else 0
    t0 = time.time()
    try:
        r = call({"cmd": "saveSequence"}, timeout=timeout)
    except SystemExit as e:
        msg = str(e)
        if "Unknown" in msg or "unknown" in msg or "not recognised" in msg.lower():
            print(f"saveSequence not available on this build ({msg}); falling back to Cmd+S")
            return save_keystroke(timeout)
        raise
    t_api = time.time() - t0
    # `call` already raised on a non-200; the truth of "did it save" is the .fseq on disk --
    # and the API returns while xLights is STILL WRITING it (09-13 #save-settle: a read 2s
    # later saw 8.6 MB of 113 MB, black past 1:00). So wait for the size to stop moving.
    size, settle_s, note = _settle_fseq(fseq, before)
    after = fseq.stat().st_mtime if fseq.exists() else 0
    if after > before:
        tail = f"settled {size/1e6:.1f} MB in {settle_s:.1f}s" + (f" ({note})" if note else "")
        print(f"saved via API in {t_api:.1f}s: {r}  -> {fseq.name} ({size/1e6:.1f} MB) {tail}")
    else:
        print(f"saveSequence returned {r} in {t_api:.1f}s but {fseq.name} mtime did not change "
              f"after {settle_s:.1f}s ({note or 'no write seen'}) "
              f"-- the .xsq may have saved without a render; render first, then save")
    return r


def _settle_fseq(fseq: Path, before_mtime: float, appear_s=10.0, stable_s=2.0,
                 cap_s=120.0, poll_s=0.5):
    """Block until the `.fseq` stops growing. Polls the size every `poll_s`; done when it has
    been unchanged for `stable_s` AFTER the file's mtime moved past `before_mtime` (so an old,
    untouched file is not mistaken for a finished write). Gives up if no write shows within
    `appear_s`, or after `cap_s`. Returns (size_bytes, elapsed_s, note) -- note is '' when
    it settled cleanly."""
    import time
    t0 = time.time(); last = None; since = t0
    while True:
        now = time.time()
        st = fseq.stat() if fseq.exists() else None
        if st is not None and st.st_mtime > before_mtime:
            if st.st_size != last:
                last, since = st.st_size, now
            elif now - since >= stable_s:
                return last, now - t0, ""
        elif now - t0 >= appear_s:
            return (st.st_size if st else 0), now - t0, \
                f"{fseq.name} {'never appeared' if st is None else 'was not rewritten'} in {appear_s:.0f}s"
        if now - t0 >= cap_s:
            return (last or 0), now - t0, f"still growing after {cap_s:.0f}s -- do not read it yet"
        time.sleep(poll_s)


def save_keystroke(timeout=180):
    """Press Cmd+S in xLights, because the automation API cannot.

    2026.16 exposes `renderAll`, `batchRender` and `exportModelWithRender` and **no save verb**,
    yet a render does not write the `.fseq` -- a save does. Autosave is no help either: it
    writes `<sequence>.xbkp` and, in xLights' own words, "No render created". So the one step
    that had to stay manual was a keystroke, and this sends it.

    Guarded, because a blind Cmd+S is not the same as an API call:
      * refuses while a render is in flight (nothing touches the sequence then);
      * refuses unless xLights is running with a sequence open;
      * brings xLights to the front and checks it actually got there, so the keystroke cannot
        land in another app;
      * confirms by watching the .fseq mtime, and reports honestly if it does not change.
    Needs Accessibility permission for whatever runs it (macOS will prompt once).
    """
    import subprocess, time
    _guard_not_rendering("save")
    st = call({"cmd": "getOpenSequence"})
    # `seq` is the bare NAME ("Be Prepared"); `fullseq` is the path. Using `seq` watched a
    # nonexistent file in the CWD, so the first save reported failure while actually working.
    full = st.get("fullseq") or ""
    if not full:
        raise SystemExit("REFUSING save: xLights has no sequence open.")
    fseq = Path(full).with_suffix(".fseq")
    before = fseq.stat().st_mtime if fseq.exists() else 0

    front = subprocess.run(["osascript", "-e",
        'tell application "System Events" to name of first application process whose frontmost is true'],
        capture_output=True, text=True).stdout.strip()
    subprocess.run(["osascript", "-e", 'tell application "xLights" to activate'],
                   capture_output=True, text=True)
    time.sleep(1.2)
    now = subprocess.run(["osascript", "-e",
        'tell application "System Events" to name of first application process whose frontmost is true'],
        capture_output=True, text=True).stdout.strip()
    if "xlights" not in now.lower():
        raise SystemExit(f"REFUSING save: xLights did not come to the front (frontmost is {now!r}). "
                         "The keystroke would have gone to the wrong app.")
    r = subprocess.run(["osascript", "-e",
        'tell application "System Events" to tell process "xLights" to keystroke "s" using command down'],
        capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"save keystroke failed: {r.stderr.strip()}\n"
                         "If this says 'not allowed assistive access', grant Accessibility "
                         "permission to the app running this, in System Settings > Privacy.")
    print(f"sent Cmd+S to xLights (was frontmost: {front!r}); waiting for {fseq.name} ...")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fseq.exists() and fseq.stat().st_mtime > before:
            time.sleep(1.5)                      # let the write settle
            print(f"saved: {fseq.name} written after {time.time()-t0:.1f}s "
                  f"({fseq.stat().st_size/1e6:.1f} MB)")
            return True
        time.sleep(1.0)
    print(f"WARNING: {fseq.name} did not change within {timeout}s. It may still be writing, or "
          f"xLights may have had nothing to save, or a dialog may have taken the keystroke. "
          f"Check xLights before assuming this worked.")
    return False


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status"); sub.add_parser("save")
    cp = sub.add_parser("close"); cp.add_argument("--discard", action="store_true", help="close even with unsaved edits (the .xbkp is newer)")
    rp = sub.add_parser("render"); rp.add_argument("--force-render", action="store_true")
    for n in ("open", "reload", "check"):
        sp = sub.add_parser(n); sp.add_argument("xsq")
        if n == "reload":
            sp.add_argument("--no-render", action="store_true", help="just reopen; render by hand in xLights")
            sp.add_argument("--force-render", action="store_true")
    a = ap.parse_args()
    if a.cmd == "status": status()
    elif a.cmd == "close": close(discard=a.discard)
    elif a.cmd == "save": save()
    elif a.cmd == "open": open_(Path(a.xsq))
    elif a.cmd == "render": render(force=a.force_render)
    elif a.cmd == "check":
        # Manual only. Never run this in a loop after a render: it closes and re-opens the
        # sequence and leaves nothing open. Our own validators cover what it checks.
        print("NOTE: check-sequence closes and re-opens the sequence; do not chain it after a render.")
        r = call({"cmd": "checkSequence", "seq": str(Path(a.xsq).resolve())}, timeout=600)
        print(f"check: {r.get('msg')}  report: {r.get('output')}")
    elif a.cmd == "reload":
        close(); open_(Path(a.xsq))
        if not a.no_render: render(force=a.force_render)
        status()


if __name__ == "__main__":
    main()
