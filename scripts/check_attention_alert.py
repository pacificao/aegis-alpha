#!/usr/bin/env python3
import json,subprocess
from pathlib import Path
from operator_email import health,load,send
STATE=Path('/home/nathan/.local/state/aegis/email-health.json')

def config():
    cfg=load('/home/nathan/aegis-alpha/.env')
    if not cfg.get('SMTP_PASSWORD') or 'CHANGE_ME' in cfg['SMTP_PASSWORD']:
        cfg.update(load('/home/nathan/.config/aegis/mail.env'))
    return cfg
def planned_notifications(cfg):
    from zoneinfo import ZoneInfo
    today=__import__("datetime").datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    expire=f"UPDATE planned_trades SET status='EXPIRED', notification_status='PENDING', notification_event='PLAN_EXPIRED', revalidation_detail='ENTRY_SESSION_PASSED' WHERE status IN ('PLANNED','REVALIDATION_BLOCKED') AND planned_entry_date < '{today}'"
    query="SELECT json_build_object('id',id,'event',notification_event,'symbol',symbol,'side',side,'quantity',quantity,'reserved_notional',reserved_notional,'planned_entry_date',planned_entry_date,'status',status,'rationale',rationale)::text FROM planned_trades WHERE notification_status='PENDING' ORDER BY created_at LIMIT 25"
    command=["docker","compose","exec","-T","postgres","psql","-U",cfg["POSTGRES_USER"],"-d",cfg["POSTGRES_DB"],"-At","-c",query]
    try: subprocess.run(command[:-1]+[expire],cwd="/home/nathan/aegis-alpha",capture_output=True,text=True,timeout=20,check=True)
    except (subprocess.SubprocessError,KeyError): return
    try: result=subprocess.run(command,cwd="/home/nathan/aegis-alpha",capture_output=True,text=True,timeout=20,check=True)
    except (subprocess.SubprocessError,KeyError): return
    rows=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    if not rows:return
    detail="; ".join(f"{x['event']}: {x['side']} {x['quantity']} {x['symbol']}, USD {x['reserved_notional']} reserved, entry {x['planned_entry_date']}, status {x['status']}. {x['rationale']}" for x in rows)
    send("alert",cfg,False,"PLANNED TRADE ACTION: "+detail+" Authenticate in Aegis to review. No broker hold or order was created; trading remains disabled.")
    ids=",".join(str(int(x["id"])) for x in rows);update=f"UPDATE planned_trades SET notification_status='SENT', notified_at=now() WHERE id IN ({ids}) AND notification_status='PENDING'"
    subprocess.run(command[:-1]+[update],cwd="/home/nathan/aegis-alpha",capture_output=True,text=True,timeout=20,check=True)

def main():
    cfg=config();planned_notifications(cfg)
    status={'Aegis application':health('https://aegis-alpha.pacificao.com/health'),'Broker gateway':health('https://brokerage.aegis-alpha.pacificao.com/health')}
    current={'healthy':all(value=='HEALTHY' for value in status.values()),'services':status}
    STATE.parent.mkdir(parents=True,exist_ok=True)
    previous=None
    if STATE.exists():
        try:
            previous=json.loads(STATE.read_text())
        except (OSError,json.JSONDecodeError):
            previous=None
    if previous is not None and previous!=current:
        failed=[name for name,value in status.items() if value!='HEALTHY']
        recovered=previous.get('healthy') is False and current['healthy'] is True
        severity='CRITICAL' if 'Aegis application' in failed else 'HIGH'
        detail='RECOVERY: all monitored Aegis services are healthy.' if recovered else severity+' ACTION REQUIRED: '+', '.join(failed)+' failed its public health check.'
        send('alert',config(),False,detail)
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(current,sort_keys=True)); temporary.replace(STATE)
    print('attention-monitor: healthy' if current['healthy'] else 'attention-monitor: attention required')
if __name__=='__main__':
    main()
