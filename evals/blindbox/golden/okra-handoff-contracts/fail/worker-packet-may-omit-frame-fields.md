# Worker Packet May Omit Frame Fields

The worker prompt packet required fields include objective and current state. Packets may omit
`anti_goals` from the frame while still carrying the action envelope and human ratification.

Previous DKR checkpoint fields, assignment fields, budget and stop rule, hand-back rule, and output
schema appear elsewhere in the packet.
