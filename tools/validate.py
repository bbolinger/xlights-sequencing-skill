#!/usr/bin/env python
"""Pre-flight checks on a generated .xsq. Everything here is a failure mode that
renders fine and looks wrong, so none of it shows up as an error in xLights.

  * a group/model name that does not resolve is silent dead air
  * two effects overlapping on one layer is illegal
  * an effect shorter than one 25ms frame renders as nothing
  * timing-track marks overlap by a few ms out of Whisper and the Faces effect reads
    those layers -- check them SEPARATELY from model effects, or the report conflates
    the two (CLAUDE.md)
  * a section boundary that butt-joins instead of blending is the default failure mode
    of a generated sequence
  * a palette gradient between two saturated colours far apart in hue passes through a
    colour nobody chose -- red->green is olive, yellow->blue is grey (check 17, WARN)
"""
import sys, json, collections, re, colorsys
from pathlib import Path as _P; sys.path.insert(0, str(_P(__file__).resolve().parent))
from tc import mmss, mmss_ms, span   # mm:ss, never raw seconds
from pathlib import Path
from lxml import etree
import os as _os, types as _types

# ---- inlined from the full toolkit so this file stands alone (copied 2026-11-01, behaviour unchanged) --------------
# compose.buffer_for + compose.MULTIPROPS (checks 3b, 3c); breakdown.load_xlights + wordcheck.py (checks 6b, 16).

# Element-name tokens that mark a PROP (irregular pixels: needs `Per Model Default Deep`), vs a house group or hero
# that keeps the model's own default buffer. Vendor-prop families, not one show's names.
PROP_TOKENS = ("hatitude", "hattitude", "outer ring", "inner ring", "spider", "bat",
               "pumpkin", "spinner", "spoke", "torch", "bell", "tombstone", "mini bats",
               "wreath", "eyeball")
# Families of IDENTICAL props render the same image on every member, the way the pros do it (Overlay - Centered).
OVERLAY_FAMILIES = {"tombstones", "Mini Trees"}

def buffer_for(element):
    """The buffer style this element needs, or None to leave it at the model's default."""
    if element in OVERLAY_FAMILIES:
        return "Overlay - Centered"
    if "/" in element:                      # an explicit submodel: always its own buffer
        return "Per Model Default Deep"
    low = element.lower()
    if any(t in low for t in PROP_TOKENS):
        return "Per Model Default Deep"
    return None                             # house groups and heroes: the model's default

# The GE "Hattitude Quartet" multiprop (rings + spinners + spokes + several outlines on one row). Check 3c reads
# an effect on its WHOLE row as a fault; a layout without these names gets n/a there.
MULTIPROPS = {"Hattitude Quartet", "Hattitude Quartet-2", "Hattitude Quartet-3"}

# xLights' own dictionaries (phoneme_mapping + standard/extended/user_dictionary). The macOS app-bundle path is the
# default; set XLIGHTS_DICTIONARIES to the folder on another OS or install.
XL_DICT = Path(_os.environ.get("XLIGHTS_DICTIONARIES")
               or "/Applications/xLights.app/Contents/Resources/dictionaries")

def load_xlights():
    """-> (phoneme -> viseme map, WORD -> phones dict), or (None, None) when the folder is not there."""
    if not (XL_DICT / "phoneme_mapping").exists(): return None, None
    mp = {}
    for line in open(XL_DICT / "phoneme_mapping"):
        line = line.split("#")[0].strip()
        if not line or line.startswith("."): continue
        k, v = line.split()[:2]; mp[k] = v
    dic = {}
    for name in ("extended_dictionary", "standard_dictionary", "user_dictionary"):     # later wins
        if not (XL_DICT / name).exists(): continue
        for line in open(XL_DICT / name, errors="ignore"):
            if not line.strip() or line.startswith(("#", ";")): continue
            parts = line.split()
            if len(parts) > 1: dic[parts[0].upper()] = parts[1:]
    return mp, dic

# wordcheck: EVERY WORD VERIFIED (a real pronunciation: sections.json `pronounce`, xLights' dictionaries, a possessive's
# base, CMU via `pronouncing` -- never spelled from letters) AND BROKEN DOWN (a mouth inside the word; 2+ syllables show
# 2+ shapes when the word lasts >= 150 ms).
WC_MIN_MS = 150

def wc_key_of(w):
    return re.sub(r"[^A-Z']", "", (w or "").upper()).strip("'")

def wc_pronounce(w, dic, over=None):
    """-> (phones, source) or (None, 'unverified')."""
    k = wc_key_of(w)
    if not k: return None, "no letters"
    over = over or {}
    if k in over: return list(over[k]), "sections.json pronounce"
    for kk, src in ((k, "xLights"), (k.replace("'", ""), "xLights"), (k.rstrip("'") + "G", "xLights (dropped g)")):
        if dic.get(kk): return list(dic[kk]), src
    if k.endswith("'S") and dic.get(k[:-2]): return list(dic[k[:-2]]) + ["Z"], "xLights (possessive)"
    try:
        import pronouncing
        p = pronouncing.phones_for_word(k.lower().replace("'", "") if "'" not in k[:-2] else k.lower())
        if not p and "'" in k: p = pronouncing.phones_for_word(k.lower().replace("'", ""))
        if p: return p[0].split(), "CMU"
    except ImportError:
        pass
    return None, "unverified"

def wc_expected(phones, mp):
    """-> (distinct shapes after merging neighbours, stressed vowels)."""
    seq = []
    for p in phones:
        vis = mp.get(p) or mp.get(re.sub(r"\d", "", p) + "1") or "etc"
        if not seq or seq[-1] != vis: seq.append(vis)
    return len(seq), sum(1 for p in phones if p[-1:].isdigit())

def wc_unbroken(w, s, e, shapes, phones, mp):
    """shapes = labels of the non-`rest` shapes inside the word. -> a reason string, or None when the word is broken down."""
    if not shapes: return "no mouth shape at all"
    if phones is None or e - s < WC_MIN_MS: return None
    ne, nv = wc_expected(phones, mp)
    if nv >= 2 and len(shapes) < 2: return f"{nv} syllables, {len(shapes)} shape"
    return None

_WORDCHECK = _types.SimpleNamespace(key_of=wc_key_of, pronounce=wc_pronounce, unbroken=wc_unbroken)
# ---- end of the inlined helpers ------------------------------------------------------------------------------------

def main():
    xsq = Path(sys.argv[1]); show = Path(sys.argv[2])
    cfg = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
    secs = cfg.get("sections", [])
    r = etree.parse(str(xsq)).getroot()
    rgb = etree.parse(str(show / "xlights_rgbeffects.xml")).getroot()
    known = {m.get("name") for m in rgb.iter("model")} | {g.get("name") for g in rgb.iter("modelGroup")}
    subs = {(m.get("name"), s.get("name")) for m in rgb.iter("model") for s in m.iter("subModel")}
    fail = 0

    model_eff, timing_eff = [], []
    for el in r.find("ElementEffects").iter("Element"):
        nm, typ = el.get("name"), el.get("type")
        for lay in el.iter():
            if lay.tag == "EffectLayer": key = nm
            elif lay.tag == "SubModelEffectLayer": key = f"{nm}/{lay.get('name')}"
            else: continue
            rows = [(int(e.get("startTime")), int(e.get("endTime")), e.get("name") or e.get("label") or "")
                    for e in lay.findall("Effect")]
            (timing_eff if typ == "timing" else model_eff).append((key, id(lay), rows))

    # 0. Fire census. Allowed while xLights GPU rendering is OFF (the owner 2026-09-12, journal
    #    #fire-allowed); the 09-08 hangs were with it ON. Info only -- not counted as a failure.
    fires = [(key, s, e) for key, _, rows in model_eff for s, e, n in rows if n == "Fire"]
    if fires:
        print(f"info  {len(fires)} Fire effect(s) -- allowed while GPU rendering is OFF (the owner 2026-09-12); "
              f"if GPU rendering is ever ON again, treat as FAIL: "
              + ", ".join(f"{k} {span(s/1000, e/1000)}" for k, s, e in fires[:6]))
    else:
        print("ok    no Fire effects")

    # 1. names
    bad = set()
    for key, _, rows in model_eff:
        if not rows: continue
        if "/" in key:
            m, s = key.split("/", 1)
            if (m, s) not in subs: bad.add(key)
        elif key not in known: bad.add(key)
    if bad:
        fail += 1; print(f"FAIL  unresolved element names (silent dead air): {sorted(bad)}")
    else:
        print(f"ok    every element name resolves ({len({k for k,_,rw in model_eff if rw})} used)")

    # ---- check 13: ONE VOICE, ONE PLACE.  The owner 2026-09-30, after the pumpkins were ADDED as a
    # second face for the hyenas: *moving a face means moving it, not adding it to another prop as
    # well -- one person singing from two places is a bug*.
    # At any instant a timing track drives Faces on ONE prop.  `facepack.py` moves, never copies.
    import re as _re
    _db = [(x.text or "") for x in r.find("EffectDB")] if r.find("EffectDB") is not None else []
    _drv = collections.defaultdict(list)                  # track -> [(s, e, element)]
    for el in r.find("ElementEffects").findall("Element"):
        if el.get("type") != "model": continue
        for e in el.iter("Effect"):
            if e.get("name") != "Faces" or not (e.get("ref") or "").isdigit() or int(e.get("ref")) >= len(_db): continue
            m = _re.search(r"E_CHOICE_Faces_TimingTrack=([^,]*)", _db[int(e.get("ref"))])
            if m and m.group(1): _drv[m.group(1)].append((int(e.get("startTime")), int(e.get("endTime")), el.get("name")))
    _two = []
    for tr, L in _drv.items():
        L.sort()
        for i, (s, e, a) in enumerate(L):
            for s2, e2, b in L[i + 1:]:
                if s2 >= e: break
                if b != a: _two.append((tr, max(s, s2), min(e, e2), a, b))
    if _two:
        fail += 1
        per = collections.defaultdict(list)
        for tr, s, e, a, b in _two: per[(tr, a, b)].append((s, e))
        print(f"FAIL  one voice sings from TWO props at once, {len(_two)} span(s) -- move the face, never copy it "
              f"(rules.md#casting, one voice one place):")
        for (tr, a, b), sp in sorted(per.items(), key=lambda kv: -len(kv[1])):
            print(f"        {tr}: {a} + {b}, {len(sp)} span(s), {sum(e - s for s, e in sp)/1000:.1f}s, first {span(sp[0][0]/1000, sp[0][1]/1000)}")
    else:
        print(f"ok    every voice sings from one prop at a time ({len(_drv)} track(s) drive faces)")

    # 2/3. overlaps and sub-frame effects, model layers only
    ov = shorts = 0
    for key, _, rows in model_eff:
        rows.sort()
        for i, (s, e, n) in enumerate(rows):
            if e - s < 25: shorts += 1
            if i + 1 < len(rows) and e > rows[i + 1][0]: ov += 1
    print(("FAIL  " if ov else "ok    ") + f"{ov} overlapping effect pairs on model layers")
    print(("FAIL  " if shorts else "ok    ") + f"{shorts} effects under one 25ms frame")
    fail += bool(ov) + bool(shorts)

    # 3a. shimmer on a BED (>= 2.5 s) -- rule 9 "shimmer is flicker; beds are calm"; the owner 2026-10-01 on the
    #     Hattitude set washes that carried the show's Ghostbusters preset's Shimmer=1: the flickering had to stop.
    _db = [(x.text or "") for x in r.find("EffectDB")] if r.find("EffectDB") is not None else []
    shim = []
    for el in r.find("ElementEffects").iter("Element"):
        if el.get("type") != "model": continue
        for lay in el.iter():
            if lay.tag not in ("EffectLayer", "SubModelEffectLayer"): continue
            for e in lay.findall("Effect"):
                ri = e.get("ref")
                if ri is None or int(ri) >= len(_db): continue
                if int(e.get("endTime")) - int(e.get("startTime")) >= 2500 and re.search(r"_Shimmer=1(,|$)", _db[int(ri)]):
                    shim.append((el.get("name"), e.get("name"), int(e.get("startTime"))))
    if shim:
        fail += 1
        print(f"FAIL  {len(shim)} bed(s) of 2.5 s+ with Shimmer on (rule 9: shimmer is flicker, beds are calm):")
        for k, n, s_ in shim[:6]: print(f"        {mmss_ms(s_):>8} {n:<12} {k}")
    else:
        print("ok    no bed shimmers (rule 9)")

    # 3b. buffer style on props -- a note in the notes is weaker than a check here.
    #     The Hattitude Quartet's pixels are not on a regular grid, so a per-preview render
    #     sweeps the physical layout and lights the whole prop instead of the ring. This is
    #     silent: it renders fine and looks wrong.
    db = [(x.text or "") for x in r.find("EffectDB")] if r.find("EffectDB") is not None else []
    bad_buf = []
    # Gate on the LAYOUT: the check judges prop-like names (PROP_TOKENS) and explicit submodels. A layout with neither
    # has nothing it can judge, and says so (a check that quietly skips is worse than no check).
    _prop_like = sorted(n for n in known if buffer_for(n)) + sorted(f"{m}/{x}" for m, x in subs)
    if not _prop_like:
        print("n/a   prop buffer check (3b) -- no such prop in this layout (nothing named like a multiprop, ring, spider, "
              "bat, pumpkin, spinner, tombstone or wreath, and no submodels)")
    for el in (r.find("ElementEffects").iter("Element") if _prop_like else ()):
        if el.get("type") != "model": continue
        for lay in el.iter():
            if lay.tag == "EffectLayer": key = el.get("name")
            elif lay.tag == "SubModelEffectLayer": key = f"{el.get('name')}/{lay.get('name')}"
            else: continue
            if buffer_for(key) is None: continue          # house elements may sweep: that is the point
            # HIS OWN FILES USE PER-PREVIEW ON A CHARACTER, AND HIS FILE IS THE AUTHORITY.
            # The fault this check was written for is a per-preview effect across the concentric
            # RINGS, where one arc crosses all eleven and lights ~8% of each ("all the sub models
            # light up", 09-03). A single character submodel -- Spider, Bat Wings Flying, Blob or
            # Ghost, Mouth N -- is one compact shape, and a chase rendered across its own preview
            # footprint is how the chase runs THROUGH it: Ghostbusters does exactly that
            # (`Spider` + SingleStrand at `Per Preview`), and `Outer Rings` carries 75 per-preview
            # Pinwheels in Home Alone. Counted, not assumed. rules.md#hattitude, 2026-09-19 #vision
            _, _, _sub = key.partition("/")
            # Mini Trees (10-01, run 6): a regular cone, not concentric rings. Counted: the owner's own
            # files put Per Preview on the mini trees 145x per tree (This is Halloween), 29x (Addams
            # Family), 8x (Nightmare) and `Per Model Per Preview` 9x on the Mini Trees GROUP (Hocus
            # Pocus); the pro library has 324 Per Preview uses on mini trees in 11 songs.
            attested = (_sub.startswith(("Spider", "Bat ", "Blob or Ghost", "Mouth"))
                        or key in ("Outer Rings", "Mini Trees"))
            for e in lay.findall("Effect"):
                ri = e.get("ref")
                if ri is None or int(ri) >= len(db): continue
                if "Per Preview" in db[int(ri)] and not attested:
                    bad_buf.append((key, e.get("name"), int(e.get("startTime"))))
    if bad_buf:
        fail += 1
        print(f"FAIL  {len(bad_buf)} prop effects sweep the physical preview "
              f"(irregular pixels light up; use Per Model Default Deep):")
        for k, n, s in bad_buf[:6]: print(f"        {mmss_ms(s):>8} {n:<12} {k}")
        print("      fix in place with:  fix_buffers.py <file.xsq>")
    elif _prop_like:
        print("ok    no prop effect sweeps the physical preview")

    # 3c. an effect on a MULTIPROP'S WHOLE ROW -- the owner 2026-10-07, Thriller: effects had gone onto the whole
    #     Hattitude prop, lighting every pixel instead of the spinners, spokes and rings. vendor_remap.py had
    #     copied 666 vendor spinner effects onto the whole Hattitude rows; a whole-prop buffer is every outline the GE prop
    #     carries (pumpkin, bat, spider, tree, bells...). Counted in the show's 30 Halloween files: the whole rows carry Faces
    #     (a face definition lives there) and Off masks; anything else is at most ONE effect a song (Remix: a Twinkle,
    #     19.8 s; Thriller's original: an On, 0.9 s). So: 1-2 = WARN (the show's idiom, rare), 3+ = FAIL. rules.md#hattitude
    _MP = MULTIPROPS & known                         # only the multiprops THIS layout has
    whole = []
    for el in (r.find("ElementEffects").findall("Element") if _MP else ()):
        if el.get("type") != "model" or el.get("name") not in _MP: continue
        for lay in el.findall("EffectLayer"):
            for e in lay.findall("Effect"):
                if e.get("name") not in ("Faces", "Off"): whole.append((el.get("name"), e.get("name"), int(e.get("startTime"))))
    if not _MP:
        print(f"n/a   multiprop whole-row check (3c) -- no such prop in this layout ({', '.join(sorted(MULTIPROPS))})")
    elif len(whole) > 2:
        fail += 1
        print(f"FAIL  {len(whole)} effect(s) on a Hattitude's WHOLE row -- lights every outline on the prop; move them to "
              f"its spinner / ring / spoke group (retarget.py):")
        for k, n, s in whole[:6]: print(f"        {mmss_ms(s):>8} {n:<12} {k}")
    elif whole:
        print(f"WARN  {len(whole)} effect(s) on a Hattitude's whole row (the show's files: at most one a song): " +
              ", ".join(f"{n} {mmss_ms(s)} {k}" for k, n, s in whole))
    else:
        print("ok    no effect on a Hattitude's whole row but Faces / Off")

    # 4. timing tracks, separately
    tov = 0
    for key, _, rows in timing_eff:
        rows.sort()
        for i, (s, e, n) in enumerate(rows):
            if i + 1 < len(rows) and e > rows[i + 1][0]: tov += 1
    print(("FAIL  " if tov else "ok    ") + f"{tov} overlapping marks on timing layers")
    fail += bool(tov)

    # 5. blended boundaries: something must already be running across each section start
    if secs:
        spans = collections.defaultdict(list)
        for key, lid, rows in model_eff:
            for s, e, n in rows: spans[key].append((s, e))
        hard = []
        for sec in secs[1:]:
            t = int(sec["start"] * 1000)
            crossing = sum(1 for k in spans for s, e in spans[k] if s < t - 200 and e > t + 200)
            if crossing == 0: hard.append((sec["name"], sec["start"]))
        if hard: print("WARN  section starts with nothing crossing them (hard cut): "
                       + ", ".join(f"{n} {mmss(t)}" for n, t in hard))
        else:    print(f"ok    every section boundary has material crossing it (blended)")

    # 6. THE FILE MUST MATCH THE ANALYSIS.
    #
    # Added 2026-09-07 after a night in which four separate tools silently dropped or mangled
    # lyric data and nothing noticed until the owner saw it on screen: `cast.line_at` gave Scar's
    # words to the hyenas; `voices_of_phoneme` gave the hyenas' visemes to Scar (Shenzi kept 4
    # of 13 shapes in a phrase); the viseme sequentialiser deleted shapes across speakers;
    # `recast.py` left the whole-song lyric track on stale phonemes while the character tracks
    # were rebuilt. The owner: *"So how do you make sure we don't make this mistake again"*.
    # Documentation did not prevent any of them -- this does, by refusing to pass a file whose
    # timing tracks disagree with `casting.json`.
    # Find analysis/ by walking UP, so a backup that lives inside analysis/ is still checked.
    # The first version looked only at `xsq.parent/"analysis"` and therefore SILENTLY SKIPPED
    # every backup -- it reported PASSED on three files known to be broken. A check that can
    # quietly not run is worse than no check, so say so out loud when it cannot.
    an = None
    for d in [xsq.parent, *xsq.parents]:
        if (d / "analysis" / "casting.json").exists(): an = d / "analysis"; break
        if d.name == "analysis" and (d / "casting.json").exists(): an = d; break
    if an is None:
        # A song with no singing has no casting to check, and that is a FACT about the song,
        # not a check quietly failing to run. Halloween Mike Meyers' demucs vocals stem sits
        # at -66..-84 dB for its whole length; it has no script.json, no casting.json and no
        # timing tracks by design. `instrumental: true` in sections.json says so out loud, so
        # this reports n/a instead of a warning that trains the eye to ignore warnings. Any
        # song WITHOUT that flag and without casting.json still gets the loud DID NOT RUN.
        if cfg.get("instrumental"):
            n_tracks = len({k for k, _, _ in timing_eff if k != "Black Holes"})   # review marks, not lyric data (blackholes.py)
            if n_tracks:
                print(f"FAIL  sections.json says instrumental, but the file has {n_tracks} timing "
                      f"track(s) -- one of the two is wrong")
                fail += 1
            else:
                print("n/a   instrumental (sections.json): no casting, no timing tracks, "
                      "nothing for the casting check to compare")
        else:
            print("WARN  no analysis/casting.json found -- the file-matches-analysis check DID NOT RUN")
    cast_f = (an / "casting.json") if an else None
    if cast_f and cast_f.exists():
        cast = json.load(open(cast_f))
        want = {}
        # a song whose faces read a track it did not name after the character (a vendor sequence:
        # Everyday Is Halloween's faces read `01EverydayIsHalloween`) maps it in sections.json ->
        # casting.tracks {character: track}; retrack.py writes that track
        _tmap = (cfg.get("casting") or {}).get("tracks") or {}
        for ch in cast.get("characters", []):
            v = cast["voices"][ch]
            want[_tmap.get(ch, ch.capitalize())] = (len(v["words"]), len(v["phonemes"]))
        got = {}
        for key, _, rows in timing_eff:
            got.setdefault(key, []).append(len(rows))
        bad = []
        for name, (nw, nph) in want.items():
            layers = sorted(got.get(name, []), reverse=True)
            if not layers: bad.append(f"{name}: track MISSING from the file"); continue
            # the three layers are phrases / words / phonemes; compare the two that matter
            if nph and not any(abs(n - nph) <= max(3, nph * 0.02) for n in layers):
                bad.append(f"{name}: casting.json has {nph} phonemes, file has {layers}")
            if nw and not any(abs(n - nw) <= max(3, nw * 0.02) for n in layers):
                bad.append(f"{name}: casting.json has {nw} words, file has {layers}")
        # The PHONEME layer must carry rest marks. `timing_eff` holds one entry per LAYER
        # (phrases / words / phonemes), so check only the densest one -- the phrases and words
        # layers have no rests by design and flagging them was a false positive of this check.
        densest = {}
        for key, _, rows in timing_eff:
            if key not in want: continue
            if len(rows) > len(densest.get(key, [])): densest[key] = rows
        for key, rows in densest.items():
            labs = [n for _, _, n in rows]
            if labs and len(labs) > 30 and "rest" not in labs:
                bad.append(f"{key}: phoneme layer has no `rest` marks -- the mouth never "
                           f"closes (rules.md#casting)")
        # A track that drives an MLS pumpkin's Faces uses the FULL mouth set (rules.md#casting, the owner 2026-10-09:
        # "it just moves up and down when this has like 8 faces"): 8 mouths, 9 non-rest shapes -- breakdown.py's
        # open-shut mode gave Everyday / Thriller 6 of them (M3 / M4 never lit). Counted on the densest layer.
        _pump_models = sorted(n for n in known if n.startswith("MLS Pumpkin"))
        if not _pump_models:
            print("n/a   pumpkin mouth-set check (6b) -- no such prop in this layout (MLS Pumpkin*)")
        _pump_tracks = set()
        for _el in (r.find("ElementEffects").findall("Element") if _pump_models else ()):
            if _el.get("type") != "model" or not (_el.get("name") or "").startswith("MLS Pumpkin"): continue
            for _q in _el.iter("Effect"):
                if _q.get("name") == "Faces" and (_q.get("ref") or "").isdigit():
                    _m = re.search(r"E_CHOICE_Faces_TimingTrack=([^,]+)", db[int(_q.get("ref"))])
                    if _m: _pump_tracks.add(_m.group(1))
        _FULL = {"AI", "E", "etc", "L", "O", "U", "WQ", "FV", "MBP"}
        # A track whose WORDS hold no L / U / W sound cannot use those mouths in the full breakdown either (Feed My
        # Frankenstein 10-12: the side pumpkins sing only "Feed my Frankenstein" / "He's a psycho" -- xLights' own
        # dictionary + phoneme_mapping give 6 shapes). So a short track fails only on a shape its OWN words call for;
        # a word the dictionaries lack keeps the strict 8-of-9 test.
        try:
            _xmap, _xdic = load_xlights()               # (None, None) when xLights' dictionaries are not installed here
        except Exception:
            _xmap = _xdic = None
        for key, rows in densest.items():
            if key not in _pump_tracks: continue
            have = {n for _, _, n in rows} & _FULL
            if len(have) >= 8: continue
            called = None
            _lay = sorted((rws for k2, _, rws in timing_eff if k2 == key), key=len)
            if _xmap and len(_lay) >= 2:
                called = set()
                for _, _, w in _lay[-2]:                                  # the WORD layer (phrases < words < phonemes)
                    ph = _xdic.get(re.sub(r"[^A-Z']", "", (w or "").upper()))
                    if ph is None: called = None; break
                    called |= {_xmap.get(p) for p in ph} & _FULL
            missing = (called - have) if called is not None else (_FULL - have)
            if missing:
                bad.append(f"{key}: drives an MLS pumpkin with {len(have)} of 9 shapes ({', '.join(sorted(missing))} never"
                           f"{' though its words call for them' if called is not None else ''}) "
                           f"-- a pumpkin track uses all 8 mouths, never open-shut (rules.md#casting)")
            else:
                print(f"info  {key}: {len(have)} of 9 shapes -- every shape its {len(_lay[-2])} words call for "
                      f"in xLights' dictionary ({', '.join(sorted(_FULL - have))} are not in them)")
        if bad:
            print(f"FAIL  {len(bad)} timing track(s) disagree with casting.json:")
            for b in bad[:8]: print(f"        {b}")
            print("      re-run:  align.py -> cast.py -> recast.py")
            fail += 1
        else:
            print(f"ok    every character timing track matches casting.json "
                  f"({len(want)} tracks) and carries rest marks")

    # 7. THE TUNE-TO SIGN SHOWS THE STATION ALL SONG (rules.md#tune-to).
    #
    # The owner 2026-09-13: no digits were lit, so no one driving by would know which station to tune to; the
    # sign normally stays lit the whole song except in a blackout, with a fade in and out at the ends. Be Prepared ran five days with the
    # sign dark and nothing said so. The sign's element, text and (for a digit model) the
    # submodels that spell the station come from sections.json -> "tune_to"; every one of them
    # must be covered from the show start to song_end, except inside `stops` (whole-house dark
    # is the ONE time the sign goes out with the house). More than 1.0 s uncovered, cumulative,
    # fails; so does a Text effect on the sign that does not say the station. No block = n/a,
    # said out loud -- a check that quietly skips is worse than no check.
    tt = cfg.get("tune_to")
    if not tt:
        print("n/a   no `tune_to` block in sections.json -- the sign check has nothing to check "
              "(add {element, text[, submodels]} if this show has a tune-to sign)")
    elif tt.get("element") not in known:
        print(f"n/a   tune-to sign {tt.get('element')!r} (sections.json tune_to) -- no such prop in this layout")
    else:
        t0, t1 = int(float(cfg.get("start", 0)) * 1000), int(float(cfg.get("song_end", 0)) * 1000)
        stops = [(int(float(s["start"]) * 1000), int(float(s["end"]) * 1000)) for s in cfg.get("stops", [])]
        elem, text = tt["element"], str(tt["text"])
        targets = [f"{elem}/{s}" for s in tt.get("submodels", [])] or [elem]
        by_key = collections.defaultdict(list)
        for key, _, rows in model_eff:
            by_key[key].extend(rows)
        bad = []
        for key in targets:
            rows = sorted(by_key.get(key, []))
            # uncovered time inside [t0, t1] minus the stops, in 25 ms frames
            frames = range(t0, t1, 25)
            covered = 0; gaps = []; run = None
            for f in frames:
                if any(s <= f < e for s, e in stops):
                    inside = True
                else:
                    inside = any(s <= f < e and n != "Off" for s, e, n in rows)
                if inside:
                    covered += 1
                    if run: gaps.append(run); run = None
                else:
                    run = [f, f + 25] if run is None else [run[0], f + 25]
            if run: gaps.append(run)
            unc = sum(e - s for s, e in gaps)
            if unc > 1000:
                bad.append(f"{key}: uncovered {unc/1000:.1f}s, first at "
                           + ", ".join(span(s/1000, e/1000) for s, e in gaps[:3]))
        # a Text effect on the sign must say the station
        for el in r.find("ElementEffects").iter("Element"):
            if el.get("type") != "model" or el.get("name") != elem: continue
            for lay in el.iter():
                if lay.tag not in ("EffectLayer", "SubModelEffectLayer"): continue
                for e in lay.findall("Effect"):
                    if e.get("name") != "Text": continue
                    ri = e.get("ref"); st = db[int(ri)] if ri is not None and int(ri) < len(db) else ""
                    line = dict(kv.split("=", 1) for kv in st.split(",") if "=" in kv).get("E_TEXTCTRL_Text", "")
                    if text not in line:
                        bad.append(f"{elem} Text at {mmss_ms(int(e.get('startTime')))} says {line!r}, not {text!r}")
        if bad:
            fail += 1
            print(f"FAIL  the tune-to sign ({elem} = {text!r}) is not lit all song (rules.md#tune-to):")
            for b in bad[:8]: print(f"        {b}")
            print("      place it with:  tuneto.py <file.xsq> --dry-run  (twice, diff) then --apply")
        else:
            print(f"ok    tune-to sign {elem} reads {text!r} from {mmss(t0/1000)} to {mmss(t1/1000)} on "
                  f"{len(targets)} target(s), dark only in {len(stops)} stop(s)")

    # 8. THE MINI TREES CARRY THE MEGATREE (rules.md#minitrees, approved 2026-09-14).
    #
    # The owner 2026-09-14: *the house kept feeling empty, and this is the missing weight: the mini
    # trees are barely used. Most of the MegaTree's effects normally go over to them too, to carry
    # it through the song*. Be Prepared had the mini
    # trees lit 7 % of node-seconds against 27-68 % in the show's songs, and nothing said so. In the show's
    # files the effect-seconds REACHING each mini tree (its own row plus every group that
    # expands to it) are a median 0.87 of the effect-seconds reaching the MegaTree (its row,
    # masks excluded, plus its groups); 17 of the 21 songs with a real MegaTree part sit at
    # 0.39 or above, and the four below (Thriller 0.03, Feed My Frankenstein 0.18, Name of
    # Jesus 0.18, Around The World 0.00) are the ones where the owner left them dark. WARN below
    # 40 % -- a warning, not a failure, by the rule's own text (WARN). n/a, said out loud,
    # when the layout has no mini trees or the file has no MegaTree row.
    MINI_SHARE = 0.40
    MASKS = {"Pictures", "Video", "Shape", "Faces"}
    gmodels = {g.get("name"): [x for x in (g.get("models") or "").split(",") if x] for g in rgb.iter("modelGroup")}
    def _expand(n, seen=()):
        if n in gmodels and n not in seen:
            return {m for x in gmodels[n] for m in _expand(x, seen + (n,))}
        return {n.split("/")[0]}
    minis = [m for m in ("Mini Tree L", "Mini Tree R") if m in known]
    secs_of = collections.defaultdict(float)          # element -> effect-seconds (masks excluded)
    for key, _, rows in model_eff:
        for s, e, n in rows:
            if n not in MASKS: secs_of[key.split("/")[0]] += (e - s) / 1000
    if not minis:
        print("n/a   the layout has no Mini Tree L / Mini Tree R -- nothing for the mini-tree check to compare")
    elif "MegaTree" not in secs_of:
        print("n/a   no MegaTree effects in the file -- the mini-tree share has no denominator")
    else:
        def reach(model):
            return sum(v for k, v in secs_of.items() if k == model or (k in gmodels and model in _expand(k)))
        mega = reach("MegaTree")
        low = []
        parts = []
        for m in minis:
            ratio = reach(m) / mega if mega else 0.0
            parts.append(f"{m} {reach(m):.0f}s / MegaTree {mega:.0f}s = {ratio:.2f}")
            if ratio < MINI_SHARE: low.append(m)
        if low:
            print(f"WARN  mini trees carry under {MINI_SHARE:.0%} of the MegaTree (the show's files: median 0.87, 17/21 songs "
                  f">= 0.39): " + "; ".join(parts))
            print("      mirror it with:  minitrees.py <file.xsq> --dry-run  (twice, diff) then --apply")
        else:
            print(f"ok    mini trees carry the MegaTree (>= {MINI_SHARE:.0%}): " + "; ".join(parts))

    # ---- check 9: BURIED GESTURES -- a wide element painted OVER a narrower one
    #
    # The owner 2026-09-16: *make it a rule to always check the other layers and what is left -- no
    # layer conflicts that were not done on purpose*.
    #
    # The fault: a whole-house Shader went on `All Everything` (row 65) while the generator's
    # beds still ran on `MegaTree`, `ALL House`, `tombstones` and the mini trees -- all INSIDE
    # All Everything, all on earlier rows. 47 effects were alive in one 3.4s window. The file
    # validated clean, because per-element layer counts cannot see it: the effects are on
    # DIFFERENT elements and collide only after expansion.
    #
    # What is NOT flagged, because it is the documented pattern (rules.md#keys): a GROUP bed on
    # an early row with a NARROWER group or prop detailing over it on a later row. Render order
    # is row order, so narrower-on-top is how detail survives a bed.
    # What IS flagged: the reverse -- something WIDER on a LATER row, which paints across
    # everything beneath and buries whatever was underneath it.  rules.md#layers
    order = {}
    for i, el in enumerate(r.find("ElementEffects").findall("Element")):
        order.setdefault(el.get("name"), i)
    OVERLAP_OK = {"Faces", "Off"}      # a face owns its prop while singing; an Off is a mask
    paint = collections.defaultdict(list)
    for key, _, rows in model_eff:
        el = key.split("/")[0]
        reach = _expand(el) if el in gmodels else {el}
        for s, e, n in rows:
            if n in OVERLAP_OK: continue
            paint[el].append((s, e, n, frozenset(reach)))
    buried = collections.Counter(); worst = {}
    els = sorted(paint, key=lambda x: order.get(x, 0))
    for i, lo in enumerate(els):
        for hi in els[i + 1:]:                       # hi is on a LATER row -> paints on top
            if order.get(hi, 0) <= order.get(lo, 0): continue
            for s, e, n, ra in paint[lo]:
                for s2, e2, n2, rb in paint[hi]:
                    if s2 >= e or e2 <= s: continue
                    if not (ra < rb): continue        # only WIDER-on-top is a burial
                    ov = min(e, e2) - max(s, s2)
                    if ov < 400: continue             # a seam crossfade is deliberate
                    pair = (lo, hi)
                    buried[pair] += 1
                    if pair not in worst or ov > worst[pair][0]:
                        worst[pair] = (ov, max(s, s2), n, n2, len(rb) - len(ra))
    if not buried:
        print("ok    no buried gestures -- nothing wide is painted over something narrower beneath it")
    else:
        tot = sum(buried.values())
        print(f"WARN  {tot} buried gesture(s): a WIDER element on a LATER row painting over a "
              f"narrower one beneath it (rules.md#layers). Check each is deliberate:")
        for (lo, hi), n in buried.most_common(8):
            ov, at, n1, n2, extra = worst[(lo, hi)]
            print(f"        {hi!r} ({n2}) buries {lo!r} ({n1})  x{n}  "
                  f"worst {ov/1000:.1f}s at {mmss(at/1000)}, +{extra} extra models")
        print("      if it IS deliberate, the narrower effect should not be there at all -- "
              "mark the section `owned` so the generator keeps out.")

    # ---- check 10: WORD LAYER AND VISEME LAYER MUST AGREE, per track.
    #
    # The owner 2026-09-18: *when a word is regenerated, the text tied to it is cleared and regenerated
    # too -- stop the two fighting*. The word layer and the viseme layer of
    # one timing track are two copies of the same lyric; when one is rebuilt and the other is
    # not they drift, and the face reads a word the mouth is not making. Structural check:
    # every viseme lies inside ONE word of its own track, every word holds at least one
    # viseme, and no viseme crosses a word boundary. Refuses the file otherwise.
    HI_VOWELS, LO_VOWELS = {"AI", "E"}, {"O", "U", "WQ"}
    tracks = {}
    for key, _, rows in timing_eff:
        tracks.setdefault(key, []).append(sorted(rows))
    struct_bad = []; lip_pairs = {}          # track -> [(word, viseme, s, e)]
    VISEMES = {"AI", "E", "etc", "FV", "L", "MBP", "O", "U", "WQ", "rest"}
    def _is_viseme_layer(rows):
        labs = [n for _, _, n in rows if n]
        return bool(labs) and sum(n in VISEMES for n in labs) >= 0.9 * len(labs)
    for name, layers in tracks.items():
        # Identify layers by CONTENT, never by count. Be Prepared's whole-song track has 324
        # words and 246 phonemes -- the word layer is the denser one -- so "densest = visemes"
        # read it backwards and reported 236 "words with no viseme, e.g. 'rest'". A viseme
        # layer is the one whose labels are viseme names; the word layer is the densest of
        # the rest. 2026-09-18
        vis_layers = [l for l in layers if _is_viseme_layer(l)]
        other = [l for l in layers if not _is_viseme_layer(l) and l]
        if not vis_layers or not other: continue
        vis = max(vis_layers, key=len)
        words = max(other, key=len)
        if not words or not vis: continue
        w_of = lambda s, e: [w for w in words if w[0] - 30 <= s and e <= w[1] + 30]
        cross = [(s, e, n) for s, e, n in vis if n != "rest" and not w_of(s, e)]
        empty = [w for w in words if not any(s >= w[0] - 30 and e <= w[1] + 30 for s, e, n in vis if n != "rest")]
        if cross:
            struct_bad.append(f"{name}: {len(cross)} viseme(s) outside/crossing a word, e.g. "
                              f"{cross[0][2]} {mmss(cross[0][0]/1000)}-{mmss(cross[0][1]/1000)}")
        if empty:
            struct_bad.append(f"{name}: {len(empty)} word(s) with no viseme, e.g. {empty[0][2]!r} at "
                              f"{mmss(empty[0][0]/1000)}")
        lip_pairs[name] = [(next((w[2] for w in w_of(s, e)), "?"), n, s, e) for s, e, n in vis
                           if n in HI_VOWELS | LO_VOWELS]
    if struct_bad:
        _ntr = len({b.split(":")[0] for b in struct_bad})
        # On a song whose tracks are the owner's own hand edits, "run lipsync.py" is the WRONG
        # remedy -- the chain refuses that song, and rebuilding is what would destroy the
        # edits. There the disagreement is a list of marks to look at by hand, and it WARNs:
        # the show's file scored better against the stem than the rebuild did on every track
        # (2026-09-19 #hand-edits-refuse). Anywhere else it stays a FAIL with its fix.
        _he = (cfg.get("casting") or {}).get("hand_edited") if cfg else None
        if _he:
            print(f"WARN  word and viseme layers disagree on {_ntr} track(s) -- these tracks are "
                  f"HAND EDITS by {_he.get('by', 'the owner')}, so this is a list to fix BY HAND in "
                  f"xLights (or with tweak.py), never by rebuilding (rules.md#casting):")
        else:
            print(f"FAIL  word and viseme layers disagree on {_ntr} track(s) -- one was rebuilt "
                  f"without the other (rules.md#casting). Run lipsync.py, which rebuilds the whole chain:")
        for b in struct_bad[:6]: print(f"        {b}")
        fail += 0 if _he else 1
    elif tracks:
        print(f"ok    word and viseme layers agree on every track ({len(lip_pairs)} checked)")

    # ---- check 16: EVERY WORD VERIFIED AND BROKEN DOWN, on every track that drives a face.
    # The owner 2026-10-18, Be Prepared: "warthog's" sang as ONE closed shape for 725 ms (a word missing from xLights' dictionaries was
    # spelled from letters into mouth shapes, then mis-read as phones) -- the words had clearly not been broken down -> make
    # sure the script catches this from now on: every word verified and broken down. Unverified = no real pronunciation
    # (sections.json `pronounce`, xLights' dictionaries, a possessive's base, CMU); unbroken = a word with no mouth shape, or of 2+
    # syllables showing < 2 shapes over >= 150 ms (tools/wordcheck.py; breakdown.py refuses the same before it writes). Laughs
    # gags.py placed (timed by the film's mouths) are exempt.
    try:
        _WC = _WORDCHECK
        _mp, _dic = load_xlights() if _drv else (None, None)     # nothing drives a face: nothing to verify
        if _drv and _mp is None:
            raise ImportError(f"xLights' dictionaries not found at {XL_DICT} -- set XLIGHTS_DICTIONARIES to the "
                              f"xLights.app/Contents/Resources/dictionaries folder")
        _an = xsq.resolve().parent / "analysis"
        _cfg = cfg or (json.load(open(_an / "sections.json")) if (_an / "sections.json").exists() else {})
        _over = {k.upper(): v.split() for k, v in (_cfg.get("pronounce") or {}).items()}
        _gp = _an / "gags.placed.json"
        _gags = json.load(open(_gp)).get("marks", []) if _gp.exists() else []
        _unv, _unb, _nw = collections.Counter(), [], 0
        for name, layers in tracks.items():
            if name not in _drv: continue
            vis_layers = [l for l in layers if _is_viseme_layer(l)]
            other = [l for l in layers if not _is_viseme_layer(l) and l]
            if not vis_layers or not other: continue
            vis, words = max(vis_layers, key=len), max(other, key=len)
            keep = [(int(m["start"]), int(m["end"])) for m in _gags if m["track"] == name]
            for ws_, we_, w_ in words:
                if any(ws_ < b and a < we_ for a, b in keep): continue
                _nw += 1
                ph_, src_ = _WC.pronounce(w_, _dic, _over)
                if ph_ is None and _WC.key_of(w_): _unv[_WC.key_of(w_)] += 1
                sh_ = [n for a, b, n in vis if n != "rest" and a >= ws_ - 30 and b <= we_ + 30]
                why_ = _WC.unbroken(w_, ws_, we_, sh_, ph_, _mp)
                if why_: _unb.append((name, w_, ws_, we_, why_, sh_))
        if _unv or _unb:
            fail += 1
            print(f"FAIL  words not verified / not broken down on the face tracks (rules.md#casting, the owner 10-18 'we need all words "
                  f"verified and broken down'): {sum(_unv.values())} unverified, {len(_unb)} unbroken")
            if _unv:
                print(f"        UNVERIFIED (add sections.json pronounce {{WORD: \"CMU phones\"}}): " +
                      ", ".join(f"{k} x{c}" for k, c in _unv.most_common(12)))
            for name, w_, a, b, why_, sh_ in _unb[:12]:
                print(f"        UNBROKEN {name}: {w_!r} {mmss(a/1000)} ({b - a} ms): {why_} {sh_}")
        elif _drv:
            print(f"ok    every word verified and broken down ({_nw} words on {len(_drv)} face track(s))")
    except (ImportError, OSError) as ex:
        fail += 1; print(f"FAIL  word verification DID NOT RUN -- {ex}")

    # ---- check 11: EVERY VOWEL VISEME SCORED AGAINST THE AUDIO, with a percentage.
    #
    # The owner 2026-09-18: *"maybe a percentage calculator for areas to be checked too?"* This is
    # the check that would have caught today's fault before the owner did: an O placed at 925ms while
    # the vocals stem's spectral centroid was still ~2100 Hz -- the "ay" band -- for 900ms more.
    # The centroid of the vocals stem tracks the vowel: "ay"/"ee" (AI, E) sit high, ~2000-2400 Hz
    # on this singer; "oh"/"oo" (O, U, WQ) sit low, ~1450-1700. For each vowel viseme, measure
    # the centroid over its span and ask whether it is in the band its shape claims. Reports the
    # % that agree per track and lists the disagreements -- the words to go and LOOK at. WARN,
    # never FAIL: a singer can bend a vowel, and the owner's eye outranks this number.
    voc = None
    try:
        media = cfg.get("media")
        if an is not None and media:
            voc = an.parent / "media" / "stems" / Path(media).stem / "vocals.wav"
    except Exception: voc = None
    if not lip_pairs:
        pass
    elif voc is None or not voc.exists():
        print(f"WARN  lip-sync vs audio DID NOT RUN -- no vocals stem at "
              f"{voc if voc else '<no media in sections.json>'}")
    else:
        try:
            import numpy as _np, soundfile as _sf, librosa as _lr
            y, sr = _sf.read(str(voc)); y = y.mean(1) if y.ndim > 1 else y
            # The HIGH/LOW split is PER TRACK -- the median of that track's own vowel centroids --
            # unless sections.json pins `lip_split_hz`. A fixed 1800 Hz was derived from one
            # singer (Belafonte, Day-O 85-88%) and read Be Prepared's Scar -- a far darker voice --
            # at 65%, which is calibration, not a verdict on the sync. A singer's "ay" sits
            # above THEIR median and "oh" below it whatever their register. 2026-09-18
            PIN = cfg.get("lip_split_hz")
            for name, pairs in lip_pairs.items():
                if not pairs: continue
                meas = []
                for word, vis, s, e in pairs:
                    seg = y[int(s / 1000 * sr): int(e / 1000 * sr)]
                    if len(seg) < 512: continue
                    C = _lr.feature.spectral_centroid(y=seg, sr=sr, n_fft=min(2048, len(seg)),
                                                      hop_length=256)[0]
                    R = _lr.feature.rms(y=seg, frame_length=min(2048, len(seg)), hop_length=256)[0]
                    if not len(C) or R.max() < 0.02: continue     # no voice here to judge
                    meas.append((word, vis, s, e, float(_np.median(C[R > 0.02]))))
                if len(meas) < 6: continue
                # FIXED split, 1800 Hz, unless sections.json pins `lip_split_hz`. Two adaptive
                # schemes were tried and both were WORSE than the constant: a per-track median
                # (Day-O 85% -> 60%: a track with more ay/ee than oh/oo puts the median inside
                # the high cluster) and a two-cluster Otsu threshold (85% -> 25%: ~40 points
                # with consonant-smeared outliers is not two clean clusters). 1800 is derived
                # from ONE singer and is right for the owner; a darker voice needs its own pin,
                # calibrated from a few vowels the ear is sure of -- NOT guessed. Until a song
                # has a pin, treat its % as uncalibrated. 2026-09-18 journal #lip-split
                split = float(PIN) if PIN else 1800.0
                agree, rows_out = 0, []
                for word, vis, s, e, c in meas:
                    ok = (c >= split) == (vis in HI_VOWELS)
                    agree += ok
                    rows_out.append((ok, word, vis, s, e, c))
                n = len(rows_out)
                pct = 100.0 * agree / n
                flagged = [r for r in rows_out if not r[0]]
                print(f"{'ok  ' if pct >= 85 else 'WARN'}  lip-sync vs audio, {name}: {pct:.0f}% of "
                      f"{n} vowel visemes sit in the band their shape claims "
                      f"(split {split:.0f} Hz, {'pinned' if PIN else 'default -- UNCALIBRATED for this voice unless it is the Day-O singer'})")
                for ok, word, vis, s, e, c in flagged[:8]:
                    print(f"        LOOK: {word!r:>12} {vis:<3} {mmss(s/1000)}-{mmss(e/1000)}  "
                          f"centroid {c:5.0f} Hz reads {'HIGH (ay/ee)' if c >= split else 'LOW (oh/oo)'}")
            # ---- check 12: VOICE WITH NO MOUTH.
            # The owner 2026-09-18: *do they hold the "go" from 24.8 to 27.8, how was that missed?*.
            # Whisper dropped "home"; the transcript ended at 25.70 and the vocals stem was
            # still singing an "oh" to 27.7 with every face closed. Check 11 can only score
            # visemes that EXIST; this finds singing that has none. Scan the vocals stem for
            # RMS above threshold where no non-rest viseme is active on ANY track, and report
            # every such span >= 400ms. A span here is a dropped word, a dropped syllable, or
            # a line the script does not know about -- all three are what was missed.
            _covered = []
            for _n, _layers in tracks.items():
                if _n not in lip_pairs and _n not in {k for k in tracks if len(tracks[k]) >= 2}: continue
                _ls = sorted(_layers, key=len)
                if len(_ls) < 2: continue
                _covered += [(s, e) for s, e, n in _ls[-1] if n != "rest"]
            _covered.sort()
            _h = int(sr * 0.025)
            _r = _np.array([_np.sqrt((y[i:i + _h] ** 2).mean()) for i in range(0, len(y) - _h, _h)])
            _thr = float(cfg.get("voice_rms", 0.035))
            _on = _r > _thr
            _gaps, _start = [], None
            for _i, _v in enumerate(_on):
                _t = _i * 25
                _has = any(s - 60 <= _t <= e + 60 for s, e in _covered)
                if _v and not _has:
                    if _start is None: _start = _t
                else:
                    if _start is not None and _t - _start >= 400: _gaps.append((_start, _t))
                    _start = None
            if _start is not None: _gaps.append((_start, len(_on) * 25))
            _gaps = [(s, e) for s, e in _gaps if e - s >= 400]
            # spans the owner has ruled are NOT voice (instrument bleed in the stem) are skipped,
            # and said so -- sections.json -> vocal_ignore, in seconds
            _ign = [(int(a_ * 1000), int(b_ * 1000)) for a_, b_ in (cfg.get("vocal_ignore") or [])]
            _skipped = [g for g in _gaps if any(g[0] < b_ and g[1] > a_ for a_, b_ in _ign)]
            _gaps = [g for g in _gaps if g not in _skipped]
            if _skipped:
                print(f"info  {len(_skipped)} voiced span(s) skipped as sections.json vocal_ignore "
                      f"(the owner: instrument bleed, not voice)")
            if not _gaps:
                print("ok    no voice without a mouth -- every voiced span of the vocals stem has a viseme")
            else:
                _tot = sum(e - s for s, e in _gaps) / 1000
                print(f"WARN  voice with NO MOUTH: {len(_gaps)} span(s), {_tot:.1f}s of singing with every face "
                      f"closed (rules.md#casting). A dropped word, syllable or line -- go and listen:")
                for s, e in _gaps[:8]:
                    print(f"        LISTEN: {mmss(s/1000)}-{mmss(e/1000)}  {(e-s)/1000:.1f}s")
            # ---- check 12b: A MOUTH WITH NO VOICE -- check 12's mirror. The owner 2026-10-08, Thriller: the cut's timing tracks were
            # not fixed: at 1:44 the audio says "come on" while the mouths still sing the chorus line.
            # The source alignment had laid chorus 2's sheet line over its ad-libs; the cut carried it across join 1: two
            # "a"s in the join's silence and "tonight" held 1.6 s on a dead-flat 139 Hz synth note (10-07: 166 Hz, "Hee hee").
            # Every WORD on a track that drives a face: >= 70 % of it below -40 dB in the vocals stem = sung into silence;
            # a word >= 0.4 s whose pitch is flat (std < 1.5 Hz over >= 20 voiced frames) = an instrument, not a voice.
            _ftr = {m_.group(1) for _q in r.find("ElementEffects").iter("Effect") if _q.get("name") == "Faces"
                    and (_q.get("ref") or "").isdigit() and int(_q.get("ref")) < len(_db)
                    for m_ in [re.search(r"E_CHOICE_Faces_TimingTrack=([^,]+)", _db[int(_q.get("ref"))])] if m_}
            _fh, _hh = int(0.04 * sr), int(0.01 * sr)
            _sus = []
            for _n in sorted(_ftr):
                _ls = sorted(tracks.get(_n, []), key=len)
                if len(_ls) < 3: continue
                for s, e, w_ in _ls[1]:
                    if (w_ or "").strip().lower() in ("", "rest"): continue
                    seg = y[int(s * sr / 1000):max(int(e * sr / 1000), int(s * sr / 1000) + _fh + 1)]
                    fr_ = _np.array([_np.sqrt((seg[i:i + _fh] ** 2).mean()) for i in range(0, max(1, len(seg) - _fh), _hh)])
                    quiet = float((20 * _np.log10(fr_ + 1e-6) < -40).mean()) if len(fr_) else 1.0
                    why = f"silent {quiet * 100:.0f}%" if quiet >= 0.7 else None
                    if not why and e - s >= 400:
                        f0_, _, _ = _lr.pyin(_lr.resample(seg.astype(_np.float32), orig_sr=sr, target_sr=16000),
                                             fmin=70, fmax=900, sr=16000, frame_length=1024, hop_length=160)
                        fv = f0_[~_np.isnan(f0_)]
                        if len(fv) >= 20 and _np.std(fv) < 1.5: why = f"FLAT {_np.median(fv):.0f} Hz (instrument bleed)"
                    if why: _sus.append((_n, w_, s, e, why))
            if _sus:
                print(f"WARN  {len(_sus)} word(s) with a mouth and NO VOICE under it (sung into silence, or on a flat "
                      f"instrument note) -- go and listen (a cut carries the source's alignment):")
                for _n, w_, s, e, why in _sus[:10]:
                    print(f"        LISTEN: {mmss(s/1000)}-{mmss(e/1000)}  {w_!r:<12} {why:<32} {_n}")
            else:
                print(f"ok    every word on the {len(_ftr)} face track(s) has a voice under it")
        except ImportError as ex:
            print(f"WARN  lip-sync vs audio DID NOT RUN -- {ex}")

    # ---- check 17: MUDDY GRADIENTS. A colour curve whose two adjacent stops are both saturated and far apart in hue
    #    blends through a colour nobody chose: red->green = olive #7f7f00, yellow->blue / gold->navy = grey. The owner 10-02
    #    (rules.md#colour): olive beside red reads as a Christmas tree. Idea + the midpoint test from nod/skill-xlights'
    #    color_check.py (read 2026-11-01), refined on the owner's own 50 files (journal #mud-gradient): the owner's Christmas files blend
    #    green->blue and red->blue for minutes on purpose, and a clean dim teal or purple is not mud -- only a GREY
    #    midpoint (s < .35) or an OLIVE/BROWN one (hue 30-100 deg, v < .7) counts. WARN, never FAIL: the show's own files carry
    #    these (Pentatonix red->green 20 min, the Tune To sign yellow->blue in three songs); the render is the judge.
    #    Not covered: effects that blend ADJACENT PALETTE colours themselves (Spirals/Fan blend, Butterfly) -- render only.
    try:
        _cp = r.find("ColorPalettes")
        _pals = [p.text or "" for p in _cp] if _cp is not None else []
        _hexs = re.compile(r"x=[0-9.]+\^c=(#[0-9a-fA-F]{6})")
        def _hsv(h): return colorsys.rgb_to_hsv(*(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)))
        def _mud(pal):
            out = []
            for f_ in pal.split(","):
                if not f_.startswith("C_BUTTON_Palette") or "Values=" not in f_: continue
                cols = _hexs.findall(f_)
                for a, b in zip(cols, cols[1:]):
                    (ha, sa, va), (hb, sb, vb) = _hsv(a), _hsv(b)
                    if min(sa, sb) < .5 or min(va, vb) < .5: continue          # a fade to dark / to white is not mud
                    gap = abs(ha - hb) * 360
                    if min(gap, 360 - gap) < 60: continue                     # a blend inside one colour family is fine
                    m = "#%02x%02x%02x" % tuple((int(a[i:i + 2], 16) + int(b[i:i + 2], 16)) // 2 for i in (1, 3, 5))
                    hm, sm, vm = _hsv(m)
                    kind = "grey" if sm < .35 else ("olive" if 30 <= hm * 360 <= 100 and vm < .7 else None)
                    if kind: out.append((a, b, m, kind))
            return out
        _mudpal = {i: _mud(p) for i, p in enumerate(_pals) if "Values=" in p}
        _mudpal = {i: v for i, v in _mudpal.items() if v}
        _curves, _hits = set(), {}                                             # (element, effect, pair) -> [secs, first ms, n]
        for _el in r.find("ElementEffects").iter("Element"):
            if _el.get("type") != "model": continue
            for _e in _el.iter("Effect"):
                p = _e.get("palette")
                if p is None or not p.isdigit() or int(p) >= len(_pals): continue
                if "Values=" in _pals[int(p)]: _curves.add(int(p))
                if int(p) not in _mudpal: continue
                s, t = int(_e.get("startTime")), int(_e.get("endTime"))
                h_ = _hits.setdefault((_el.get("name"), _e.get("name"), _mudpal[int(p)][0]), [0.0, s, 0])
                h_[0] += (t - s) / 1000; h_[1] = min(h_[1], s); h_[2] += 1
        if _hits:
            _n, _tot = sum(v[2] for v in _hits.values()), sum(v[0] for v in _hits.values())
            print(f"WARN  {_n} effect(s), {_tot:.0f}s lit, on a MUDDY gradient -- two saturated colours whose midpoint is grey "
                  f"or olive (rules.md#colour; the owner 10-02: olive beside red is a Christmas tree). Look at the render:")
            for (el_, nm_, (a, b, m, kind)), (d, s0, _) in sorted(_hits.items(), key=lambda kv: -kv[1][0])[:6]:
                print(f"        {d:6.1f}s  {el_[:28]:<28} {nm_:<12} {a}->{b}  mid {m} ({kind})  first at {mmss(s0 / 1000)}")
        else:
            print(f"ok    no muddy gradients ({len(_curves)} colour curve(s) in use)")
    except Exception as ex:
        print(f"WARN  muddy-gradient check DID NOT RUN -- {ex}")

    print(("FAILED" if fail else "PASSED") + f"  {xsq.name}")
    return 1 if fail else 0

sys.exit(main())
