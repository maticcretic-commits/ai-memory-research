"""sentinel - P-wave early-warning weak-signal sensing (instinct 1).

The honest kernel of "cats sense earthquakes": not prediction, but the
earliest detectable weak signal, scored prospectively. Streaming
statistics over the ears' intake: gate rejection bursts, contradiction
arrivals, retrieval-access gaps, lane-activity gaps. Each channel keeps
a rolling baseline; a deviation beyond a declared threshold fires a
SENTINEL ALERT into the mind's queue.

Prospective scoring: every alert is logged with its outcome (real event
/ false alarm) and the sentinel's precision is tracked like calibration
- an instinct that cries wolf gets its threshold raised by measurement,
not by vibes. A channel whose precision falls under the floor (with
enough samples) is MUTED and reported, never left screaming.

Rule-based, zero LLM. Fast and cheap - the reflex path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --- channel registry (declared, not discovered) ----------------------------

# Each channel: (window_s, threshold_k) - k = deviations above baseline.
CHANNELS = {
    # bursts of gate rejections = the P-wave of a poisoning attempt.
    # Red-Team Round 1 (class A7i): deviation-only sensing is blind
    # to a SUSTAINED attack - 30 consecutive rejection samples fired
    # zero alerts because a constant stream has no deviation. The
    # level guard fires once when value stays above level_ceiling
    # for level_min_run consecutive samples.
    "gate_rejection_rate": {"window_s": 3600.0, "threshold_k": 2.0,
                            "level_ceiling": 0.5, "level_min_run": 5},
    # queued writes piling up = the gate is unsure about something systemic
    "gate_queue_rate": {"window_s": 3600.0, "threshold_k": 2.0},
    # declared contradictions arriving fast = a conflict forming
    "contradiction_arrival_rate": {"window_s": 3600.0, "threshold_k": 2.0},
    # a record going quiet for long = retrieval misses or a stalled lane
    "access_gap_s": {"window_s": 86400.0, "threshold_k": 2.0},
    # Red-Team Round 5: a canary record was read through a
    # reader-facing path (mm/canary.py) - extraction sampling
    # the store. Value is 1.0 per trip; the level guard fires
    # on a sustained run of trips.
    "canary_trip": {"window_s": 3600.0, "threshold_k": 2.0,
                    "level_ceiling": 0.5, "level_min_run": 3},
    # Red-Team Round 5: one source identity's share of
    # surfaced retrievals (mm/circuit_breaker.py), observed
    # by deployments that feed it; the level guard fires when
    # the share stays pinned above the ceiling.
    "retrieval_share": {"window_s": 3600.0, "threshold_k": 2.0,
                        "level_ceiling": 0.5, "level_min_run": 3},
}

# Precision floor: a channel at or below this with >= MIN_ALERTS samples
# is muted until a human/agent re-arms it.
PRECISION_FLOOR = 0.25
MIN_ALERTS = 10


@dataclass
class SentinelAlert:
    """One fired alert. outcome: None=unjudged, True=real, False=false.
    judge: who/what judged it - a verified outcome source (drill,
    confirmed incident) or nitesh, never the channel itself."""
    id: int
    channel: str
    at: float
    value: float
    baseline_mean: float
    baseline_std: float
    detail: str = ""
    outcome: bool | None = None
    judge: str = ""


@dataclass
class _ChannelState:
    samples: list[tuple[float, float]] = field(default_factory=list)  # (at, value)
    alerts: list[SentinelAlert] = field(default_factory=list)
    muted: bool = False
    muted_reason: str = ""
    above_run: int = 0  # consecutive samples above the level ceiling


class Sentinel:
    """The instinct under the mind. Cheap, always-on, fail-quiet."""

    def __init__(self, channels: dict | None = None,
                 judge_allowlist: set[str] | None = None) -> None:
        spec = channels or CHANNELS
        self._spec = spec
        self._state: dict[str, _ChannelState] = {
            name: _ChannelState() for name in spec
        }
        self._next_id = 1
        # Red-Team Round 2 (class A7ii fix, corpus 3365): when the
        # deployment wires a judge allowlist, mark_outcome refuses
        # judgments from any identity not on it - in Round 1, ANY
        # non-empty judge string ("mallory-controlled-process")
        # marked 10 false outcomes and muted a channel. None = not
        # wired (legacy behaviour); wiring the list is the
        # deployment's responsibility, exactly like judge identity
        # itself: authenticity is a deployment trust boundary.
        self._judge_allowlist = (set(judge_allowlist)
                                 if judge_allowlist is not None
                                 else None)

    # -- feeding -----------------------------------------------------------

    def observe(self, channel: str, value: float, at: float,
                detail: str = "") -> SentinelAlert | None:
        """Feed one sample. Returns an alert if the threshold trips."""
        if channel not in self._state:
            raise KeyError(f"unknown sentinel channel {channel!r}")
        st = self._state[channel]
        cfg = self._spec[channel]
        st.samples.append((at, value))
        # drop samples outside the rolling window
        window = cfg["window_s"]
        st.samples = [(t, v) for t, v in st.samples if at - t <= window]
        ceiling = cfg.get("level_ceiling")
        if ceiling is not None:
            st.above_run = st.above_run + 1 if value > ceiling else 0
        if st.muted or len(st.samples) < 2:
            return None
        mean = sum(v for _, v in st.samples) / len(st.samples)
        var = sum((v - mean) ** 2 for _, v in st.samples) / len(st.samples)
        std = math.sqrt(var)
        if std != 0:
            k = (value - mean) / std
            if k >= cfg["threshold_k"]:
                alert = SentinelAlert(
                    id=self._next_id, channel=channel, at=at, value=value,
                    baseline_mean=mean, baseline_std=std, detail=detail)
                self._next_id += 1
                st.alerts.append(alert)
                self._retune(channel)
                return alert
        # Level guard (Red-Team Round 1): no deviation does not mean
        # no attack - a value pinned above the ceiling for a full run
        # of samples is a sustained event. Fires once, at the crossing.
        if ceiling is not None and st.above_run == cfg.get(
                "level_min_run", 5):
            alert = SentinelAlert(
                id=self._next_id, channel=channel, at=at, value=value,
                baseline_mean=mean, baseline_std=std,
                detail=(detail + " [sustained level above ceiling "
                        f"{ceiling} for {st.above_run} samples]").strip())
            self._next_id += 1
            st.alerts.append(alert)
            self._retune(channel)
            return alert
        return None

    # -- prospective scoring -------------------------------------------------

    def mark_outcome(self, alert_id: int, was_real: bool,
                     judge: str = "") -> bool:
        """Judge one alert: real event or false alarm. Finding 8
        (ChatGPT review): judgments must come from verified outcomes
        (drills, confirmed incidents) or nitesh - never self-certified
        by the channel. The judge is recorded on the alert, so the
        trail is auditable. False = unknown id, or (Red-Team Round 2)
        a judge outside the deployment-wired allowlist: the judgment
        is refused and nothing is recorded, so a forged judge string
        can no longer mute a channel by marking its alerts false."""
        if (self._judge_allowlist is not None
                and judge not in self._judge_allowlist):
            return False
        for st in self._state.values():
            for a in st.alerts:
                if a.id == alert_id:
                    a.outcome = bool(was_real)
                    a.judge = judge
                    self._retune(a.channel)
                    return True
        return False

    def precision(self, channel: str) -> float | None:
        """Prospective precision of a channel, or None below MIN_ALERTS."""
        judged = [a for a in self._state[channel].alerts
                  if a.outcome is not None]
        if len(judged) < MIN_ALERTS:
            return None
        return sum(1 for a in judged if a.outcome) / len(judged)

    def _retune(self, channel: str) -> None:
        """Mute a wolf-crying channel by measurement. Re-arm is explicit."""
        p = self.precision(channel)
        if p is not None and p <= PRECISION_FLOOR:
            st = self._state[channel]
            if not st.muted:
                st.muted = True
                st.muted_reason = (
                    f"precision {p:.2f} <= floor {PRECISION_FLOOR} "
                    f"after {MIN_ALERTS} judged alerts")

    def rearm(self, channel: str) -> bool:
        """Re-arm a muted channel. False = unknown channel."""
        if channel not in self._state:
            return False
        st = self._state[channel]
        st.muted = False
        st.muted_reason = ""
        return True

    def status(self) -> dict:
        """Every channel: samples, alerts, precision, mute state."""
        return {
            name: {
                "samples": len(st.samples),
                "alerts": len(st.alerts),
                "precision": self.precision(name),
                "muted": st.muted,
                "muted_reason": st.muted_reason,
            }
            for name, st in self._state.items()
        }
