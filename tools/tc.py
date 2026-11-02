"""Timecode formatting. A show is read in MINUTES AND SECONDS, never raw seconds.

The owner, 2026-09-07: *say it in minutes and seconds; timelines do not work in seconds alone*. The owner reads the sequencer on a mm:ss ruler, so 179.7 means nothing and
2:59.7 means the end of the finale build. Every tool that prints a time uses this.

    mmss(179.7)          -> '2:59.7'
    mmss(179.7, dp=0)    -> '3:00'
    span(163.78, 164.92) -> '2:43.8-2:44.9'
    mmss_ms(92400)       -> '1:32.4'
"""
from __future__ import annotations


def mmss(t, dp: int = 1) -> str:
    """Seconds -> 'M:SS.d'. Negative times keep their sign."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return str(t)
    sign = "-" if t < 0 else ""
    t = abs(t)
    m = int(t // 60)
    s = t - m * 60
    if dp <= 0:
        s = int(round(s))
        if s == 60:                      # 2:59.6 -> 3:00, not 2:60
            m, s = m + 1, 0
        return f"{sign}{m}:{s:02d}"
    s_str = f"{s:0{3 + dp}.{dp}f}"
    if float(s_str) >= 60.0:             # rounding carried into the next minute
        m, s_str = m + 1, f"{0:0{3 + dp}.{dp}f}"
    return f"{sign}{m}:{s_str}"


def mmss_ms(ms, dp: int = 1) -> str:
    """Milliseconds -> 'M:SS.d'."""
    try:
        return mmss(float(ms) / 1000.0, dp)
    except (TypeError, ValueError):
        return str(ms)


def span(a, b, dp: int = 1, ms: bool = False) -> str:
    """'M:SS.d-M:SS.d' for a start/end pair."""
    f = mmss_ms if ms else mmss
    return f"{f(a, dp)}-{f(b, dp)}"


def dur(seconds) -> str:
    """A LENGTH, not a position: '0.82s' under a minute, else 'M:SS'. A 500ms effect is
    500ms, not 0:00.5 -- durations and positions are different things and reading a short
    duration as a timecode is worse, not better."""
    try:
        t = float(seconds)
    except (TypeError, ValueError):
        return str(seconds)
    return f"{t:.2f}s" if abs(t) < 60 else mmss(t)
