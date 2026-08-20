from datetime import UTC,datetime,timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from app.auth import Principal,csrf_protected,current_principal
from app.intelligence import consensus,validate_artifact
from app.main import app
from app.schemas import IntelligenceArtifactCreate

NOW=datetime.now(UTC)
RUN_ID=uuid4().hex
def artifact(**changes):
    value={"artifact_type":"MARKET_REGIME","subject":f"SPY regime review {RUN_ID}","thesis":"Evidence indicates a bounded neutral research posture.","recommendation":"HOLD","confidence":0.75,"evidence":[{"source_url":"https://example.com/official-source","title":"Official market observation","as_of":NOW.isoformat(),"max_age_seconds":3600,"claim":"Current observation supports neutral posture."}],"analysis":{"regime":"NEUTRAL","countercase":"Momentum could reverse."}}
    value.update(changes);return value

def test_validation_is_checksummed_and_stale_fails_closed():
    current=IntelligenceArtifactCreate(**artifact());snapshot,checksum,status,reasons=validate_artifact(current,NOW)
    assert len(checksum)==64 and status=="PROPOSED" and not reasons and snapshot["recommendation"]=="HOLD"
    stale=IntelligenceArtifactCreate(**artifact(evidence=[{"source_url":"https://example.com/official-source","title":"Old observation","as_of":(NOW-timedelta(hours=2)).isoformat(),"max_age_seconds":60,"claim":"Old evidence must fail freshness."}]))
    assert validate_artifact(stale,NOW)[2:]==("NEEDS_REVIEW",["STALE_EVIDENCE"])

def test_intelligence_auth_artifacts_reviews_consensus_and_no_authority():
    principal=Principal(username="test-operator",session_id="intel",csrf_token="csrf")
    with TestClient(app) as anonymous:assert anonymous.get("/api/intelligence/status").status_code==401
    app.dependency_overrides[current_principal]=lambda:principal;app.dependency_overrides[csrf_protected]=lambda:principal
    try:
      with TestClient(app) as client:
        status=client.get("/api/intelligence/status");assert status.status_code==200 and status.json()["risk_authority"] is False and status.json()["execution_available"] is False and status.json()["independent_verification"]=="WAITING_FOR_CREDENTIALS"
        evidence=client.get("/api/intelligence/evidence/SPY");assert evidence.status_code==200 and evidence.json()["authority"]=="EVIDENCE_ONLY" and evidence.json()["trading"]=="DISABLED"
        created=client.post("/api/intelligence/artifacts",json=artifact(),headers={"X-CSRF-Token":"csrf"});assert created.status_code==201,created.text
        body=created.json();disabled=client.post(f"/api/intelligence/artifacts/{body['id']}/verify/codex",headers={"X-CSRF-Token":"csrf"});assert disabled.status_code==409
        reserved=client.post(f"/api/intelligence/artifacts/{body['id']}/reviews",json={"reviewer":"codex:forged","verdict":"APPROVE","confidence":0.8,"rationale":"Attempted reserved identity forgery.","evidence_checksum":body["checksum"]},headers={"X-CSRF-Token":"csrf"});assert reserved.status_code==422
        assert body["governance"]=="HUMAN_REVIEW" and body["risk_authorized"] is False and body["executable"] is False and body["trading"]=="DISABLED"
        bad=client.post(f"/api/intelligence/artifacts/{body['id']}/reviews",json={"reviewer":"Verifier A","verdict":"APPROVE","confidence":0.8,"rationale":"Independent evidence supports this bounded conclusion.","evidence_checksum":"0"*64},headers={"X-CSRF-Token":"csrf"});assert bad.status_code==409
        for reviewer in ["Verifier A","Verifier B"]:
            reviewed=client.post(f"/api/intelligence/artifacts/{body['id']}/reviews",json={"reviewer":reviewer,"verdict":"APPROVE","confidence":0.8,"rationale":"Independent evidence supports this bounded conclusion.","evidence_checksum":body["checksum"]},headers={"X-CSRF-Token":"csrf"});assert reviewed.status_code==201,reviewed.text
        final=reviewed.json();assert final["governance"]=="ELIGIBLE_FOR_RISK_REVIEW" and final["risk_authorized"] is False and final["executable"] is False
        duplicate=client.post("/api/intelligence/artifacts",json=artifact(),headers={"X-CSRF-Token":"csrf"});assert duplicate.status_code==409
    finally:app.dependency_overrides.clear()

def test_high_impact_never_auto_advances():
    class A:recommendation="BUY";checksum="a"*64
    class R:independent=True;evidence_checksum="a"*64;verdict="APPROVE"
    assert consensus(A(),[R(),R()])==("HUMAN_REVIEW","DISAGREEMENT_OR_HIGH_IMPACT")
