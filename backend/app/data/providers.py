from __future__ import annotations

from dataclasses import dataclass
import csv
import io
from datetime import UTC, datetime
from typing import Any

import httpx

class ProviderError(RuntimeError):
    pass

@dataclass(frozen=True)
class NormalizedItem:
    data_type: str
    external_id: str
    event_time: datetime
    interval: str
    payload: dict[str, Any]
    source_url: str

def utc(value: str) -> datetime:
    parsed=datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed=parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)

class HttpProvider:
    def __init__(self, client: httpx.Client | None = None):
        self.client=client or httpx.Client(timeout=20, follow_redirects=True)
    def json(self, url: str, *, params: dict[str,str] | None = None, headers: dict[str,str] | None = None) -> dict[str,Any]:
        response=self.client.get(url,params=params,headers=headers)
        response.raise_for_status()
        value=response.json()
        if not isinstance(value,dict):
            raise ProviderError("Provider returned a non-object response")
        return value

class AlphaVantageProvider(HttpProvider):
    name="alpha_vantage"
    base_url="https://www.alphavantage.co/query"
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        if not api_key or "CHANGE_ME" in api_key:
            raise ProviderError("Alpha Vantage API key is not configured")
        super().__init__(client); self.api_key=api_key
    def request(self, function: str, **params: str) -> dict[str,Any]:
        data=self.json(self.base_url,params={"function":function,"apikey":self.api_key,**params})
        error=data.get("Error Message") or data.get("Note") or data.get("Information")
        if error: raise ProviderError(str(error)[:300])
        return data
    def historical_daily(self, symbol: str) -> list[NormalizedItem]:
        data=self.request("TIME_SERIES_DAILY",symbol=symbol,outputsize="compact")
        series=data.get("Time Series (Daily)")
        if not isinstance(series,dict): raise ProviderError("Daily series is missing")
        items=[]
        for day,row in series.items():
            payload={"open":float(row["1. open"]),"high":float(row["2. high"]),"low":float(row["3. low"]),"close":float(row["4. close"]),"volume":int(row["5. volume"])}
            items.append(NormalizedItem("OHLCV",f"{symbol}:{day}",utc(day),"1d",payload,self.base_url))
        return items
    def quote(self, symbol: str) -> list[NormalizedItem]:
        row=self.request("GLOBAL_QUOTE",symbol=symbol).get("Global Quote",{})
        if not row: raise ProviderError("Quote is missing")
        day=row.get("07. latest trading day") or datetime.now(UTC).date().isoformat()
        payload={"price":float(row["05. price"]),"open":float(row["02. open"]),"high":float(row["03. high"]),"low":float(row["04. low"]),"volume":int(row["06. volume"]),"previous_close":float(row["08. previous close"])}
        return [NormalizedItem("QUOTE",f"{symbol}:{day}",datetime.now(UTC),"realtime",payload,self.base_url)]
    def fundamentals(self, symbol: str) -> list[NormalizedItem]:
        payload=self.request("OVERVIEW",symbol=symbol)
        if not payload.get("Symbol"): raise ProviderError("Fundamental overview is missing")
        return [NormalizedItem("FUNDAMENTAL",f"{symbol}:overview",datetime.now(UTC),"snapshot",payload,self.base_url)]
    def dividends(self, symbol: str) -> list[NormalizedItem]:
        rows=self.request("DIVIDENDS",symbol=symbol).get("data",[])
        return [NormalizedItem("CORPORATE_ACTION",f"{symbol}:dividend:{row['ex_dividend_date']}",utc(row["ex_dividend_date"]),"event",{"action":"DIVIDEND",**row},self.base_url) for row in rows]
    def news(self, tickers: str = "") -> list[NormalizedItem]:
        params={"limit":"50"};
        if tickers: params["tickers"]=tickers
        rows=self.request("NEWS_SENTIMENT",**params).get("feed",[])
        items=[]
        for row in rows:
            published=row.get("time_published","")
            when=datetime.strptime(published,"%Y%m%dT%H%M%S").replace(tzinfo=UTC) if published else datetime.now(UTC)
            items.append(NormalizedItem("NEWS",row.get("url",row.get("title","")),when,"event",row,self.base_url))
        return items

class FredProvider(HttpProvider):
    name="fred"
    base_url="https://api.stlouisfed.org/fred/series/observations"
    def __init__(self, api_key: str = "", client: httpx.Client | None = None):
        super().__init__(client); self.api_key=api_key if "CHANGE_ME" not in api_key else ""
    def observations(self, series_id: str) -> list[NormalizedItem]:
        if self.api_key:
            data=self.json(self.base_url,params={"series_id":series_id,"api_key":self.api_key,"file_type":"json"}); rows=data.get("observations",[]); source=self.base_url
        else:
            source="https://fred.stlouisfed.org/graph/fredgraph.csv"; response=self.client.get(source,params={"id":series_id}); response.raise_for_status(); rows=[{"date":row.get("DATE") or row.get("observation_date"),"value":row.get(series_id)} for row in csv.DictReader(io.StringIO(response.text))]
        return [NormalizedItem("ECONOMIC",f"{series_id}:{row['date']}",utc(row["date"]),"observation",{"series_id":series_id,**row},source) for row in rows if row.get("date") and row.get("value") not in (None,".","")]

class SecEdgarProvider(HttpProvider):
    name="sec_edgar"
    base_url="https://data.sec.gov/api/xbrl/companyfacts"
    def __init__(self, user_agent: str, client: httpx.Client | None = None):
        if "@" not in user_agent: raise ProviderError("SEC user agent must include an operator email")
        super().__init__(client); self.user_agent=user_agent
    def company_facts(self, cik: str) -> list[NormalizedItem]:
        padded=str(cik).zfill(10); url=f"{self.base_url}/CIK{padded}.json"
        payload=self.json(url,headers={"User-Agent":self.user_agent,"Accept-Encoding":"gzip, deflate"})
        observed=datetime.now(UTC)
        return [NormalizedItem("FUNDAMENTAL",f"CIK{padded}:companyfacts",observed,"snapshot",payload,url)]
