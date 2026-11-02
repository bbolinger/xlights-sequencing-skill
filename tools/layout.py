"""layout.py -- the channel layout of a show, read from the show's own files. READ-ONLY.

`Layout(show_folder)` reads `xlights_rgbeffects.xml` + `xlights_networks.xml` and answers,
for every model: its absolute 1-based start channel, its channels per node (stride), and the
node list of each of its submodels; for every group, what it expands to.  This is what every
render reader needs before it can decode an `.fseq` at the right bytes (`snap.py`, and any
tool that samples a prop from a saved render):

    lay = Layout(Path("~/Documents/MyShow").expanduser())
    lay.start["Tombstone"]          -> 119428       absolute 1-based start channel
    lay.stride["Tombstone"]         -> 3            4 for an "RGBW Nodes" model
    lay.subnodes["Tombstone"]       -> {"eyes": [12, 13], ...}   1-based nodes per submodel
    lay.expand("ALL House")         -> {"Peaks", "Tombstone/eyes", ...}  the concrete leaves
    lay.bases                       -> {"ControllerA": 1, "ControllerB": 2560, ...}  controller bases

Two facts this encodes, both learned the hard way:

  * Controller bases come from THIS show's `xlights_networks.xml`, in definition order, never
    from a hardcoded table.  A constant table went silently wrong on 2026-09-30 when a
    controller lost a port and a prop was added (one base moved 25570 -> 25009) -- every render
    read through it would have decoded three props off by hundreds of channels and still
    looked plausible.
  * A `StartChannel` of the form `!Controller:offset` is controller-relative; the absolute
    channel is `base + offset - 1`.  A bare number is an xLights-assigned "No Controller"
    channel and is taken as is.  The byte index into a decoded frame is the absolute channel
    MINUS ONE -- `fseq.rgb()` does that subtraction; never do it twice.

Extracted 2026-11-01 from the full toolkit's eye-gating tool so that the render readers can
ship without it.  Behaviour is unchanged.
"""
from __future__ import annotations
import re
from pathlib import Path
from lxml import etree


def show_folder_of(p: Path) -> Path:
    """The show folder above `p`: the first parent holding `xlights_rgbeffects.xml`."""
    for d in [p, *p.parents]:
        if (d / "xlights_rgbeffects.xml").exists():
            return d
    raise SystemExit(f"no xlights_rgbeffects.xml above {p}")


def bases_from_network(show: Path) -> dict:
    """Controller name -> absolute 1-based base channel, from THIS show's xlights_networks.xml in
    definition order.  Never a hardcoded table: a constant `BASES` table went silently wrong on
    2026-09-30 when one controller lost a port and a prop was added (one base 25570 -> 25009) --
    every render read through it would have decoded three props off by hundreds."""
    bases, base = {}, 1
    for c in etree.parse(str(show / "xlights_networks.xml")).getroot().findall("Controller"):
        bases[c.get("Name")] = base
        base += sum(int(n.get("MaxChannels", "0")) for n in c.findall("network"))
    return bases


def _nodes(sm):
    """1-based node list of a <subModel>: every `lineN` attribute, ranges `a-b` expanded."""
    out = set()
    for k, v in sm.attrib.items():
        if not re.fullmatch(r"line\d+", k): continue
        for t in (v or "").split(","):
            t = t.strip()
            if not t: continue
            if "-" in t:
                a, b = t.split("-", 1)
                try: a, b = int(a), int(b)
                except ValueError: continue
                lo, hi = (a, b) if a <= b else (b, a); out.update(range(lo, hi + 1))
            else:
                try: out.add(int(t))
                except ValueError: pass
    return sorted(out)


class Layout:
    def __init__(self, show: Path):
        r = etree.parse(str(show / "xlights_rgbeffects.xml")).getroot()
        self.groups = {g.get("name"): [m.strip() for m in (g.get("models") or "").split(",") if m.strip()]
                       for g in r.iter("modelGroup")}
        self._cache = {}
        # absolute start channel (1-based) and per-submodel node lists, for reading renders
        self.bases = bases_from_network(show)
        self.start, self.subnodes, self.stride = {}, {}, {}
        for m in r.iter("model"):
            sc = m.get("StartChannel") or ""
            if sc.startswith("!") and ":" in sc:
                ctl, off = sc[1:].rsplit(":", 1)
                if ctl in self.bases and off.isdigit():
                    self.start[m.get("name")] = self.bases[ctl] + int(off) - 1
            elif sc.isdigit():                    # No Controller: xLights' own number (by name)
                self.start[m.get("name")] = int(sc)
            self.subnodes[m.get("name")] = {x.get("name"): _nodes(x) for x in m.findall("subModel")}
            # channels per node: an "RGBW Nodes" model is 4 per node, so a 3-stride read lands
            # on the wrong pixel from node 2 onward
            self.stride[m.get("name")] = 4 if "RGBW" in (m.get("StringType") or "") else 3

    def expand(self, name, seen=None):
        """Resolve a group (or model) to its concrete 'Model' / 'Model/Sub' leaves.
        Checking a group by NAME cannot tell you what it touches -- only expansion can.
        A group named like a section of roofline can, and did, contain three whole
        multiprops; nothing but expanding it shows that."""
        if name in self._cache: return self._cache[name]
        seen = seen or set()
        if name in seen: return set()
        seen = seen | {name}
        if name in self.groups:
            out = set()
            for m in self.groups[name]:
                out |= self.expand(m, seen)
        else:
            out = {name}
        if not seen - {name}: self._cache[name] = out
        return out
