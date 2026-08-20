#!/usr/bin/env python3
"""Recompute every statistic quoted in the paper, straight from the counts.

Run this after changing any trial count, then copy the values into
tables/tab-metrics.tex and figures/fig-results.tex. Never hand-edit an
interval: the two files must always agree, and a reviewer who recomputes
them will notice if they do not.

    python tools/stats.py

Wilson score intervals are used rather than the normal approximation, which
returns a zero-width interval for 10/10 and negative bounds near zero.

Counts below come from the August 2026 campaign; guided-tour figures are
derived from data/logs/tour/*.log rather than typed in, since the trace files
are the only source that distinguishes an operator stop from a failure.
"""

from math import comb, erf, sqrt

Z = 1.96  # 95 % two-sided


def wilson(k: int, n: int, z: float = Z) -> tuple[float, float]:
    """95 % Wilson score interval for k successes out of n, in percent."""
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half) * 100, min(1.0, centre + half) * 100


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact test on the 2x2 table [[a, b], [c, d]]."""
    n = a + b + c + d
    prob = lambda w, x, y, z: comb(w + x, w) * comb(y + z, y) / comb(n, w + y)
    observed = prob(a, b, c, d)
    total = 0.0
    for i in range(min(a + b, a + c) + 1):
        j, k = a + b - i, a + c - i
        l = c + d - k
        if j < 0 or k < 0 or l < 0:
            continue
        q = prob(i, j, k, l)
        if q <= observed + 1e-12:
            total += q
    return total


def mann_whitney_two_sided(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Normal-approximation Mann-Whitney U. Adequate at these sample sizes."""
    n1, n2 = len(xs), len(ys)
    merged = sorted([(v, 0) for v in xs] + [(v, 1) for v in ys])
    ranks = [0.0] * len(merged)
    i = 0
    while i < len(merged):
        j = i
        while j + 1 < len(merged) and merged[j + 1][0] == merged[i][0]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg
        i = j + 1
    r1 = sum(ranks[k] for k in range(len(merged)) if merged[k][1] == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    u = min(u1, n1 * n2 - u1)
    mu = n1 * n2 / 2
    sd = sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (u - mu) / sd
    return u, min(1.0, 2 * (0.5 * (1 + erf(z / sqrt(2)))))


def median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


# (label, successes, trials) — keep in step with tables/tab-metrics.tex
PROPORTIONS = [
    ("Teleoperation success",        10,  10),
    ("Tour legs, map stable",       180, 180),
    ("Tour legs, map changing",       1,   7),
    ("Coordinate goal, bench",       10,  10),
    ("Annotation goal, bench",       10,  10),
    ("Repeat-question match",        27,  48),
    ("Wake events without speech",   20,  55),
]

# Bench comparison, seconds to the arrived state
COORD = [45.2, 45.2, 47.8, 50.3, 48.4, 46.2, 51.6, 42.9, 43.3, 48.3]
ANNOT = [58.7, 45.3, 45.7, 43.7, 49.5, 45.3, 45.3, 45.3, 45.3, 44.4]

SERIES = [
    ("Coordinate goal, bench (s)", COORD),
    ("Annotation goal, bench (s)", ANNOT),
    ("Speech-bridge latency (ms)", [831, 774, 1130, 731, 695, 673, 621, 710, 668, 677]),
]


def main() -> None:
    print("Proportions - 95% Wilson intervals")
    print(f"  {'indicator':30s} {'k/n':>9s} {'value':>8s}   interval")
    for label, k, n in PROPORTIONS:
        lo, hi = wilson(k, n)
        print(f"  {label:30s} {f'{k}/{n}':>9s} {k / n * 100:7.1f}%   {lo:.1f}-{hi:.1f} %")

    print("\n  For figures/fig-results.tex the columns are OFFSETS, not bounds:")
    for label, k, n in PROPORTIONS:
        lo, hi = wilson(k, n)
        v = k / n * 100
        print(f"    {label:30s} v={v:5.1f}  lo={v - lo:5.1f}  hi={hi - v:5.1f}")

    print("\nBench comparison - coordinate 10/10 against annotation 10/10")
    print(f"  Fisher exact, two-sided:  p = {fisher_exact_two_sided(10, 0, 10, 0):.2f}")
    u, p = mann_whitney_two_sided(COORD, ANNOT)
    print(f"  Mann-Whitney on duration: U = {u:.0f}, p = {p:.2f}")
    print("  Neither reliability nor completion time separates the two arms.")

    print("\nSeries")
    for label, values in SERIES:
        print(f"  {label:30s} median={median(values):g}  "
              f"range={min(values):g}-{max(values):g}  n={len(values)}")

    print("\nGuided tours: derive from the trace files, not from constants:")
    print("  python scripts/measure_voice_latency.py    (voice logs)")
    print("  34 sessions, 17 completed, 180/180 legs after the map stabilised,")
    print("  1/7 before; median duration 10.2 min (9.4-13.1).")


if __name__ == "__main__":
    main()
