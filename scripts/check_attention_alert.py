#!/usr/bin/env python3
import json
from pathlib import Path
from operator_email import health,load,send
STATE=Path('/home/nathan/.local/state/aegis/email-health.json')

def config():
    cfg=load('/home/nathan/aegis-alpha/.env')
    if not cfg.get('SMTP_PASSWORD') or 'CHANGE_ME' in cfg['SMTP_PASSWORD']:
        cfg=load('/home/nathan/.config/aegis/mail.env')
    return cfg
def main():
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
        detail='RECOVERY: all monitored Aegis services are healthy.' if recovered else 'ACTION REQUIRED: '+', '.join(failed)+' failed its public health check.'
        send('alert',config(),False,detail)
    temporary=STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(current,sort_keys=True)); temporary.replace(STATE)
    print('attention-monitor: healthy' if current['healthy'] else 'attention-monitor: attention required')
if __name__=='__main__':
    main()
