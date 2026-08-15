"use client";

import { FormEvent, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import Header from "@/components/Header";
import { api } from "@/lib/api";

type System = {application:string;backend_version:string;environment:string;postgresql:string;redis:string;uptime_seconds:number;server_time:string;trading:string};
type RobinhoodConfig = {connection_name:string;endpoint:string;mode:string;status:string;updated_at:string};
const OFFICIAL_ENDPOINT = "https://agent.robinhood.com/mcp/trading";

export default function SystemPage(){
  const [system,setSystem]=useState<System|null>(null);
  const [broker,setBroker]=useState<RobinhoodConfig|null>(null);
  const [name,setName]=useState("Robinhood Agentic");
  const [endpoint,setEndpoint]=useState(OFFICIAL_ENDPOINT);
  const [message,setMessage]=useState("");
  const [saving,setSaving]=useState(false);

  useEffect(()=>{
    api<System>("/api/system").then(setSystem);
    api<RobinhoodConfig>("/api/broker/robinhood/config").then((value)=>{setBroker(value);setName(value.connection_name);setEndpoint(value.endpoint)});
  },[]);

  async function save(event:FormEvent<HTMLFormElement>){
    event.preventDefault();setSaving(true);setMessage("");
    try{
      const me=await api<{csrf_token:string}>("/api/auth/me");
      const value=await api<RobinhoodConfig>("/api/broker/robinhood/config",{method:"PATCH",headers:{"X-CSRF-Token":me.csrf_token},body:JSON.stringify({connection_name:name,endpoint})});
      setBroker(value);setMessage("Non-secret MCP configuration saved.");
    }catch(error){setMessage(error instanceof Error?error.message:"Unable to save configuration")}finally{setSaving(false)}
  }

  return <AppShell>
    <Header title="System Telemetry" subtitle="Runtime identity, connectivity, and guarded external integrations."/>
    <section className="card">{!system?<div className="loading">Loading system telemetry…</div>:Object.entries(system).map(([key,value])=><div className="status-row" key={key}><span>{key.replaceAll("_"," ")}</span><strong className={value==="CONNECTED"?"healthy":value==="DISABLED"?"bad":""}>{String(value)}</strong></div>)}</section>
    <section className="card" style={{marginTop:18}}>
      <div className="eyebrow">Broker connection · non-secret metadata only</div>
      <h2>Robinhood Trading MCP</h2>
      <p className="sub">Enter the official MCP connection information here. Authentication remains in Robinhood’s browser/OAuth flow; never enter a password, token, API key, or private key in Aegis.</p>
      <form onSubmit={save}>
        <div className="field"><label htmlFor="connection-name">Connection name</label><input id="connection-name" value={name} onChange={(event)=>setName(event.target.value)} maxLength={80} required/></div>
        <div className="field"><label htmlFor="mcp-endpoint">Official MCP endpoint</label><input id="mcp-endpoint" value={endpoint} onChange={(event)=>setEndpoint(event.target.value)} required/></div>
        <div className="status-row"><span>Mode</span><strong className="healthy">{broker?.mode||"READ_ONLY"}</strong></div>
        <div className="status-row"><span>Connection</span><strong>{broker?.status||"NOT_CONFIGURED"}</strong></div>
        {message&&<p className={message.includes("saved")?"sub":"error"}>{message}</p>}
        <button className="primary" disabled={saving||endpoint!==OFFICIAL_ENDPOINT}>{saving?"SAVING…":"SAVE MCP INFORMATION"}</button>
      </form>
      <p className="sub" style={{marginTop:14}}>Next, add this endpoint in Codex Settings → MCP servers → Streamable HTTP and complete Robinhood authorization on desktop.</p>
    </section>
  </AppShell>;
}
