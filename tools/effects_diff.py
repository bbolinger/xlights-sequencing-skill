#!/usr/bin/env python3
"""effects_diff.py <A.xsq> <B.xsq> -- re-baseline after an xLights save: compare two sequences by CONTENT.

Effects are matched on (element, effect name, start frame, end frame) at 25 ms, never by raw string -- an
xLights Save rewrites the whole file (CLAUDE.md SAFETY). Prints how many effects are only in A, only in B,
common, and the rows that differ. A clean re-baseline after a save is "only in A: 0  only in B: 0".
Also used 2026-10-05 to compare a song against last year's show copy (journal #right-templates).
"""
import collections
import sys

from lxml import etree


def effects(path):
    r = etree.parse(path).getroot()
    c = collections.Counter()
    for el in r.find("ElementEffects").findall("Element"):
        if el.get("type") != "model":
            continue
        for e in el.iter("Effect"):
            c[(el.get("name"), e.get("name"), int(e.get("startTime")) // 25, int(e.get("endTime")) // 25)] += 1
    return c, r.find("head").findtext("mediaFile")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, ma = effects(sys.argv[1])
    b, mb = effects(sys.argv[2])
    if ma != mb:
        print("A media:", ma); print("B media:", mb)
    print("only in A:", sum((a - b).values()), " only in B:", sum((b - a).values()), " common:", sum((a & b).values()))
    for label, d in (("only in B, by row:", b - a), ("only in A, by row:", a - b)):
        rows = collections.Counter(k[0] for k in d.elements())
        if rows:
            print(label, rows.most_common(12))


if __name__ == "__main__":
    main()
