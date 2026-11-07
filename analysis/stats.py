"""Small exact statistics for run-level rates (standard library only). MEASUREMENT.md §3.

- wilson:     95% Wilson score interval for k/n.
- boschloo:   Boschloo's exact unconditional test for two binomial proportions (as Knecht et al.).
- holm:       Holm step-down adjustment of a family of p-values.
- cmh:        Cochran-Mantel-Haenszel test across strata (save points), with continuity correction.
- cohen_kappa: agreement between two reviewers' labels.
"""

from __future__ import annotations

import math
from collections import Counter


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def _hyper_upper(a: int, n1: int, n2: int, s: int) -> float:
    """P(X >= a) for X ~ hypergeometric: s successes in total, n1 drawn as sample 1."""
    lo, hi = max(0, s - n2), min(n1, s)
    den = math.comb(n1 + n2, s)
    return sum(math.comb(n1, x) * math.comb(n2, s - x) for x in range(max(a, lo), hi + 1)) / den


def _boschloo_greater(k1: int, n1: int, k2: int, n2: int, grid: int = 400) -> float:
    """One-sided H1: p1 > p2. Statistic = Fisher's one-sided p-value; maximise the size over the
    nuisance parameter (common success probability)."""
    t_obs = _hyper_upper(k1, n1, n2, k1 + k2)
    tol = t_obs * 1e-9 + 1e-15
    region = [(a, b) for a in range(n1 + 1) for b in range(n2 + 1)
              if _hyper_upper(a, n1, n2, a + b) <= t_obs + tol]
    c1 = [math.comb(n1, a) for a in range(n1 + 1)]
    c2 = [math.comb(n2, b) for b in range(n2 + 1)]

    def size(pi: float) -> float:
        if pi <= 0.0 or pi >= 1.0:
            return sum(1.0 for a, b in region if (a + b == 0 if pi <= 0 else a + b == n1 + n2))
        lp, lq = math.log(pi), math.log1p(-pi)
        return sum(c1[a] * c2[b] * math.exp((a + b) * lp + (n1 + n2 - a - b) * lq) for a, b in region)

    xs = [(i + 0.5) / grid for i in range(grid)]
    vals = [size(x) for x in xs]
    best = max(range(grid), key=vals.__getitem__)
    # refine around the best grid point (golden-section search on the bracket)
    lo, hi = xs[max(best - 1, 0)], xs[min(best + 1, grid - 1)]
    g = (math.sqrt(5) - 1) / 2
    for _ in range(40):
        m1, m2 = hi - g * (hi - lo), lo + g * (hi - lo)
        if size(m1) < size(m2):
            lo = m1
        else:
            hi = m2
    return min(1.0, max(vals[best], size((lo + hi) / 2), size(0.0), size(1.0)))


def boschloo(k1: int, n1: int, k2: int, n2: int, alternative: str = "two-sided") -> float:
    """Boschloo's exact test. alternative: 'greater' (p1 > p2), 'less', or 'two-sided'
    (twice the smaller one-sided p, capped at 1, as scipy.stats.boschloo_exact does)."""
    if n1 == 0 or n2 == 0:
        return float("nan")
    if alternative == "greater":
        return _boschloo_greater(k1, n1, k2, n2)
    if alternative == "less":
        return _boschloo_greater(k2, n2, k1, n1)
    return min(1.0, 2 * min(_boschloo_greater(k1, n1, k2, n2), _boschloo_greater(k2, n2, k1, n1)))


def holm(pvals: list[float]) -> list[float]:
    """Holm-adjusted p-values, same order as the input. NaNs are passed through and not counted."""
    idx = [i for i, p in enumerate(pvals) if not math.isnan(p)]
    m = len(idx)
    out = list(pvals)
    running = 0.0
    for rank, i in enumerate(sorted(idx, key=lambda i: pvals[i])):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        out[i] = running
    return out


def cmh(strata: list[tuple[int, int, int, int]]) -> float:
    """CMH test of a common association across strata. Each stratum is (k1, n1, k2, n2).
    Returns a two-sided p-value (1 df, continuity-corrected), or NaN if no stratum is informative."""
    num, var = 0.0, 0.0
    for k1, n1, k2, n2 in strata:
        n = n1 + n2
        s = k1 + k2
        if n < 2 or s == 0 or s == n:
            continue
        num += k1 - n1 * s / n
        var += n1 * n2 * s * (n - s) / (n * n * (n - 1))
    if var == 0:
        return float("nan")
    chi = (max(abs(num) - 0.5, 0.0)) ** 2 / var
    return math.erfc(math.sqrt(chi / 2))


def cohen_kappa(a: list[str], b: list[str]) -> float:
    pairs = [(x, y) for x, y in zip(a, b) if x and y]
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in pairs) / n
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
