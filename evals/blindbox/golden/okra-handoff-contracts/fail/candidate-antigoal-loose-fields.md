# Candidate Anti-Goal Loose Fields

The accumulated anti-goal layer is a candidate guardrail library represented as
`candidate-anti-goals.v1.json`.

Each record includes `metric_id`, `applies_when`, source refs, `candidate_status`,
`no_regression_evidence`, `trace_manifest_ref`, and a human ratification boundary.

This artifact does not require `threshold`, `type`, `does_not_apply_when`, or
`invalidates_when` / `recertify_by`.
