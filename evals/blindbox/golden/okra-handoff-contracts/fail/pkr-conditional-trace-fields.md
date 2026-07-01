# Conditional PKR Trace Fields

CKRs are measurable contribution context, not worker work, and never dispatched. The CKR defines the
direct CKR metric for write governance.

PKRs carry `linked_ckr`, `source_dkr_checkpoint`, and `contribution_metric` only when available; if
they are not available, the PKR may omit them. They still have a done check, progress signals, and a
hand-back rule.
