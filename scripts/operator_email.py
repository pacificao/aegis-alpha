#!/usr/bin/env python3
import argparse, datetime, html, smtplib, ssl, subprocess, urllib.request
from email.message import EmailMessage
from pathlib import Path
def load(path):
    values={}
    for line in Path(path).read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1); values[key]=value
    return values
def health(url):
    try:
        with urllib.request.urlopen(url,timeout=10,context=ssl.create_default_context()) as response:
            return 'HEALTHY' if response.status==200 else f'HTTP {response.status}'
    except Exception:
        return 'UNAVAILABLE'
def db_lines(sql,cfg):
    command=["docker","compose","exec","-T","postgres","psql","-U",cfg.get("POSTGRES_USER","aegis"),"-d",cfg.get("POSTGRES_DB","aegis"),"-At","-c",sql]
    try:
        result=subprocess.run(command,capture_output=True,text=True,timeout=20,check=True)
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (OSError,subprocess.SubprocessError):
        return []

def investment_sections(cfg):
    q=chr(39)
    market=db_lines(f"WITH ranked AS (SELECT i.symbol,dr.event_time::date day,coalesce(dr.payload->>{q}adjusted_close{q},dr.payload->>{q}close{q})::numeric close,row_number() OVER (PARTITION BY i.symbol ORDER BY dr.event_time DESC) rn FROM data_records dr JOIN instruments i ON i.id=dr.instrument_id WHERE dr.data_type={q}OHLCV{q} AND dr.quality_status<>{q}REJECTED{q} AND i.symbol IN ({q}SPY{q},{q}QQQ{q},{q}IWM{q})) SELECT concat(symbol,{q} — {q},max(close) FILTER (WHERE rn=1),{q} close on {q},max(day) FILTER (WHERE rn=1),{q} — {q},round(((max(close) FILTER (WHERE rn=1)/nullif(max(close) FILTER (WHERE rn=2),0))-1)*100,2),{q}% vs prior session{q}) FROM ranked WHERE rn<=2 GROUP BY symbol HAVING count(*)=2 ORDER BY symbol",cfg)
    plans=db_lines(f"SELECT concat(symbol,{q} — {q},round(reserved_notional::numeric,2),{q} dollars reserved for {q},planned_entry_date,{q} — {q},replace(status,{q}_{q},{q} {q})) FROM planned_trades WHERE status IN ({q}PLANNED{q},{q}REVALIDATION_BLOCKED{q},{q}READY_FOR_FINAL_APPROVAL{q}) ORDER BY planned_entry_date LIMIT 5",cfg)
    decisions=db_lines(f"SELECT concat(decision,{q} {q},symbol,{q} — {q},array_to_string(reason_codes,{q}, {q})) FROM strategy_decisions WHERE created_at>=now()-interval {q}24 hours{q} AND decision<>{q}HOLD{q} ORDER BY created_at DESC LIMIT 5",cfg)
    intelligence=db_lines(f"SELECT concat(recommendation,{q} — {q},subject,{q}: {q},left(thesis,180),{q} — confidence {q},round(confidence::numeric*100),{q}%{q}) FROM intelligence_artifacts WHERE created_at>=now()-interval {q}36 hours{q} AND status<>{q}REJECTED{q} ORDER BY created_at DESC LIMIT 5",cfg)
    candidates=db_lines(f"SELECT concat(i.symbol,{q} — ex-dividend {q},coalesce(dr.payload->>{q}ex_dividend_date{q},dr.event_time::date::text),{q} — {q},coalesce(dr.payload->>{q}dividend_per_share{q},dr.payload->>{q}amount{q},{q}?{q}),{q} dollars per share — verify in Dividend Calendar{q}) FROM data_records dr JOIN instruments i ON i.id=dr.instrument_id WHERE dr.data_type={q}CORPORATE_ACTION{q} AND dr.quality_status<>{q}REJECTED{q} AND dr.event_time>=now() AND dr.event_time<now()+interval {q}14 days{q} ORDER BY dr.event_time LIMIT 6",cfg)
    news=db_lines(f"SELECT concat(coalesce(i.symbol,{q}MARKET{q}),{q} — {q},left(coalesce(dr.payload->>{q}title{q},{q}Untitled report{q}),150),{q} — {q},coalesce(dr.payload->>{q}source{q},{q}external source{q})) FROM data_records dr LEFT JOIN instruments i ON i.id=dr.instrument_id WHERE dr.data_type={q}NEWS{q} AND dr.quality_status<>{q}REJECTED{q} AND dr.event_time>=now()-interval {q}24 hours{q} ORDER BY dr.event_time DESC LIMIT 5",cfg)
    readiness=db_lines(f"WITH d AS (SELECT instrument_id,count(*) n FROM data_records WHERE data_type={q}CORPORATE_ACTION{q} AND quality_status<>{q}REJECTED{q} AND payload->>{q}action{q}={q}DIVIDEND{q} GROUP BY instrument_id), b AS (SELECT instrument_id,count(*) n FROM data_records WHERE data_type IN ({q}OHLCV{q},{q}BROKER_OHLCV{q}) AND quality_status<>{q}REJECTED{q} GROUP BY instrument_id) SELECT concat(count(*),{q} symbols currently meet the 12-event dividend and price-history research threshold.{q}) FROM d JOIN b USING(instrument_id) WHERE d.n>=12 AND b.n>=12",cfg)
    sections=[]
    sections.append(("Market tape",market or ["Benchmark price history is not fresh enough for a verified overnight comparison."]))
    sections.append(("Operator decisions",plans+decisions or ["No planned allocation or new non-HOLD strategy decision requires review."]))
    sections.append(("Upcoming Dividend Farm watch",candidates or ["No verified ex-dividend event was found in the next 14 days."]))
    sections.append(("Fresh intelligence",intelligence+news or ["No fresh cited intelligence or market news is available; do not infer a signal."]))
    sections.append(("Evidence readiness",readiness or ["Research-readiness count is unavailable."]))
    return sections

def postmarket_sections(cfg):
    q=chr(39);base=investment_sections(cfg)
    broker=db_lines(f"SELECT concat({q}Robinhood snapshot {q},status,{q} observed {q},source_observed_at,{q} — reconciliation {q},coalesce(reconciliation->>{q}status{q},{q}UNKNOWN{q}),{q} — {q},coalesce(reconciliation->>{q}order_records{q},{q}0{q}),{q} orders and {q},coalesce(reconciliation->>{q}fill_records{q},{q}0{q}),{q} fills observed{q}) FROM broker_snapshots ORDER BY source_observed_at DESC LIMIT 1",cfg)
    paper=db_lines(f"SELECT concat(count(DISTINCT po.id),{q} paper orders, {q},count(DISTINCT pf.id),{q} paper fills today — realized paper P&L {q},round(coalesce(max(pa.realized_pnl),0)::numeric,2),{q} dollars{q}) FROM paper_accounts pa LEFT JOIN paper_orders po ON po.account_id=pa.id AND po.created_at::date=current_date LEFT JOIN paper_fills pf ON pf.order_id=po.id",cfg)
    decisions=db_lines(f"SELECT concat(decision,{q} {q},symbol,{q} — {q},array_to_string(reason_codes,{q}, {q})) FROM strategy_decisions WHERE created_at::date=current_date ORDER BY created_at DESC LIMIT 6",cfg)
    plans=db_lines(f"SELECT concat(symbol,{q} — {q},replace(status,{q}_{q},{q} {q}),{q} — {q},round(reserved_notional::numeric,2),{q} dollars — entry {q},planned_entry_date) FROM planned_trades WHERE updated_at::date=current_date ORDER BY updated_at DESC LIMIT 5",cfg)
    ingestion=db_lines(f"SELECT concat(count(*) FILTER (WHERE status={q}COMPLETE{q} AND completed_at::date=current_date),{q} ingestion jobs completed today; {q},count(*) FILTER (WHERE status={q}FAILED{q} AND completed_at::date=current_date),{q} failed; {q},count(*) FILTER (WHERE status={q}QUEUED{q}),{q} remain queued.{q}) FROM ingestion_jobs",cfg)
    return [("Market close",base[0][1]),("Portfolio and execution evidence",broker+paper or ["No reconciled portfolio or paper-execution evidence is available."]),("Decisions and changes",plans+decisions or ["No strategy decision or planned-allocation change was recorded today."]),("Notable intelligence",base[3][1]),("Next-session watch",base[2][1]),("Data readiness",base[4][1]+ingestion)]

def send(kind,cfg,test,detail_override=None):
    now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    system=[('Aegis application',health('https://aegis-alpha.pacificao.com/health')),('Broker gateway',health('https://brokerage.aegis-alpha.pacificao.com/health')),('Trading','DISABLED')]
    sections=investment_sections(cfg) if kind=="premarket" else postmarket_sections(cfg) if kind=="postmarket" else []
    content={'premarket':('Pre-market Decision Briefing','Decisions that matter before the market opens.','Evidence-backed actions, upcoming opportunities, fresh intelligence, and readiness constraints. Items without sufficient evidence are explicitly excluded.'),'postmarket':('Post-market Highlights','The important outcomes from today.','Verified closing context, portfolio and execution evidence, decisions made, tomorrow’s watchlist, and exceptions. P&L or attribution is omitted whenever reconciliation cannot support it.'),'alert':('Attention Required','Aegis operator-attention alert.','TEST ALERT: delivery and escalation formatting validation only. No production incident or user action is currently asserted.')}
    if kind=='alert' and detail_override:
        content['alert']=('Attention Required','Aegis operator-attention alert.',detail_override)
    title,subtitle,detail=content[kind]; prefix='[TEST] ' if test else ''
    msg=EmailMessage(); msg['Subject']=f'{prefix}Aegis Alpha — {title} — {now}'; msg['From']=cfg.get('SMTP_FROM_ADDRESS') or cfg.get('SMTP_FROM') or cfg['SMTP_USERNAME']; msg['To']=cfg.get('OPERATOR_EMAIL') or cfg.get('SMTP_TO')
    lines=[f"{prefix}{title}",subtitle,"",detail]
    for heading,items in sections:lines.extend(["",heading+":"]+[f"- {item}" for item in items])
    lines.extend(["","System readiness:"]+[f"- {key}: {value}" for key,value in system]+["","Notification only. Authenticate in Aegis before taking action."])
    msg.set_content('\n'.join(lines))
    rows=''.join(f'<tr><td style="padding:10px;border-bottom:1px solid #203343">{html.escape(key)}</td><td style="padding:10px;border-bottom:1px solid #203343;text-align:right;color:{"#ef6a70" if value=="DISABLED" else "#37d7c3"};font-weight:bold">{html.escape(value)}</td></tr>' for key,value in system)
    badge='<div style="color:#dda84b;font-weight:bold">TEST DRAFT — NOT A LIVE SIGNAL</div>' if test else ''
    section_html="".join("<div style=\"margin:20px 0\"><h2 style=\"font-size:16px;color:rgb(55,215,195)\">{}</h2><ul>{}</ul></div>".format(html.escape(heading),"".join("<li style=\"margin:9px 0;line-height:1.45\">{}</li>".format(html.escape(item)) for item in items)) for heading,items in sections)
    msg.add_alternative(f'<!doctype html><html><body style="background:#071018;color:#e7edf3;font-family:Arial,sans-serif;padding:28px"><div style="max-width:680px;margin:auto;background:#101922;border:1px solid #203343;border-radius:10px;padding:28px"><div style="color:#37d7c3;font-size:12px;letter-spacing:2px">AEGIS ALPHA</div>{badge}<h1>{html.escape(title)}</h1><p style="color:#9aabba">{html.escape(subtitle)}</p><div style="background:#0a1118;border-left:3px solid #37d7c3;padding:16px;margin:20px 0">{html.escape(detail)}</div>{section_html}<table style="width:100%;border-collapse:collapse">{rows}</table><p style="color:#9aabba;font-size:12px;margin-top:24px">Notification only. Authenticate in Aegis before taking action.</p></div></body></html>',subtype='html')
    with smtplib.SMTP(cfg['SMTP_HOST'],int(cfg.get('SMTP_PORT','587')),timeout=20) as smtp:
        smtp.ehlo(); smtp.starttls(context=ssl.create_default_context()); smtp.ehlo(); smtp.login(cfg['SMTP_USERNAME'],cfg['SMTP_PASSWORD']); refused=smtp.send_message(msg)
    if refused:
        raise RuntimeError('SMTP server refused one or more recipients')
    print(f'{kind}: submission accepted')
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('kind',choices=('premarket','postmarket','alert')); parser.add_argument('--test',action='store_true'); parser.add_argument('--detail'); args=parser.parse_args()
    cfg=load('.env')
    if not cfg.get('SMTP_PASSWORD') or 'CHANGE_ME' in cfg['SMTP_PASSWORD']:
        cfg=load('/home/nathan/.config/aegis/mail.env')
    send(args.kind,cfg,args.test,args.detail)
if __name__=='__main__':
    main()
