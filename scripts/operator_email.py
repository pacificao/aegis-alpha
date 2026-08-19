#!/usr/bin/env python3
import argparse, datetime, html, smtplib, ssl, urllib.request
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
def send(kind,cfg,test,detail_override=None):
    now=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    system=[('Aegis application',health('https://aegis-alpha.pacificao.com/health')),('Broker gateway',health('https://brokerage.aegis-alpha.pacificao.com/health')),('Trading','DISABLED')]
    content={'premarket':('Pre-market Decision Briefing','Decisions that matter before the market opens.','Review fresh, cited Aegis Intelligence artifacts, market regime, economic events, scenario evidence, and the operator decision queue. Verified broker snapshots are available in the authenticated Portfolio view; sensitive holdings are not included in email. No signal is inferred.'),'postmarket':('Post-market Highlights','The important outcomes from today.','Review post-market intelligence, anomalies, scenario research, and risk-control changes. Verified broker snapshots are available in the authenticated Portfolio view. Gains and attribution remain omitted until sufficient reconciled history exists; no performance is fabricated.'),'alert':('Attention Required','Aegis operator-attention alert.','TEST ALERT: delivery and escalation formatting validation only. No production incident or user action is currently asserted.')}
    if kind=='alert' and detail_override:
        content['alert']=('Attention Required','Aegis operator-attention alert.',detail_override)
    title,subtitle,detail=content[kind]; prefix='[TEST] ' if test else ''
    msg=EmailMessage(); msg['Subject']=f'{prefix}Aegis Alpha — {title} — {now}'; msg['From']=cfg.get('SMTP_FROM_ADDRESS') or cfg.get('SMTP_FROM') or cfg['SMTP_USERNAME']; msg['To']=cfg.get('OPERATOR_EMAIL') or cfg.get('SMTP_TO')
    lines=[f'{prefix}{title}',subtitle,'',detail,'','System readiness:']+[f'- {key}: {value}' for key,value in system]+['','Notification only. Authenticate in Aegis before taking action.']
    msg.set_content('\n'.join(lines))
    rows=''.join(f'<tr><td style="padding:10px;border-bottom:1px solid #203343">{html.escape(key)}</td><td style="padding:10px;border-bottom:1px solid #203343;text-align:right;color:{"#ef6a70" if value=="DISABLED" else "#37d7c3"};font-weight:bold">{html.escape(value)}</td></tr>' for key,value in system)
    badge='<div style="color:#dda84b;font-weight:bold">TEST DRAFT — NOT A LIVE SIGNAL</div>' if test else ''
    msg.add_alternative(f'<!doctype html><html><body style="background:#071018;color:#e7edf3;font-family:Arial,sans-serif;padding:28px"><div style="max-width:680px;margin:auto;background:#101922;border:1px solid #203343;border-radius:10px;padding:28px"><div style="color:#37d7c3;font-size:12px;letter-spacing:2px">AEGIS ALPHA</div>{badge}<h1>{html.escape(title)}</h1><p style="color:#9aabba">{html.escape(subtitle)}</p><div style="background:#0a1118;border-left:3px solid #37d7c3;padding:16px;margin:20px 0">{html.escape(detail)}</div><table style="width:100%;border-collapse:collapse">{rows}</table><p style="color:#9aabba;font-size:12px;margin-top:24px">Notification only. Authenticate in Aegis before taking action.</p></div></body></html>',subtype='html')
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
