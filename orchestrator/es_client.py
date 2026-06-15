import httpx

from .config import settings


class ESClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=settings.es_url, timeout=10.0)

    async def close(self):
        await self.client.aclose()

    async def search_failed_ssh(self, since_seconds: int) -> list[dict]:
        body = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"event.action": "ssh_login"}},
                        {"match": {"event.outcome": "failure"}},
                        {"range": {"@timestamp": {"gte": f"now-{since_seconds}s"}}},
                    ]
                }
            },
            "size": 1000,
            "sort": [{"@timestamp": "asc"}],
        }
        r = await self.client.post(f"/{settings.es_index}/_search", json=body)
        r.raise_for_status()
        return r.json().get("hits", {}).get("hits", [])

    async def index_alert(self, doc: dict) -> None:
        r = await self.client.post(f"/{settings.alerts_index}/_doc", json=doc)
        r.raise_for_status()

    async def index_response(self, doc: dict) -> None:
        r = await self.client.post(f"/{settings.response_index}/_doc", json=doc)
        r.raise_for_status()
