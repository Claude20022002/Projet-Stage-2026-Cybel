#!/usr/bin/env python3
"""Recompute every statistic quoted in the paper, straight from the counts.

Run this after changing any trial count, then copy the values into
tables/tab-metrics.tex and figures/fig-results.tex. Never hand-edit an
interval: the two files must always agree, and a reviewer who recomputes
them will notice if they do not.

    python tools/stats.py

Wilson score intervals are used rather than the normal approximation, which
returns a zero-width interval for 3/3 and negative bounds near zero.
"""

from math import comb, sqrt

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


# (label, successes, trials) — keep in step with tables/tab-metrics.tex
PROPORTIONS = [
    ("Teleoperation success", 10, 10),
    ("Guided tours completed", 3, 3),
    ("  individual legs", 30, 30),
    ("Coordinate goal, bench", 3, 3),
    ("Annotation goal, bare client", 0, 3),
    ("Repeat-question match", 27, 48),
]

# (label, values) — medians and ranges quoted in the text
SERIES = [
    ("Coordinate goal, bench (s)", [40.0, 40.9, 46.5]),
    ("Tour duration (s)", [667.6, 670.4, 822.3]),
]


def main() -> None:
    print("Proportions - 95% Wilson intervals")
    print(f"  {'indicator':30s} {'k/n':>8s} {'value':>8s}   interval")
    for label, k, n in PROPORTIONS:
        lo, hi = wilson(k, n)
        print(f"  {label:30s} {f'{k}/{n}':>8s} {k / n * 100:7.1f}%   "
              f"{lo:.1f}-{hi:.1f} %")

    print("\n  For figures/fig-results.tex the columns are OFFSETS, not bounds:")
    for label, k, n in PROPORTIONS:
        lo, hi = wilson(k, n)
        v = k / n * 100
        print(f"    {label.strip():30s} v={v:5.1f}  lo={v - lo:5.1f}  hi={hi - v:5.1f}")

    print("\nBench comparison - coordinate 3/3 against annotation 0/3")
    print(f"  Fisher exact, two-sided: p = {fisher_exact_two_sided(3, 0, 0, 3):.2f}")
    print("  Not significant at n = 3 per arm. The paper says so explicitly.")

    print("\nSeries")
    for label, values in SERIES:
        ordered = sorted(values)
        median = ordered[len(ordered) // 2] if len(ordered) % 2 else \
            (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2
        print(f"  {label:30s} median={median:g}  range={min(values):g}-{max(values):g}")


if __name__ == "__main__":
    main()
