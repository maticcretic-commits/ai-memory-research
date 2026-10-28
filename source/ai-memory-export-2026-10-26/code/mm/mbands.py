"""mbands - M-band machinery: preregistered bands + per-band normalization.

Phase-3 (2026-10-20, chunk 2). Centralizes everything the codebase does
with M bands so calibration, confidence, and evals share one definition:

- BANDS: the preregistered band boundaries (gate (d) preregistration).
  M=0 -> "none"; (0, 0.50] -> "low"; (0.50, 0.70] -> "medium";
  (0.70, 1] -> "high".
- band_for(m): deterministic band assignment (boundary-inclusive on the
  upper edge, matching the preregistered intervals).
- MIN_SAMPLES = 30: bands with fewer than 30 calibration samples borrow
  the M>0 pooled curve (declared fallback, per chunk-1 head decision).
- BandStats / band_normalize: per-band z-normalization of a score so
  bands are comparable for ranking (e.g. confidence built on top of M).
  Bands stay stakes-invariant (W11): M never carries stakes.

This module changes no measurement - mm.resolver still owns M itself.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# Preregistered band boundaries (gate (d)). Boundaries are UPPER-inclusive:
# (0, 0.50] means 0 < m <= 0.50.
BANDS: tuple[tuple[str, float, float], ...] = (
    ("none", 0.0, 0.0),
    ("low", 0.0, 0.50),
    ("medium", 0.50, 0.70),
    ("high", 0.70, 1.0),
)

# Minimum calibration samples per band before the band gets its own curve.
# Thin bands borrow the M>0 pooled curve (chunk-1 head decision, declared).
MIN_SAMPLES = 30


def band_for(m: float) -> str:
    """Assign a normalized M value to its preregistered band.

    Boundary-inclusive on the upper edge: m=0.50 -> "low", m=0.70 -> "medium".
    Values are clamped into [0, 1] first (M saturates below 1.0 by design).
    """
    m = max(0.0, min(1.0, m))
    if m == 0.0:
        return "none"
    for name, lo, hi in BANDS:
        if name == "none":
            continue
        if lo < m <= hi:
            return name
    return "high"  # unreachable after clamping, kept for totality


@dataclass
class BandStats:
    """Descriptive stats of one band's sample, for normalization."""

    band: str
    n: int = 0
    mean: float = 0.0
    std: float = 1.0
    borrowed: bool = False   # True when this band borrows the pooled curve
    borrowed_from: str = ""  # which band's curve was borrowed


def fit_band_stats(values_by_band: dict[str, list[float]]) -> dict[str, BandStats]:
    """Fit per-band mean/std for normalization, with the pooled fallback.

    Bands with n < MIN_SAMPLES borrow the M>0 pooled (low+medium+high)
    stats; the borrow is declared on the returned BandStats so no caller
    can mistake a borrowed curve for a fitted one.
    """
    pooled: list[float] = []
    for name, _, _ in BANDS:
        if name != "none":
            pooled.extend(values_by_band.get(name, []))

    out: dict[str, BandStats] = {}
    pooled_stats = _stats("pooled-m>0", pooled, borrowed=False)
    for name, _, _ in BANDS:
        vals = values_by_band.get(name, [])
        if name == "none" or len(vals) >= MIN_SAMPLES:
            out[name] = _stats(name, vals, borrowed=False)
        else:
            out[name] = BandStats(
                band=name,
                n=len(vals),
                mean=pooled_stats.mean,
                std=pooled_stats.std,
                borrowed=True,
                borrowed_from="pooled-m>0",
            )
    return out


def _stats(name: str, vals: list[float], borrowed: bool) -> BandStats:
    n = len(vals)
    if n == 0:
        return BandStats(band=name, n=0, mean=0.0, std=1.0, borrowed=borrowed)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / n
    return BandStats(band=name, n=n, mean=mean,
                     std=math.sqrt(var) if var > 0 else 1.0,
                     borrowed=borrowed)


def band_normalize(value: float, m: float, stats: dict[str, BandStats]) -> float:
    """Z-normalize `value` against its M band's stats: (v - mean) / std.

    Makes a score comparable across bands (a "high" in the high-conflict
    band means the same relative standing as a "high" in the no-conflict
    band). Bands with borrowed curves use the pooled stats - declared on
    BandStats.borrowed, never silent.
    """
    band = band_for(m)
    st = stats.get(band)
    if st is None or st.n == 0:
        return value  # no stats at all: pass through unchanged, no invention
    return (value - st.mean) / st.std


def band_curve_source(band: str, stats: dict[str, BandStats]) -> str:
    """Human-readable declaration of which curve a band uses (audit aid)."""
    st = stats.get(band)
    if st is None:
        return f"{band}: no stats"
    if st.borrowed:
        return f"{band}: BORROWED from {st.borrowed_from} (n={st.n} < {MIN_SAMPLES})"
    return f"{band}: fitted (n={st.n})"
