# DKR Heading Without Learning Cycle

Objective: raise harness acceptance from 0.60 to 0.90.

Anti-goal metric: hard_okra_violation_count <= 0.

Human owns the frame and thresholds.

The orchestrator owns objective checks, check-ins, the OKR board, and subagent steering until the
objective metric reaches target. DKR and PKR are worker scopes; CKR is measurable contribution
context, not subagent work.

DKR-1: Look at likely harness anti-patterns. Budget: one pass. Confidence: 70%.

CKR-1 links to source DKR-1 because it measures hard-gate false accepts. Direct metric comes from
checker output and no-cascade source reads.

PKR-1 links to source DKR-1 because it adds a checker task.

Each CKR has a mini reverse tornado with discovery/delivery balance. Check-in cadence is every
ten minutes with `.okra/workers/dkr-1/progress.jsonl` worker progress reports and PKR progress
signals for off-track work, quality drift, churn, stale metrics, and late discovery.

This artifact still rushes: it lists a DKR heading and then promotes CKR and PKR immediately. It
never defines the DKR learning checkpoint, evidence collected, probability update, candidate CKR
state, or orchestrator acceptance gate.
