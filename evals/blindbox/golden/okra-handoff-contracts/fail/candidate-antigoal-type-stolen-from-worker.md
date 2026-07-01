# Candidate Anti-Goal Type Stolen From Worker

The worker prompt packet includes a worker type field, assignment type, and output type.

The accumulated anti-goal layer is a candidate guardrail library represented as
`candidate-anti-goals.v1.json`.

Each record includes `metric_id`, `threshold`, `applies_when`, `does_not_apply_when`,
`invalidates_when`, source refs, `candidate_status`, `no_regression_evidence`,
`trace_manifest_ref`, and a human ratification boundary.

This candidate anti-goal section never says whether the guardrail itself is a drift or tripwire
type.
