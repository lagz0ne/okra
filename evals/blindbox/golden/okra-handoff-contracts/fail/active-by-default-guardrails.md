# Active By Default Guardrails

Prior-run anti-goals are loaded as active guardrails for the next frame by default.

`candidate-anti-goals.v1.json` includes `metric_id`, `threshold`, `type: "tripwire"`,
`applies_when`, `does_not_apply_when`, `invalidates_when`, source refs, `candidate_status`,
`no_regression_evidence`, `trace_manifest_ref`, and a human ratification boundary.
