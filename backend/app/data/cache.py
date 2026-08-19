import json
import redis

class DataCache:
    def __init__(self,url: str,ttl: int): self.client=redis.Redis.from_url(url,decode_responses=True); self.ttl=ttl
    def get(self,key: str):
        value=self.client.get(f"aegis:data:{key}")
        return json.loads(value) if value else None
    def set(self,key: str,value) -> None:
        self.client.setex(f"aegis:data:{key}",self.ttl,json.dumps(value,default=str))
    def invalidate(self) -> None:
        keys=list(self.client.scan_iter("aegis:data:*"))
        if keys: self.client.delete(*keys)
