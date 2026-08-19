from datetime import UTC,datetime
from sqlalchemy import func,select
from sqlalchemy.orm import Session
from ..models import DataRecord,DevelopmentActivity,Instrument,PaperAccount,PaperFill,PaperOrder,PaperPosition,RiskAssessment

MAX_QUOTE_AGE_SECONDS=300;SLIPPAGE_BPS=5.0;COMMISSION=1.0

def account(db:Session):
    row=db.scalar(select(PaperAccount).where(PaperAccount.name=="Aegis Paper"))
    if row is None:row=PaperAccount(name="Aegis Paper",initial_cash=100000.0,cash=100000.0,realized_pnl=0.0);db.add(row);db.commit();db.refresh(row)
    return row

def _utc(value):
    if value.tzinfo is None:return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

def execute(db:Session,risk_assessment_id:int,quote_record_id:int,actor:str,now=None):
    now=now or datetime.now(UTC);acct=account(db)
    if db.scalar(select(PaperOrder).where(PaperOrder.risk_assessment_id==risk_assessment_id)):raise ValueError("Risk assessment already consumed by paper simulator")
    risk=db.get(RiskAssessment,risk_assessment_id)
    if risk is None or risk.outcome!="AUTHORIZED" or not risk.risk_authorized:raise ValueError("Deterministic RiskEngine authorization is required")
    request=risk.request_snapshot;record=db.get(DataRecord,quote_record_id)
    if record is None or record.data_type!="QUOTE" or record.quality_status=="REJECTED":raise ValueError("A valid normalized live quote is required")
    instrument=db.get(Instrument,record.instrument_id) if record.instrument_id else None
    if instrument is None or instrument.symbol!=request["symbol"]:raise ValueError("Quote symbol does not match risk-authorized proposal")
    age=(now-_utc(record.observed_at)).total_seconds()
    if age<0 or age>MAX_QUOTE_AGE_SECONDS:raise ValueError("Live quote is stale")
    price=float(record.payload.get("price",0));qty=float(request["quantity"]);side=request["side"]
    if price<=0:raise ValueError("Quote has no valid price")
    if abs(price-float(request["price"]))/float(request["price"])*10000>100:raise ValueError("Quote moved beyond the authorized price boundary")
    fill_price=round(price*(1+(SLIPPAGE_BPS/10000 if side=="BUY" else -SLIPPAGE_BPS/10000)),6);notional=fill_price*qty
    position=db.scalar(select(PaperPosition).where(PaperPosition.account_id==acct.id,PaperPosition.symbol==instrument.symbol))
    if side=="BUY" and notional+COMMISSION>acct.cash:raise ValueError("Paper account has insufficient cash")
    if side=="SELL" and (position is None or position.quantity<qty):raise ValueError("Paper account has insufficient position")
    order=PaperOrder(account_id=acct.id,risk_assessment_id=risk.id,quote_record_id=record.id,symbol=instrument.symbol,side=side,quantity=qty,status="FILLED",reason="Deterministic paper fill from fresh normalized quote",created_by=actor);db.add(order);db.flush()
    db.add(PaperFill(order_id=order.id,price=fill_price,quantity=qty,commission=COMMISSION,slippage_bps=SLIPPAGE_BPS))
    if side=="BUY":
        acct.cash-=notional+COMMISSION
        if position is None:position=PaperPosition(account_id=acct.id,symbol=instrument.symbol,quantity=0,average_cost=0);db.add(position)
        position.average_cost=((position.average_cost*position.quantity)+notional)/(position.quantity+qty);position.quantity+=qty
    else:
        acct.cash+=notional-COMMISSION;acct.realized_pnl+=(fill_price-position.average_cost)*qty-COMMISSION;position.quantity-=qty
    db.add(DevelopmentActivity(actor=actor,action="paper_order_filled",entity_type="paper_order",entity_id=order.id,detail=f"{side} {qty} {instrument.symbol}; simulated=true; broker_called=false; trading=DISABLED"));db.commit();db.refresh(order);return order

def snapshot(db:Session):
    acct=account(db);positions=db.scalars(select(PaperPosition).where(PaperPosition.account_id==acct.id,PaperPosition.quantity>0)).all();items=[];market_value=0.0;unrealized=0.0
    for p in positions:
        inst=db.scalar(select(Instrument).where(Instrument.symbol==p.symbol));quote=db.scalar(select(DataRecord).where(DataRecord.instrument_id==inst.id,DataRecord.data_type=="QUOTE",DataRecord.quality_status!="REJECTED").order_by(DataRecord.observed_at.desc()).limit(1));price=float(quote.payload.get("price",p.average_cost)) if quote else p.average_cost;value=p.quantity*price;upl=(price-p.average_cost)*p.quantity;market_value+=value;unrealized+=upl;items.append({"symbol":p.symbol,"quantity":p.quantity,"average_cost":p.average_cost,"mark_price":price,"market_value":round(value,2),"unrealized_pnl":round(upl,2)})
    equity=acct.cash+market_value;fills=db.scalar(select(func.count()).select_from(PaperFill)) or 0
    return {"account_id":acct.id,"initial_cash":acct.initial_cash,"cash":round(acct.cash,2),"market_value":round(market_value,2),"equity":round(equity,2),"total_return_pct":round((equity/acct.initial_cash-1)*100,6),"realized_pnl":round(acct.realized_pnl,2),"unrealized_pnl":round(unrealized,2),"positions":items,"fill_count":fills,"environment":"PAPER","broker_called":False,"risk_authorized_per_order":True,"live_execution_available":False,"trading":"DISABLED"}
