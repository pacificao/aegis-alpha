"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import Header from "@/components/Header";
import { api } from "@/lib/api";

type System = {application:string;backend_version:string;environment:string;postgresql:string;redis:string;uptime_seconds:number;server_time:string;trading:string};
type RobinhoodConfig = {connection_name:string;endpoint:string;mode:string;status:string;account_scope:string;updated_at:string};
type BrokerStatus = {status:string;detail:string;mode:string;trading:string;authorization_enabled:boolean;last_sync_at?:string|null;allowed_tools?:number;blocked_tools?:number};
const OFFICIAL_ENDPOINT = "https://agent.robinhood.com/mcp/trading";

export default function SystemPage(){
  const [system,setSystem]=useState<System|null>(null);
  const [broker,setBroker]=useState<RobinhoodConfig|null>(null);
  const [status,setStatus]=useState<BrokerStatus|null>(null);
  const [name,setName]=useState("Robinhood Agentic");
  const [endpoint,setEndpoint]=useState(OFFICIAL_ENDPOINT);
  const [message,setMessage]=useState("");
  const [saving,setSaving]=useState(false);
  const [completionNonce,setCompletionNonce]=useState("");
  const [callbackUrl,setCallbackUrl]=useState("");

  async function refreshStatus(){
    try{setStatus(await api<BrokerStatus>("/api/broker/status"))}catch{/* AuthGate handles session failures. */}
  }

  useEffect(()=>{
    api<System>("/api/system").then(setSystem);
    api<RobinhoodConfig>("/api/broker/robinhood/config").then((value)=>{setBroker(value);setName(value.connection_name);setEndpoint(value.endpoint)});
    api<BrokerStatus>("/api/broker/status").then(setStatus);
    const timer=window.setInterval(refreshStatus,3000);
    return()=>window.clearInterval(timer);
  },[]);

  async function csrf(){return (await api<{csrf_token:string}>("/api/auth/me")).csrf_token}

  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setSaving(true);setMessage("");
    try{
      const value=await api<RobinhoodConfig>("/api/broker/robinhood/config",{method:"PATCH",headers:{"X-CSRF-Token":await csrf()},body:JSON.stringify({connection_name:name,endpoint})});
      setBroker(value);setMessage("Non-secret MCP configuration saved.");
    }catch(error){setMessage(error instanceof Error?error.message:"Unable to save configuration")}finally{setSaving(false)}
  }

  async function connect(){
    if(!window.confirm("Continue to Robinhood in this browser? Aegis will permit read-only tools only; trading remains disabled."))return;
    const authorizationWindow=window.open("about:blank","_blank");
    if(!authorizationWindow){setMessage("Popup blocked. Allow popups for Aegis and try again.");return}
    authorizationWindow.opener=null;
    authorizationWindow.document.title="Opening Robinhood…";
    authorizationWindow.document.body.textContent="Opening Robinhood authorization…";
    setSaving(true);setMessage("");
    try{
      const result=await api<{authorization_url:string|null;completion_nonce?:string;status:string}>("/api/broker/robinhood/connect",{method:"POST",headers:{"X-CSRF-Token":await csrf()}});
      if(result.authorization_url&&result.completion_nonce){setCompletionNonce(result.completion_nonce);authorizationWindow.location.href=result.authorization_url}else{authorizationWindow.close();setMessage("Existing authorization is being validated.")}
    }catch(error){authorizationWindow.close();setMessage(error instanceof Error?error.message:"Unable to start authorization")}finally{setSaving(false)}
  }

  async function completeConnection(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setSaving(true);setMessage("");
    try{
      const response=await fetch("https://brokerage.aegis-alpha.pacificao.com/api/broker/robinhood/oauth/complete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({callback_url:callbackUrl,completion_nonce:completionNonce})});
      const body=await response.json().catch(()=>({detail:"Completion failed"}));
      if(!response.ok)throw new Error(body.detail||"Completion failed");
      setCallbackUrl("");setCompletionNonce("");setStatus(body);setMessage("Robinhood connected and read-only access validated.");
    }catch(error){setMessage(error instanceof Error?error.message:"Unable to complete authorization")}finally{setSaving(false)}
  }

  async function disconnect(){
    if(!window.confirm("Remove Aegis’s protected Robinhood authorization?"))return;
    setSaving(true);
    try{await api("/api/broker/robinhood/disconnect",{method:"POST",headers:{"X-CSRF-Token":await csrf()}});setCallbackUrl("");setCompletionNonce("");setMessage("Robinhood authorization and any pending connection attempt were cleared.");await refreshStatus()}
    catch(error){setMessage(error instanceof Error?error.message:"Unable to disconnect")}
    finally{setSaving(false)}
  }

  return <AppShell>
    <Header title="System Telemetry" subtitle="Runtime identity, connectivity, and guarded external integrations."/>
    <section className="card">{!system?<div className="loading">Loading system telemetry…</div>:Object.entries(system).map(([key,value])=><div className="status-row" key={key}><span>{key.replaceAll("_"," ")}</span><strong className={value==="CONNECTED"?"healthy":value==="DISABLED"?"bad":""}>{String(value)}</strong></div>)}</section>
    <section className="card" style={{marginTop:18}}>
      <div className="eyebrow">Aegis broker gateway · protected browser authorization</div>
      <h2>Robinhood Trading MCP</h2>
      <p className="sub">Aegis completes authorization in Robinhood’s browser flow. Never enter a Robinhood password, token, API key, or private key into this form.</p>
      <form onSubmit={save}>
        <div className="field"><label htmlFor="connection-name">Connection name</label><input id="connection-name" value={name} onChange={(event)=>setName(event.target.value)} maxLength={80} required/></div>
        <div className="field"><label htmlFor="mcp-endpoint">Official MCP endpoint</label><input id="mcp-endpoint" value={endpoint} onChange={(event)=>setEndpoint(event.target.value)} required/></div>
        <div className="status-row"><span>Mode</span><strong className="healthy">READ_ONLY</strong></div>
        <div className="status-row"><span>Account scope</span><strong className={broker?.account_scope==="SINGLE_ACCOUNT"?"healthy":"warn"}>{broker?.account_scope||"NOT_SELECTED"}</strong></div>
        <div className="status-row"><span>Connection</span><strong>{status?.status||broker?.status||"NOT_CONFIGURED"}</strong></div>
        <div className="status-row"><span>Trading</span><strong className="bad">DISABLED</strong></div>
        {status?.detail&&<p className="sub">{status.detail}</p>}
        {status?.last_sync_at&&<p className="sub">Last validated read sync: {status.last_sync_at}</p>}
        {message&&<p className={message.includes("saved")||message.includes("removed")?"sub":"error"}>{message}</p>}
        <button className="primary" disabled={saving||endpoint!==OFFICIAL_ENDPOINT}>{saving?"WORKING…":"SAVE MCP INFORMATION"}</button>
      </form>
      <div style={{display:"flex",gap:10,marginTop:12}}>
        <button className="primary" type="button" disabled={saving||endpoint!==OFFICIAL_ENDPOINT||!status?.authorization_enabled} onClick={connect}>CONNECT ROBINHOOD IN BROWSER</button>
        {status?.status!=="NOT_CONFIGURED"&&<button type="button" disabled={saving} onClick={disconnect}>DISCONNECT</button>}
      </div>
      {completionNonce&&<form onSubmit={completeConnection} style={{marginTop:16}}>
        <div className="field"><label htmlFor="oauth-callback-url">Robinhood localhost callback URL</label><input id="oauth-callback-url" value={callbackUrl} onChange={(event)=>setCallbackUrl(event.target.value)} placeholder="http://127.0.0.1:8765/callback?code=…&state=…" required/></div>
        <p className="sub">After Robinhood approves, the localhost page may not load. Copy its complete address from the desktop browser and paste it here. It is sent directly to the isolated gateway and is not stored by Aegis.</p>
        <button className="primary" disabled={saving||!callbackUrl.startsWith("http://127.0.0.1:8765/callback?")}>{saving?"VALIDATING…":"COMPLETE ROBINHOOD CONNECTION"}</button>
      </form>}
      {!status?.authorization_enabled&&<p className="sub" style={{marginTop:14}}>Authorization is disabled on this development host. Deploy the gateway in the protected execution domain before connecting.</p>}
      <p className="sub" style={{marginTop:14}}>The isolated gateway encrypts authorization material and rejects all order, cancellation, review, watchlist-mutation, scan-mutation, and unknown MCP tools.</p>
    </section>
  </AppShell>;
}
