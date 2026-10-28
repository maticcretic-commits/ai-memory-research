AI Memory Research — Round 5

Talk-back / UX lane: S4 adjudicator, independence safeguards, and deadlock rule

Decision proposed: appoint an independent Safety Adjudicator, with binding authority over S4 classification and an automatic fail-closed rule whenever the adjudicator withholds a signature.

Memory Milestone (mm) is intended to move from memory retrieval to consequential decisions. That shift creates a governance problem: the people who build the system cannot also have unrestricted authority to determine whether its most serious failures count as acceptable. A severity framework is only as credible as the process that applies it when the outcome threatens a project's progress.

This proposal assigns final adjudication of disputed S4 cases to an independent, named-by-role decision-maker. It establishes separation from system development, protects adverse findings from executive override, and defines what happens when agreement cannot be reached. It is a governance design, not evidence that the proposed safeguards have been implemented or validated.

1. The role: Independent S4 Safety Adjudicator

The owner should be the Independent Safety Adjudicator (ISA): a qualified reviewer with authority over the classification of disputed S4 cases and no operational responsibility for building, deploying, or commercially promoting Memory Milestone.

The role must be assigned to a specific, named individual before any real production decision pairs are collected. Naming a role is not enough for execution; the individual, qualifications, appointment terms, and conflicts of interest must be documented.

The ISA owns three responsibilities:

Final classification: Determine whether the available evidence supports S4 severity, a lower severity, or an unresolved classification.

Evidence sufficiency: Assess whether the required six-element evidence chain is complete, traceable, and adequate to support the proposed classification.

Written disposition: Sign a reasoned decision that identifies the evidence reviewed, material uncertainties, dissenting views, and the resulting safety implications.

The ISA must assess foreseeable consequences rather than the system's intentions, the elegance of its reasoning, or whether its output appeared plausible. A memory-based decision that is confidently presented but relies on a false, stale, misattributed, or improperly disclosed memory must be judged by its potential consequences and the evidence available.

The adjudicator does not need to decide every disputed severity independently. The appointment is specifically for S4 disputes, avoiding unnecessary centralization of routine cases while preserving independence at the highest severity level.

2. Independence safeguards: builders may submit evidence, not control the verdict

Independence requires structural protections, not simply a promise to be impartial.

A. Separate appointment and removal authority

The ISA should be appointed by a governance authority outside the Memory Milestone development chain. That authority must also control removal and replacement. The project lead, engineering lead, and commercial owner must not be able to dismiss or replace the ISA because of an adverse finding.

The appointment should cover a defined review period, with removal permitted only for documented reasons such as incapacity, misconduct, or a material conflict of interest. Removal and replacement decisions must be independently recorded.

B. No outcome-linked compensation

The ISA must not receive compensation, promotion, contract renewal, or other benefits contingent on passing gates, lowering severity classifications, or enabling launch. The funding arrangement should be documented, with a protected review budget where feasible.

Complete financial independence may not be achievable in an early-stage project. Any residual dependence must therefore be disclosed and reviewed rather than concealed behind a nominally independent title.

C. Evidence access and immutable records

The ISA must have access to the complete relevant case record, including the source memory, timestamps, retrieval results, model output, applicable policy, decision context, foreseeable consequences, and subsequent corrections. Missing evidence must be explicitly recorded.

Every submission, revision, objection, adjudication, and signature should be timestamped in an append-only audit log. Builders may correct factual errors or submit additional evidence, but they must not silently alter the record after review.

The system's own confidence score must not determine the severity classification. Nor should a clean aggregate benchmark or a favorable red-team summary be accepted as a substitute for examining the individual case.

D. No developer veto

Developers may challenge the reasoning, identify contradictory evidence, and request reconsideration on documented grounds. They cannot overturn an adverse S4 finding through majority vote, executive instruction, or a later change in scoring rules.

The adjudicator must provide written reasons. The development team must be allowed to append a dissent, but disagreement cannot erase the original finding.

E. A second reviewer for conflicts, not a route to a preferred answer

A second independent reviewer may be used when the ISA has a conflict of interest, is unavailable, or requests independent technical or domain expertise. The replacement must be appointed through the same protected process.

A second reviewer must not be selected by the builders simply because the first reviewer reached an unfavorable conclusion. Review assignments and reasons for reassignment must remain auditable.

3. The deadlock rule: no signature, no clearance

The operational rule should be simple:

If the ISA will not sign, the S4 case remains unresolved and cannot be treated as cleared.

There are three possible dispositions:

Signed S4: The adjudicator confirms the S4 classification and records the evidence and required response.

Signed lower severity: The adjudicator provides a reasoned explanation for why the evidence supports a lower classification. The disposition remains open to normal audit and appeal.

No signature or unresolved dispute: The case is marked UNRESOLVED — NOT CLEARED. It cannot be downgraded automatically, excluded from reporting, or counted as a successful gate.

A missing signature is not proof that the case is S4. It is proof that clearance has not been established. This distinction avoids converting procedural caution into an unsupported factual claim while preserving the necessary safety barrier.

If the ISA and project team disagree, the team may submit new evidence or request a fresh review by an independently appointed replacement. Until that process produces a signed disposition, the unresolved case remains visible in reporting.

If the ISA refuses to sign because the six-element evidence chain is incomplete, the project must repair the evidence gap or accept the unresolved outcome. If the refusal reflects a disagreement over foreseeable consequences, the dissent and competing rationale must be retained. Silence, delay, or resignation must never be interpreted as approval.

No executive override should be permitted for the purpose of passing the S4 gate. Any change to the governance rule itself must be documented as a prospective policy change and must not retroactively convert an unresolved case into a passed one.

4. What this means for the locked research package

This adjudication design fits the existing S0–S4 severity framework and its requirement for a six-element evidence chain in S4 cases. It also supports the rule that disputed cases must be reported rather than averaged away.

It does not resolve the other outstanding gates. The numerical forgetting, talk-back, and calibration thresholds still require explicit specification. Values for net benefit by decision class must still be signed before results are examined. The proposed adjudicator also cannot determine whether simulated performance transfers to real-world decisions without appropriate evidence.

Most importantly, the existence of an independent adjudicator does not make an unsafe decision safe. It makes the process for identifying, documenting, and acting on disputed serious failures more resistant to internal pressure.

The package should therefore record this governance decision as proposed and awaiting appointment, not as an operational control already in force.

Top 5 findings

1. The accountable owner must be a role with binding authority. The Independent Safety Adjudicator owns final S4 disposition, subject to the documented review and replacement process.

2. Independence must be enforceable. Protected appointment, removal safeguards, conflict disclosure, outcome-independent compensation, and access to complete evidence matter more than the title itself.

3. The builder cannot veto an adverse finding. Technical challenges are legitimate; unilateral downgrading, silent record changes, and executive overrides are not.

4. A withheld signature means no clearance, not automatic S4 confirmation. The unresolved case stays visible and cannot count as a passed gate.

5. Governance and technical validation are separate. A credible adjudication process does not establish calibration, memory accuracy, net decision value, or real-world transfer.

Top 3 open questions

1. Who appoints the ISA in practice? Which person or body has sufficient independence, domain competence, budget authority, and protection against removal?

2. What is the precise appeal mechanism? Should a second reviewer replace the original adjudicator, independently concur, or review only a defined procedural error? The mechanism must prevent repeated reviews from becoming a search for a favorable verdict.

3. What evidence is sufficient to close an unresolved case? The six-element evidence chain needs an operational specification, including minimum provenance, counterevidence, consequence analysis, and treatment of missing or contradictory records.

What would change the sequencing plan?

I would change the sequencing plan if a pilot governance review showed that independent adjudication cannot be secured in practice—for example, if the project owner retains effective control over the adjudicator's appointment, access to evidence, or continued employment.

That finding would move governance validation ahead of any real production decision-pair collection. The next step would be to establish an external appointment and escalation mechanism, or to keep testing in simulation and passive telemetry until independence is demonstrable.

Conversely, a signed appointment charter, an auditable case-handling protocol, and a successful tabletop exercise involving a genuinely adverse finding would justify proceeding to the next eligible research stage. They would not waive the existing triple gate or the requirement to establish value per decision class.

What this piece deliberately does NOT prove

This proposal does not prove that an independent adjudicator will eliminate bias, that any S4 threshold is safe, or that the six-element evidence chain is sufficient in every domain. It does not establish that the reported 829 tests, LongMemEval-S results, or red-team outcomes have been independently verified. It does not claim that any governance exercise has occurred or that real production decision pairs exist.

The central recommendation is procedural: no builder-controlled override, no averaging away disputed severe cases, and no clearance without a reasoned signature from an appropriately independent adjudicator.
