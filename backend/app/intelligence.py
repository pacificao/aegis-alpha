from datetime import UTC,datetime
from .strategy_engine import canonical_checksum

def validate_artifact(payload,now=None):
    now=now or datetime.now(UTC);evidence=[e.model_dump(mode="json") for e in payload.evidence]
    fresh=all(0<=(now-e.as_of.astimezone(UTC)).total_seconds()<=e.max_age_seconds for e in payload.evidence);cited=all(e.source_url.startswith("https://") for e in payload.evidence)
    reasons=[]
    if not evidence:reasons.append("MISSING_EVIDENCE")
    if not fresh:reasons.append("STALE_EVIDENCE")
    if not cited:reasons.append("INVALID_CITATION")
    snapshot={"artifact_type":payload.artifact_type,"subject":payload.subject,"thesis":payload.thesis,"recommendation":payload.recommendation,"confidence":payload.confidence,"evidence":evidence,"analysis":payload.analysis}
    return snapshot,canonical_checksum(snapshot),"PROPOSED" if not reasons else "NEEDS_REVIEW",reasons

def consensus(artifact,reviews):
    independent=[r for r in reviews if r.independent and r.evidence_checksum==artifact.checksum];verdicts=[r.verdict for r in independent]
    if len(independent)<2:return "HUMAN_REVIEW","INSUFFICIENT_INDEPENDENT_REVIEWS"
    if all(v=="REJECT" for v in verdicts):return "REJECTED","CONSENSUS_REJECT"
    if all(v=="APPROVE" for v in verdicts) and artifact.recommendation in {"HOLD","RESEARCH","ADJUST"}:return "ELIGIBLE_FOR_RISK_REVIEW","CONSENSUS_APPROVE_LOW_IMPACT"
    return "HUMAN_REVIEW","DISAGREEMENT_OR_HIGH_IMPACT"
