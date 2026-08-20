from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN=ZoneInfo("America/New_York")

def observed(day: date) -> date:
    if day.weekday()==5: return day-timedelta(days=1)
    if day.weekday()==6: return day+timedelta(days=1)
    return day

def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    day=date(year,month,1)
    return day+timedelta(days=(weekday-day.weekday())%7+7*(n-1))

def last_weekday(year: int, month: int, weekday: int) -> date:
    day=date(year+month//12,month%12+1,1)-timedelta(days=1)
    return day-timedelta(days=(day.weekday()-weekday)%7)

def easter(year: int) -> date:
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4; f=(b+8)//25; g=(b-f+1)//3
    h=(19*a+b-d-g+15)%30; i=c//4; k=c%4; l=(32+2*e+2*i-h-k)%7; m=(a+11*h+22*l)//451
    value=h+l-7*m+114; return date(year,value//31,value%31+1)

def nyse_holidays(year: int) -> set[date]:
    days={observed(date(year,1,1)),nth_weekday(year,1,0,3),nth_weekday(year,2,0,3),easter(year)-timedelta(days=2),last_weekday(year,5,0),observed(date(year,7,4)),nth_weekday(year,9,0,1),nth_weekday(year,11,3,4),observed(date(year,12,25))}
    if year>=2022: days.add(observed(date(year,6,19)))
    return days

def market_session(day: date) -> dict:
    is_open=day.weekday()<5 and day not in nyse_holidays(day.year)
    opened=datetime.combine(day,time(9,30),EASTERN).astimezone(UTC) if is_open else None
    closed=datetime.combine(day,time(16,0),EASTERN).astimezone(UTC) if is_open else None
    return {"market":"XNYS","session_date":day.isoformat(),"is_open":is_open,"open_at":opened.isoformat() if opened else None,"close_at":closed.isoformat() if closed else None,"timezone":"America/New_York","source":"https://www.nyse.com/markets/hours-calendars"}

def sessions(start: date, end: date) -> list[dict]:
    if end<start or (end-start).days>370: raise ValueError("Calendar range must be between 0 and 370 days")
    return [market_session(start+timedelta(days=offset)) for offset in range((end-start).days+1)]

def next_sessions(count:int=10,start:date|None=None)->list[dict]:
    if count<1 or count>31:raise ValueError("Trading-session count must be between 1 and 31")
    day=start or datetime.now(UTC).astimezone(EASTERN).date();result=[]
    while len(result)<count:
        session=market_session(day)
        if session["is_open"]:result.append(session)
        day+=timedelta(days=1)
    return result
