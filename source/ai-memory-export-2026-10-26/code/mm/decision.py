"""decision — Soar preference cycle, reimplemented in LLM form.

v0.3 IMPLEMENTED (2026-10-14): the v0.2 cycle is now running code.
propose → inject_rejections (selvedge-style) → attach_preferences
(Soar better/worse/reject/prohibit vocabulary, lexicographic aggregation)
→ select (with tie / conflict / no-candidate impasse detection).

Aggregation rule (first cut, inspectable, tunable):
  1. `prohibit` / `reject` votes EXCLUDE a candidate (Soar semantics).
  2. Surviving candidates rank by net score: Σ(better weights) − Σ(worse weights);
     `indifferent` votes are logged, ignored in scoring.
  3. Top-two net scores within `tie_epsilon` → tie impasse (the DDM caution
     bound in mm.confidence is the finer-grained version of this same
     idea — impasse is where the coarse cycle defers to accumulation).
  4. `conflict_score >= conflict_threshold` → conflict impasse (escalate).
A human can overrule from the preference_log alone.

License: Soar is GitHub NOASSERTION vs README BSD claim — verify
LICENSE.md before any reuse. This reimplements the *cycle*, never copied
code. See DECISION.md for the end-to-end cycle and ARCHITECTURE.md §0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Candidate:
    """One proposed option entering the decision cycle."""

    id: str
    description: str
    action: str = ""                 # proposed action / tool call sketch
    source: str = ""                 # "planner" | "sop-fast-path" | "subgoal"


@dataclass
class Preference:
    """One preference vote on a candidate, in Soar's vocabulary."""

    candidate_id: str
    kind: str                        # better | worse | reject | prohibit | indifferent
    reason: str = ""
    source_module: str = ""          # e.g. "temporal", "constraints", "sop"
    weight: float = 1.0


@dataclass
class RejectedChoiceRecord:
    """selvedge-style entity-keyed record of a past rejection."""

    entity_key: str                  # what the decision was about
    rejected_approach: str
    rationale: str
    what_would_change_your_mind: str = ""


@dataclass
class Impasse:
    """No clear winner — deliberate via subgoal."""

    kind: str                        # tie | conflict | no-candidate
    candidate_ids: list[str] = field(default_factory=list)
    detail: str = ""
    suggested_subgoal: str = ""      # what the subgoal should go find/do


@dataclass
class Decision:
    """The outcome of one decision cycle."""

    selected_id: str | None          # None when impasse
    impasse: Impasse | None = None
    preference_log: list[Preference] = field(default_factory=list)
    excluded_ids: list[str] = field(default_factory=list)  # killed by reject/prohibit
    tie_broken: str | None = None    # "provenance" when a tie impasse was
                                     # resolved by the provenance tie-break
                                     # (density/provenance build, 2026-10-21)


# ---------------------------------------------------------------------------
# selvedge rejected-choice injection (propose-time)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _token_overlap(a: str, b: str) -> float:
    """Jaccard similarity over word tokens. 1.0 = identical wording."""
    ta = set(_normalize(a).split())
    tb = set(_normalize(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def inject_rejections(
    candidates: list[Candidate],
    records: list[RejectedChoiceRecord],
    *,
    fuzzy_threshold: float = 0.5,
) -> tuple[list[Candidate], list[str]]:
    """Prune/flag candidates matching rejected-choice records.

    Matching rule (first cut): entity-key equality (normalized) OR Jaccard
    token overlap between the record's rejected_approach and the
    candidate's action+description >= fuzzy_threshold.

    A matching candidate is PRUNED — unless the record names a
    what_would_change_your_mind condition, in which case it is kept and
    FLAGGED with the prior rationale (the condition may now hold).

    Returns (surviving candidates, prune log). The log names the record,
    the match type, and the rationale — everything a human needs to
    overrule a prune.
    """
    survivors: list[Candidate] = []
    log: list[str] = []
    for cand in candidates:
        cand_text = cand.action + " " + cand.description
        matched = None
        match_how = ""
        for rec in records:
            if _normalize(rec.entity_key) == _normalize(cand.id):
                matched, match_how = rec, "entity-key"
                break
            if _token_overlap(rec.rejected_approach, cand_text) >= fuzzy_threshold:
                matched, match_how = rec, "fuzzy"
                break
        if matched is None:
            survivors.append(cand)
            continue
        if matched.what_would_change_your_mind:
            survivors.append(cand)
            log.append(
                f"FLAGGED {cand.id} ({match_how}): previously rejected — "
                f"{matched.rationale} — but its change-condition may now "
                f"hold: {matched.what_would_change_your_mind}"
            )
        else:
            log.append(
                f"PRUNED {cand.id} ({match_how}): previously rejected — "
                f"{matched.rationale}"
            )
    return survivors, log


# ---------------------------------------------------------------------------
# Preference vote aggregation (Soar vocabulary)
# ---------------------------------------------------------------------------

_VALID_KINDS = {"better", "worse", "reject", "prohibit", "indifferent"}


def attach_preferences(
    candidates: list[Candidate],
    votes: list[Preference],
) -> tuple[list[tuple[str, float]], list[str], list[Preference]]:
    """Aggregate module preference votes into a candidate ranking.

    Returns (ranking, excluded, log):
    - ranking: [(candidate_id, net_score)] sorted descending. net_score =
      Σ(better weights) − Σ(worse weights).
    - excluded: candidate ids killed by prohibit/reject votes.
    - log: the full preference vote log (audit trail), including per-vote
      kind, source module, and reason.

    Lexicographic: prohibitions outrank scores — a prohibited candidate
    never wins no matter how many "better" votes it gathered. Candidates
    with no votes keep net 0.0 and stay eligible.
    """
    for v in votes:
        if v.kind not in _VALID_KINDS:
            raise ValueError(
                f"invalid preference kind {v.kind!r} on {v.candidate_id!r}; "
                f"expected one of {sorted(_VALID_KINDS)}"
            )
    by_id: dict[str, list[Preference]] = {}
    for v in votes:
        by_id.setdefault(v.candidate_id, []).append(v)

    excluded: list[str] = []
    ranking: list[tuple[str, float]] = []
    for cand in candidates:
        vs = by_id.get(cand.id, [])
        if any(v.kind in ("prohibit", "reject") for v in vs):
            excluded.append(cand.id)
            continue
        net = sum(v.weight for v in vs if v.kind == "better") - \
              sum(v.weight for v in vs if v.kind == "worse")
        ranking.append((cand.id, net))
    ranking.sort(key=lambda t: (-t[1], t[0]))
    return ranking, excluded, votes


# ---------------------------------------------------------------------------
# select: the Soar selection step + impasse taxonomy
# ---------------------------------------------------------------------------

def select(
    candidates: list[Candidate],
    preferences: list[Preference],
    time_budget_s: float = 30.0,
    *,
    tie_epsilon: float = 0.05,
    tie_epsilon_mode: str = "absolute",
    conflict_score: float = 0.0,
    conflict_threshold: float = 0.75,
    density_scale: bool = False,
    density_noise_gate: bool = False,
    density_noise_lo: float = 0.51,
    density_noise_hi: float = 0.80,
    tie_band_quality: bool = False,
    tie_band_lo: float = 0.6,
    tie_band_hi: float = 0.9,
    tie_band_widen: float = 1.25,
    tie_band_shrink: float = 0.8,
    tie_break_provenance: dict[str, float] | None = None,
    tie_break_margin: float = 0.15,
    tie_break_allowed: bool = False,
) -> Decision:
    """Select the preferred candidate; declare impasse when none wins.

    Impasse triggers:
    - no surviving candidates → "no-candidate" (subgoal: propose more, or
      relax whatever killed them).
    - conflict_score >= conflict_threshold → "conflict" (subgoal: escalate
      to agent/human with the conflict surfaced).
    - top two net scores within the effective tie epsilon → "tie"
      (subgoal: gather more evidence, then re-enter the cycle — this is
      where mm.confidence's DDM accumulation earns its keep).

    tie_epsilon_mode (next-steps item 1, 2026-10-20): "absolute" is the
    v0.3 rule - tie when the top-two margin is <= tie_epsilon, whatever
    the score scale. "relative" makes the epsilon margin-relative:
    eps_eff = tie_epsilon * |top net score|, so a tie means "within
    tie_epsilon FRACTION of the leader's score". The absolute band is
    scale-blind: when scores compress (e.g. confidences clustered near
    0.2-0.35 under a raised DDM bound), a fixed 0.05 band ties almost
    everything, while on large accumulated nets it is proportionally
    far stricter. Default stays "absolute" - the relative mode is
    opt-in until its validation (tie-lever-prereg.md) is read.

    time_budget_s is the coarse impasse lever from the spec: when the
    caller cannot afford more deliberation it passes a small budget and
    treats a "tie" impasse as an immediate escalation instead of a subgoal.
    (v0.3: budget is carried in the audit trail; the caller enforces it.)

    density_scale (density/provenance build, 2026-10-21; ChatGPT
    ruling DS-A): when True, the mode must be "relative" (anything
    else raises - the ruling defines density scaling as a multiplier
    on the relative epsilon, and a silent fallback would hide a
    misconfiguration) and eps_eff is divided by sqrt(d), where d is
    the mean scoring-vote count (kinds better/worse) over the top-two
    ranked candidates, floored at 1. At d = 1 the result is exactly
    the relative-mode epsilon. Default False: behaviour unchanged.

    density_noise_gate (DS-NG, next-lever build, 2026-10-21;
    ChatGPT ruling in next-lever-chatgpt-ruling.txt;
    preregistration next-lever-preregistration.md): when True,
    density_scale must also be True (anything else raises - no
    silent fallback), and the sqrt(d) shrinkage is scaled by a
    per-task gate g in [0, 1] driven by nu, the dispersion of
    the top-two candidates' scoring-vote log-weights (each
    candidate centred by its own mean log-weight, pooled;
    fewer than 4 pooled positive weights leaves nu undefined
    and g = 0). g = 1 at nu <= density_noise_lo (full DS-A),
    g = 0 at nu >= density_noise_hi (no shrinkage - the plain
    relative epsilon), linear between. The frozen thresholds
    (0.51 / 0.80) are the run-1-seed diagnostic's R0 median /
    p90; the diagnostic showed the statistic cannot identify
    jitter (R0/R1 distributions overlap), so the gate only
    withholds shrinkage from the highest-dispersion tasks.
    Default False: behaviour unchanged.

    Asymmetric tie band (TB-Q, 2026-10-21; ChatGPT ruling in
    asymmetric-tieband-chatgpt-ruling.txt; preregistration
    asymmetric-tieband-preregistration.md): when True, the FINAL
    eps_eff (after any density multiplier) is scaled by a per-task
    factor m(q) driven by q, the leader's share of top-two
    scoring-vote weight (kinds better/worse, weight > 0, no
    centring) - a BALANCE signal (how concentrated support is
    between the top two), not a complete measure of evidence
    quality. m(q) = tie_band_widen at q <= tie_band_lo (split
    support - the band widens, impasse protected), m(q) =
    tie_band_shrink at q >= tie_band_hi (one-sided support - the
    band shrinks, resolution sought), linear between. Degenerate
    inputs (fewer than two ranked candidates, or zero total
    top-two scoring weight) leave the band inert (m = 1.0), the
    fail-safe toward the adopted stack. Threshold validation:
    0.5 <= lo < hi <= 1.0, widen >= 1.0, 0 < shrink <= 1.0, else
    ValueError - no silent fallback. Default False: behaviour
    unchanged.

    Provenance tie-break (same build; ruling PT-A, scope enforced by
    the CALLER via tie_break_allowed): when the top-two margin lands
    within eps_eff (a tie), and tie_break_allowed is True, and
    tie_break_provenance carries a score for BOTH tied candidates,
    and the scores differ by at least tie_break_margin, the tie is
    resolved for the higher-provenance candidate instead of
    impassing, and the Decision is stamped tie_broken="provenance".
    The winner may be the net runner-up: provenance, not the net
    margin, decides a broken tie. In every other case the tie
    impasse stands exactly as before. The tie-break never fires on
    a non-tie and never overrides a conflict impasse (the conflict
    check above runs first).
    """
    ranking, excluded, log = attach_preferences(candidates, preferences)

    if not ranking:
        return Decision(
            selected_id=None,
            impasse=Impasse(
                kind="no-candidate",
                candidate_ids=[c.id for c in candidates],
                detail="every candidate was excluded by reject/prohibit votes",
                suggested_subgoal="relax constraints or propose new candidates",
            ),
            preference_log=log,
            excluded_ids=excluded,
        )

    if conflict_score >= conflict_threshold:
        top = [cid for cid, _ in ranking[:2]]
        return Decision(
            selected_id=None,
            impasse=Impasse(
                kind="conflict",
                candidate_ids=top,
                detail=f"conflict score {conflict_score:.2f} >= threshold "
                       f"{conflict_threshold:.2f}",
                suggested_subgoal="escalate to agent/human with the conflicting "
                                  "evidence surfaced, never hidden",
            ),
            preference_log=log,
            excluded_ids=excluded,
        )

    if density_scale and tie_epsilon_mode != "relative":
        raise ValueError(
            f"density_scale requires tie_epsilon_mode 'relative'; "
            f"got {tie_epsilon_mode!r} (DS-A is defined as a "
            "multiplier on the relative epsilon - no silent fallback)")

    if density_noise_gate and not density_scale:
        raise ValueError(
            "density_noise_gate requires density_scale=True "
            "(the gate scales the DS-A shrinkage - no silent "
            "fallback)")
    if density_noise_gate and not (
            0.0 <= density_noise_lo < density_noise_hi):
        raise ValueError(
            f"density noise thresholds must satisfy 0 <= lo < hi; "
            f"got lo={density_noise_lo!r}, hi={density_noise_hi!r}")

    if tie_band_quality and not (
            0.5 <= tie_band_lo < tie_band_hi <= 1.0):
        raise ValueError(
            f"tie band quality thresholds must satisfy "
            f"0.5 <= lo < hi <= 1.0; got lo={tie_band_lo!r}, "
            f"hi={tie_band_hi!r} (no silent fallback)")
    if tie_band_quality and not (
            tie_band_widen >= 1.0 and 0.0 < tie_band_shrink <= 1.0):
        raise ValueError(
            f"tie band factors must satisfy widen >= 1.0 and "
            f"0 < shrink <= 1.0; got widen={tie_band_widen!r}, "
            f"shrink={tie_band_shrink!r} (no silent fallback)")

    if tie_epsilon_mode == "relative":
        eps_eff = tie_epsilon * abs(ranking[0][1]) if ranking else tie_epsilon
    elif tie_epsilon_mode == "absolute":
        eps_eff = tie_epsilon
    else:
        raise ValueError(
            f"invalid tie_epsilon_mode {tie_epsilon_mode!r}; "
            "expected 'absolute' or 'relative'")

    if density_scale:
        # d = mean scoring-vote count over the top-two candidates.
        # Scoring votes are kinds better/worse; indifferent votes are
        # logged but never scored, and reject/prohibit votes exclude
        # rather than score, so neither counts toward density.
        counts = {cid: 0 for cid, _ in ranking}
        for v in preferences:
            if v.kind in ("better", "worse") and v.candidate_id in counts:
                counts[v.candidate_id] += 1
        top_counts = [counts[cid] for cid, _ in ranking[:2]]
        d = sum(top_counts) / len(top_counts) if top_counts else 1.0
        shrink = 1.0 / math.sqrt(max(d, 1.0))
        if density_noise_gate:
            # DS-NG gate (see the density_noise_gate docstring
            # paragraph): nu = pooled dispersion of the top-two
            # candidates' centred scoring-vote log-weights.
            pooled: list[float] = []
            for cid, _ in ranking[:2]:
                logs = [math.log(v.weight) for v in preferences
                        if v.kind in ("better", "worse")
                        and v.candidate_id == cid and v.weight > 0]
                if logs:
                    m = sum(logs) / len(logs)
                    pooled.extend(x - m for x in logs)
            if len(pooled) < 4:
                g = 0.0
            else:
                mu = sum(pooled) / len(pooled)
                nu = math.sqrt(
                    sum((x - mu) ** 2 for x in pooled) / len(pooled))
                if nu <= density_noise_lo:
                    g = 1.0
                elif nu >= density_noise_hi:
                    g = 0.0
                else:
                    g = ((density_noise_hi - nu)
                         / (density_noise_hi - density_noise_lo))
            shrink = 1.0 - g * (1.0 - shrink)
        eps_eff = eps_eff * shrink

    tie_band_q: float | None = None
    tie_band_m = 1.0
    if tie_band_quality:
        # TB-Q (see the tie_band_quality docstring paragraph): q is
        # the leader's share of top-two scoring-vote weight, no
        # centring. Applied to the FINAL eps_eff, after any density
        # multiplier, per the ruling.
        w_top = [
            sum(v.weight for v in preferences
                if v.kind in ("better", "worse")
                and v.candidate_id == cid and v.weight > 0)
            for cid, _ in ranking[:2]
        ]
        if len(w_top) == 2 and (w_top[0] + w_top[1]) > 0:
            tie_band_q = w_top[0] / (w_top[0] + w_top[1])
            if tie_band_q <= tie_band_lo:
                tie_band_m = tie_band_widen
            elif tie_band_q >= tie_band_hi:
                tie_band_m = tie_band_shrink
            else:
                tie_band_m = tie_band_widen + (
                    (tie_band_shrink - tie_band_widen)
                    * (tie_band_q - tie_band_lo)
                    / (tie_band_hi - tie_band_lo))
            eps_eff = eps_eff * tie_band_m
        # else: degenerate input - the band stays inert (m = 1.0),
        # the fail-safe toward the adopted stack.

    if len(ranking) > 1 and abs(ranking[0][1] - ranking[1][1]) <= eps_eff:
        # Provenance tie-break (PT-A): only inside this tie branch,
        # only when the caller armed it, only with both scores
        # present and a clear provenance margin.
        if (tie_break_allowed and tie_break_provenance is not None
                and ranking[0][0] in tie_break_provenance
                and ranking[1][0] in tie_break_provenance):
            p_first = tie_break_provenance[ranking[0][0]]
            p_second = tie_break_provenance[ranking[1][0]]
            if abs(p_first - p_second) >= tie_break_margin:
                winner = (ranking[0][0] if p_first > p_second
                          else ranking[1][0])
                return Decision(
                    selected_id=winner,
                    preference_log=log,
                    excluded_ids=excluded,
                    tie_broken="provenance",
                )
        return Decision(
            selected_id=None,
            impasse=Impasse(
                kind="tie",
                candidate_ids=[ranking[0][0], ranking[1][0]],
                detail=f"net scores {ranking[0][1]:.2f} vs {ranking[1][1]:.2f} "
                       f"within epsilon {eps_eff:.4f} "
                       f"({tie_epsilon_mode} mode)"
                       + (f" [tie_band q={tie_band_q:.3f} "
                          f"m={tie_band_m:.3f}]"
                          if tie_band_quality and tie_band_q is not None
                          else ""),
                suggested_subgoal="gather more evidence and re-enter the cycle "
                                  "(mm.confidence DDM accumulation)",
            ),
            preference_log=log,
            excluded_ids=excluded,
        )

    return Decision(
        selected_id=ranking[0][0],
        preference_log=log,
        excluded_ids=excluded,
    )
