import json
import httpx
from app.ai_verifier import CodexVerifier,VerifierUnavailable
from app.intelligence import consensus


def client_for(payload,status=200):
    def handler(request):
        body=json.loads(request.content)
        assert body["store"] is False and body["tools"]==[]
        assert body["text"]["format"]["type"]=="json_schema"
        assert request.headers["authorization"].startswith("Bearer ")
        return httpx.Response(status,json=payload,request=request)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_codex_verifier_requires_credentials_and_structured_output():
    try:CodexVerifier("","gpt-5.6-sol");assert False
    except VerifierUnavailable:pass
    payload={"output_text":json.dumps({"verdict":"APPROVE","confidence":0.82,"rationale":"Evidence and countercase are internally consistent."})}
    result=CodexVerifier("fixture-key","gpt-5.6-sol",client_for(payload)).review({"checksum":"a"*64,"recommendation":"HOLD"})
    assert result["verdict"]=="APPROVE" and result["confidence"]==0.82


def test_aegis_codex_consensus_only_advances_low_impact():
    class Artifact:checksum="a"*64;recommendation="HOLD"
    class Review:independent=True;evidence_checksum="a"*64;verdict="APPROVE";reviewer="codex:gpt-5.6-sol"
    assert consensus(Artifact(),[Review()])==("ELIGIBLE_FOR_RISK_REVIEW","AEGIS_CODEX_AGREEMENT_LOW_IMPACT")
    Artifact.recommendation="BUY"
    assert consensus(Artifact(),[Review()])==("HUMAN_REVIEW","AEGIS_CODEX_DISAGREEMENT_OR_HIGH_IMPACT")
