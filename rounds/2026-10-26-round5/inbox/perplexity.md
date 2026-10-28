The first V values can be locked only through a signed local valuation record—not inferred from mm’s reported performance or borrowed from public benchmarks. For an auditable starting workflow, use accounts-payable invoice exception handling: V1 values a routine routing correction; V2 values preventing a duplicate payment before release. No local records or authorized signatories were supplied, so neither numeric value is presently established.

One workflow, two decision classes

Consider an accounts-payable team reviewing invoices against purchase orders, receipt records, vendor records, and payment history. Memory Milestone proposes an action with its supporting memory; an authorized employee retains approval authority. This is a proposed evaluation workflow, not a claim that a deployment or experiment exists.

Define the classes narrowly before inspecting results:

V1, routine: route an invoice exception to the correct internal queue without changing payment authorization, amount, beneficiary, or deadline.

V2, financial: recommend holding a suspected duplicate invoice for human review before payment release. The comparison is the existing review process, not “pay everything.”

Exclude beneficiary changes, autonomous payment execution, and cases classified as high-consequence under the existing severity scheme. A financial label alone does not settle severity; foreseeable consequences still govern.

Public evidence supports the appraisal method, not these local classifications or values. HM Treasury’s Green Book describes opportunity-cost valuation and probability-weighted expected values. NIST states that risk tolerance is contextual and does not prescribe a universal acceptable level. Neither source supplies an mm-specific willingness to trade benefit against harm.

V1: documented inputs and declaration

For a successful routine routing correction, define a proposed valuation rule:

V1 = (t_saved / 60) × c_hour − c_incremental

Here, V1 is local currency per successful correction relative to the existing process. Required inputs are:

Timestamped queue histories or a documented time study establishing avoidable handling time, including handoffs and rework.

A finance-approved hourly opportunity-cost rate, with its calculation and cost components.

Incremental review, inference, logging, and administration costs, with allocation rules.

Evidence of what released staff time would actually enable.

That last item prevents “minutes saved” from silently becoming cash savings. The declaration must distinguish redeployed capacity from reduced expenditure. Opportunity cost concerns the next-best alternative use; it is not automatically payroll reduction.

The proposed declarants are the named accounts-payable operations owner, who attests to the workflow and time estimates, and a named finance controller or delegated management accountant, who approves the rate and valuation basis. These are required roles, not identified individuals: the organization must enter actual names and delegated authority.

Record a separate routine-error cost for misrouting, delay, and additional review. V1 is not permission to count successes while treating unsuccessful interventions as free.

V2: documented inputs and declaration

For the duplicate-payment class, value the recoverable economic consequence—not automatically the invoice’s face value:

V2 = A(1 − r) + C_recovery + C_funding − C_hold/review

Here, A is duplicate-payment exposure; r is the expected recovered fraction conditional on a duplicate payment occurring. The remaining terms represent avoidable recovery effort, funding cost during the recovery interval, and incremental hold/review cost.

Required local evidence comprises invoice and payment identifiers, duplicate-resolution records, recovery amounts and dates, write-offs, staff recovery time, approved funding rates, and review costs. Historical estimates need a stated observation window, inclusion rules, missing-data treatment, and uncertainty range. Probability-weighted valuation is an established appraisal technique; its probabilities and amounts must nevertheless come from applicable local evidence.

Crucially, do not multiply V2 by the system’s claimed detection accuracy: V2 values the consequence of a successful intervention. The evaluation separately estimates whether memory changes decisions. Any advance portfolio forecast must also account for whether the existing control would already have caught the duplicate.

The proposed declarants are the named accounts-payable process owner and treasury/finance controller. The delegated payment-control authority must separately approve the hold permissions. Record false-hold costs—including supplier disruption and late-payment consequences—rather than assuming equal benefit and harm.

What the declaration must freeze

Before results, create a versioned valuation register containing currency, price date, class boundaries, formulas, source-record identifiers, estimates and uncertainty ranges, error costs, permissions, exclusions, expiry date, and signatures.

For heterogeneous invoices, freeze the calculation rule and permissible inputs; do not pretend one unsupported amount fits every case. If the evaluation requires a single V2, fix a reference case or a reference distribution and aggregation rule before viewing outcomes.

Use separate preparation, approval, and evaluation responsibilities. An evaluator must not revise values after learning which arm wins. GAO’s internal-control guidance supports documented controls and separation of authorization, processing, recording, and review; the precise safeguards proposed here remain local design choices.

Refusal, missing evidence, and sequencing

If a declarant will not sign, record: NOT DECLARED, decision class, missing signatory, date, reason in their own words, disputed inputs, evidence requested, and reconsideration conditions. Distinguish refusal, unavailable evidence, and lack of delegated authority.

Do not impute a value from public averages, silently substitute another signatory, or encode an unknown value as measured zero. Record BLOCKED separately from any administrative zero-use restriction. High-consequence classes retain the stated zero authorization until both value and permissions are signed.

Declaration work can proceed now; real decision pairs remain prohibited until the existing forgetting, talk-back, and calibration gates are all green. Public frameworks support documented, context-specific risk management, not bypassing those gates.

Top 5 findings

Neither numeric V1 nor V2 is established by the supplied material.

Routine value requires attributable capacity benefit, not merely shorter elapsed time.

Duplicate-payment value depends on recoverability and existing controls, not face value alone.

Benefits, error costs, and permissions need separate declarations.

Non-signature must produce an auditable blocked status, not an invented estimate.

Top 3 open questions

Which actual individuals hold the required valuation and payment-control authority?

Do local records support credible time, recovery, and false-hold estimates?

Will the package accept case-specific values under a frozen rule, or require reference-case scalars?

Sequencing consequence and limits

The result that would change sequencing is failure to obtain an authorized, evidence-backed declaration for either class: that class stays out of value-based real-pair evaluation while records or passive telemetry are developed; another declared class may proceed only after all existing gates pass.

This piece deliberately does not prove mm’s internal claims, numeric V values, threshold safety, causal decision improvement, simulation-to-production transfer, or an independent S4 adjudication arrangement. It specifies how the first values become auditable—and when they must remain unlocked.
