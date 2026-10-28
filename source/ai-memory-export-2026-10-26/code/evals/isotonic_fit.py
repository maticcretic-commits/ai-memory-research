"""isotonic_fit - per-M-band isotonic calibration on REAL decision data.

Phase-3 re-scope (2026-10-20, chunk 2). Chunk 1 proved temperature scaling
is the wrong functional form for the conflict regime (conflict-band T hit
the grid ceiling 6.0; ECE 0.2482 vs <=0.10 target). This module implements
the re-scoped fix: isotonic regression per M band.

DATA CONTRACT (strict): fit ONLY on (stated_confidence, outcome) pairs
logged from REAL decisions - mm.confidence.CalibrationLog.record() output
("log (stated confidence, outcome) pairs from day one", ARCHITECTURE.md
?7.5). Synthetic bench tasks are NOT calibration data: chunk 1 showed
300 synthetic tasks are too thin and regime-shifted. Until real pairs
exist, `fit()` refuses (returns status "no-data") rather than fitting on
synthetic data and reporting a number.

Method: Pool-Adjacent-Violators Algorithm (PAVA) per band, pure Python
(no numpy/sklearn on this VM). Bands share mm.mbands definitions;
thin bands (< MIN_SAMPLES pairs) borrow the M>0 pooled isotonic curve -
declared on the result, never silent.

The fitted map is monotone non-decreasing: p_cal = f_band(p_raw).
Calibration is proper: isotonic regression minimizes Brier score among
all monotone maps, which directly addresses the gate-(b) full-vector
Brier concern when real data arrives.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from mm.mbands import MIN_SAMPLES, band_for


@dataclass
class IsotonicCurve:
    """One fitted monotone map: sorted x knots -> y values (non-decreasing)."""

    band: str
    xs: list[float] = field(default_factory=list)
    ys: list[float] = field(default_factory=list)
    n_pairs: int = 0
    borrowed: bool = False
    borrowed_from: str = ""

    def __call__(self, p: float) -> float:
        """Apply the isotonic map to a raw confidence."""
        if not self.xs:
            return p  # unfitted: identity, never invent
        p = max(0.0, min(1.0, p))
        # Piecewise-constant interpolation on the PAVA blocks.
        for x, y in zip(self.xs, self.ys):
            if p <= x:
                return y
        return self.ys[-1]


def _pava(xs: list[float], ys: list[float]) -> tuple[list[float], list[float]]:
    """Pool-Adjacent-Violators: isotonic (non-decreasing) regression.

    Returns (block_right_edges, block_means). Pure Python.
    """
    # Sort by x; each point starts as its own block (sum, weight).
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    blocks: list[list[float]] = []  # [sum_y, weight, max_x]
    for i in order:
        blocks.append([ys[i], 1.0, xs[i]])
        # Merge while the previous block's mean exceeds this block's mean.
        while len(blocks) >= 2:
            m_prev = blocks[-2][0] / blocks[-2][1]
            m_cur = blocks[-1][0] / blocks[-1][1]
            if m_prev <= m_cur:
                break
            s = blocks[-2][0] + blocks[-1][0]
            w = blocks[-2][1] + blocks[-1][1]
            x = max(blocks[-2][2], blocks[-1][2])
            blocks[-2:] = [[s, w, x]]
    return ([b[2] for b in blocks], [b[0] / b[1] for b in blocks])


@dataclass
class IsotonicCalibrator:
    """Per-M-band isotonic calibration, fit on real decision pairs."""

    curves: dict[str, IsotonicCurve] = field(default_factory=dict)
    status: str = "no-data"

    def fit(self, pairs: list[tuple[float, bool, float]],
            source: str) -> "IsotonicCalibrator":
        """Fit per-band isotonic maps.

        pairs: (stated_confidence, outcome, m) from REAL decisions.
        HD-2 (head decision 2026-10-20): the source parameter is
        enforced in code. The caller must declare source="real-decisions";
        anything else raises. No synthetic data in calibration - the
        real-data-only contract is mechanical, not policy-only. (A source
        tag is a declaration, not a proof of provenance: it stops
        accidental misuse, not determined misuse. Production callers pass
        only mm.confidence.CalibrationLog triples from real decisions.)
        """
        if source != "real-decisions":
            raise ValueError(
                f"isotonic fit refused: source={source!r} - calibration "
                "accepts only source='real-decisions' (HD-2: no synthetic "
                "data in calibration)")
        for p, o, m in pairs:
            if not (0.0 <= p <= 1.0):
                raise ValueError(f"confidence {p} outside [0,1]")
            if not isinstance(o, bool):
                raise ValueError("outcome must be bool (real decisions only)")
        if not pairs:
            self.status = "no-data"
            return self

        by_band: dict[str, list[tuple[float, float]]] = {}
        for p, o, m in pairs:
            by_band.setdefault(band_for(m), []).append((p, 1.0 if o else 0.0))

        # Pooled M>0 curve for thin bands (declared fallback).
        pooled = [pt for b, pts in by_band.items() if b != "none" for pt in pts]
        pooled_curve = self._fit_one("pooled-m>0", pooled, borrowed=False)

        self.curves = {}
        for band in ("none", "low", "medium", "high"):
            pts = by_band.get(band, [])
            if band == "none" or len(pts) >= MIN_SAMPLES:
                self.curves[band] = self._fit_one(band, pts, borrowed=False)
            else:
                c = IsotonicCurve(band=band, n_pairs=len(pts),
                                  borrowed=True, borrowed_from="pooled-m>0")
                c.xs, c.ys = pooled_curve.xs, pooled_curve.ys
                self.curves[band] = c
        self.status = "fitted"
        return self

    def _fit_one(self, band: str, pts: list[tuple[float, float]],
                 borrowed: bool) -> IsotonicCurve:
        c = IsotonicCurve(band=band, n_pairs=len(pts), borrowed=borrowed)
        if pts:
            xs = [p for p, _ in pts]
            ys = [y for _, y in pts]
            c.xs, c.ys = _pava(xs, ys)
        return c

    def calibrate(self, p: float, m: float) -> float:
        """Map a raw confidence through the band's isotonic curve."""
        if self.status != "fitted":
            return p  # no data: identity, never invent a correction
        return self.curves[band_for(m)](p)

    def report(self) -> dict:
        """Audit declaration: which bands are fitted vs borrowed."""
        return {
            band: {
                "n_pairs": c.n_pairs,
                "borrowed": c.borrowed,
                "borrowed_from": c.borrowed_from,
                "n_knots": len(c.xs),
            }
            for band, c in self.curves.items()
        } if self.status == "fitted" else {"status": self.status}


def brier_full_vector(probs: list[float], outcome_idx: int) -> float:
    """Proper full-vector Brier score (gate-(b) methodology fix).

    Gate-(b)'s Brier was computed on top-choice correctness only - not a
    proper scoring rule for the vector. This is the correct form:
    mean squared error over the full probability vector vs the one-hot
    outcome. Use it in the gate-(b) recompute with matched non-conflict
    controls (see calibration-rescope-phase3.md).
    """
    n = len(probs)
    if not (0 <= outcome_idx < n):
        raise ValueError("outcome_idx outside vector")
    if any(not (0.0 <= p <= 1.0) for p in probs):
        raise ValueError("probabilities outside [0,1]")
    return sum((p - (1.0 if i == outcome_idx else 0.0)) ** 2
               for i, p in enumerate(probs)) / n


def decompose_brier(probs: list[float], outcome_idx: int,
                    bins: int = 10) -> dict:
    """Decompose Brier into calibration vs refinement (Murphy decomposition).

    Locates the overconfidence source: the ?3b penalty kappaxMx(1-P) vs the
    ?3c bound raise. Fix the component, not the aggregate (design doc ?3).
    Single-vector version; the harness aggregates over the eval set.
    """
    # Reliability-in-the-small needs a population; here we return the
    # per-instance components and let the eval harness bin them.
    brier = brier_full_vector(probs, outcome_idx)
    top_p = max(probs)
    top_correct = (probs.index(top_p) == outcome_idx)
    return {
        "brier": round(brier, 4),
        "top_confidence": round(top_p, 4),
        "top_correct": top_correct,
        "overconfidence_gap": round(top_p - (1.0 if top_correct else 0.0), 4),
    }
