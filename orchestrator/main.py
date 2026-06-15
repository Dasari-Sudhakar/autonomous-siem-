import asyncio
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from . import db
from .config import settings
from .pipeline import poll_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
log = logging.getLogger(__name__)

DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"
REPORTS_OUT = Path("reports/output")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Autonomous SIEM Orchestrator", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML.read_text(encoding="utf-8")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/responses/active")
async def active():
    return await db.list_active()


@app.get("/responses/{response_id}")
async def get_response(response_id: int):
    r = await db.get(response_id)
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    return r


@app.get("/api/events/recent")
async def recent_events(seconds: int = 60):
    """Last N seconds of failed SSH events from Filebeat-indexed auth logs."""
    body = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"event.action": "ssh_login"}},
                    {"match": {"event.outcome": "failure"}},
                    {"range": {"@timestamp": {"gte": f"now-{seconds}s"}}},
                ]
            }
        },
        "size": 50,
        "sort": [{"@timestamp": "desc"}],
        "_source": ["@timestamp", "source.ip", "user.name", "host.name", "host.hostname"],
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.post(f"{settings.es_url}/{settings.es_index}/_search", json=body)
            r.raise_for_status()
        except Exception as e:
            log.warning("recent-events ES query failed: %s", e)
            return []
    hits = r.json().get("hits", {}).get("hits", [])
    return [
        {
            "ts": h["_source"].get("@timestamp"),
            "ip": (h["_source"].get("source") or {}).get("ip"),
            "user": (h["_source"].get("user") or {}).get("name"),
            "host": (h["_source"].get("host") or {}).get("hostname") or (h["_source"].get("host") or {}).get("name"),
        }
        for h in hits
    ]


@app.get("/api/alerts/recent")
async def recent_alerts(seconds: int = 300):
    """Last N seconds of orchestrator-emitted alerts (rule + ML verdicts)."""
    body = {
        "query": {"range": {"@timestamp": {"gte": f"now-{seconds}s"}}},
        "size": 30,
        "sort": [{"@timestamp": "desc"}],
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            r = await client.post(f"{settings.es_url}/{settings.alerts_index}/_search", json=body)
            r.raise_for_status()
        except Exception as e:
            log.warning("recent-alerts ES query failed: %s", e)
            return []
    return [h["_source"] for h in r.json().get("hits", {}).get("hits", [])]


@app.get("/api/incident/{response_id}.pdf")
async def incident_pdf(response_id: int):
    """Generate (or serve cached) PDF report for an incident."""
    if not await db.get(response_id):
        raise HTTPException(status_code=404, detail="incident not found")

    REPORTS_OUT.mkdir(parents=True, exist_ok=True)
    pdf_path = REPORTS_OUT / f"incident_{response_id}.pdf"

    if not pdf_path.exists():
        result = subprocess.run(
            [sys.executable, "reports/generate.py", "--id", str(response_id)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            log.error("PDF generation failed: %s", result.stderr)
            raise HTTPException(status_code=500, detail="pdf generation failed")

    return FileResponse(pdf_path, media_type="application/pdf",
                        filename=f"incident_{response_id}.pdf")
