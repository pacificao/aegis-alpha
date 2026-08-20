# ADR 0008: Governed intelligence and independent consensus

## Decision

Store AI-assisted output as immutable, cited artifacts rather than instructions. Require checksum-bound independent reviews. Only unanimous approval from at least two independent reviewers can advance low-impact research/hold/adjust artifacts to deterministic RiskEngine review. All high-impact recommendations and disagreement go to a human; all rejections reject.

## Consequences

AI/model providers remain replaceable and credential-isolated. Evidence and reviews are auditable. Consensus never equals risk authorization and cannot execute. The design adds deliberate friction and requires upstream clients to submit structured, cited results.


## Implemented verifier boundary

The authenticated Intelligence API can assemble a checksummed bundle from approved normalized record classes. A server-side Codex verifier receives only an immutable artifact package, uses no tools, requests strict structured output, disables API storage, and persists its verdict against the artifact checksum. Reserved model identities cannot be submitted through the human-review endpoint. Model failure or missing credentials fails closed. Aegis-Codex agreement advances only low-impact research posture to RiskEngine review; high-impact recommendations always escalate to the human.
