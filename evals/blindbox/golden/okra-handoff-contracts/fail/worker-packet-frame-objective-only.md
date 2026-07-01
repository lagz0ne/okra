# Worker Packet Frame Objective Only

The worker prompt packet is a dispatch packet. Frame fields include objective only.

Current state fields include current round, fresh metric reads, open flags, active CKR, active PKR,
and remaining budget. Previous checkpoint fields include previous DKR learning checkpoint and source
DKR checkpoint. Assignment fields include worker type, exact scope, allowed actions, and forbidden
actions. The packet includes budget, stop rule, hand-back rule, and output schema with progress.jsonl.
