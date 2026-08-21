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
            article_url=row.get("url","")
            source_url=article_url if isinstance(article_url,str) and article_url.startswith("https://") else self.base_url
            items.append(NormalizedItem("NEWS",article_url or row.get("title",""),when,"event",row,source_url))
        return items

    def active_listings(self) -> list[dict[str,str]]:
        response=self.client.get(self.base_url,params={"function":"LISTING_STATUS","state":"active","apikey":self.api_key})
        response.raise_for_status(); text=response.text
        if text.lstrip().startswith("{"):
            try: error=response.json().get("Information") or response.json().get("Note") or response.json().get("Error Message")
            except ValueError: error=None
            if error: raise ProviderError(str(error)[:300])
        rows=list(csv.DictReader(io.StringIO(text)))
        if not rows or "symbol" not in rows[0]: raise ProviderError("Active listing feed is missing")
        return rows

class AlpacaDataProvider(HttpProvider):
    name="alpaca";base_url="https://data.alpaca.markets"
    def __init__(self,key_id:str,secret_key:str,feed:str="iex",client:httpx.Client|None=None):
        if not key_id or not secret_key or "CHANGE_ME" in key_id or "CHANGE_ME" in secret_key:raise ProviderError("Alpaca data credentials are not configured")
        super().__init__(client);self.headers={"APCA-API-KEY-ID":key_id,"APCA-API-SECRET-KEY":secret_key};self.feed=feed
    def historical_daily(self,symbol:str)->list[NormalizedItem]:
        data=self.json(f"{self.base_url}/v2/stocks/{symbol}/bars",params={"timeframe":"1Day","start":"2016-01-01T00:00:00Z","limit":"10000","feed":self.feed,"adjustment":"all"},headers=self.headers)
        return [NormalizedItem("OHLCV",f"{symbol}:alpaca:{row['t']}",utc(row["t"]),"1d",{"open":row["o"],"high":row["h"],"low":row["l"],"close":row["c"],"volume":row["v"],"trade_count":row.get("n"),"vwap":row.get("vw")},f"{self.base_url}/v2/stocks/{symbol}/bars") for row in data.get("bars",[])]
    def dividends(self,symbol:str)->list[NormalizedItem]:
        data=self.json(f"{self.base_url}/v1/corporate-actions",params={"symbols":symbol,"types":"cash_dividend","start":"2016-01-01","end":datetime.now(UTC).date().isoformat(),"limit":"1000","data_quality":"complete"},headers=self.headers);rows=data.get("corporate_actions",{}).get("cash_dividends",[])
        return [NormalizedItem("CORPORATE_ACTION",f"{symbol}:alpaca:dividend:{row['id']}",utc(row["ex_date"]),"event",{"action":"DIVIDEND","amount":row.get("rate"),"dividend_per_share":row.get("rate"),"ex_dividend_date":row.get("ex_date"),"process_date":row.get("process_date"),"special":row.get("special",False),"foreign":row.get("foreign",False),"source_provider":"ALPACA","coverage":"HISTORICAL_COMPLETE"},f"{self.base_url}/v1/corporate-actions") for row in rows if row.get("ex_date")]

class NasdaqTraderProvider(HttpProvider):
    name="nasdaq_trader"
    sources=(("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt","Symbol","NASDAQ"),("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt","ACT Symbol","OTHER"))
    def directory(self) -> list[dict[str,str]]:
        found={}
        for url,symbol_field,default_exchange in self.sources:
            response=self.client.get(url,headers={"User-Agent":"Aegis Alpha security-universe/1.0 admin@pacificao.com"});response.raise_for_status()
            for row in csv.DictReader(io.StringIO(response.text),delimiter="|"):
                symbol=(row.get(symbol_field) or "").strip().upper()
                if not symbol or symbol.startswith("FILE CREATION TIME") or row.get("Test Issue")!="N":continue
                name=(row.get("Security Name") or "").strip();upper=name.upper();etf=row.get("ETF")=="Y"
                asset_type="ETF" if etf else "WARRANT" if "WARRANT" in upper else "PREFERRED" if "PREFERRED" in upper or " PFD" in upper else "ADR" if " ADR" in upper or "DEPOSITARY SHARES" in upper else "CEF" if "CLOSED END" in upper else "EQUITY"
                found[symbol]={"symbol":symbol,"name":name,"exchange":row.get("Exchange") or default_exchange,"asset_type":asset_type,"source_url":url}
        if not found:raise ProviderError("Official Nasdaq Trader symbol directory is empty")
        return list(found.values())

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
