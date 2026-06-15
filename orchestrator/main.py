import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import db
from .pipeline import poll_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poll_loop())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Autonomous SIEM Orchestrator", lifespan=lifespan)


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
        return {"error": "not found"}
    return r
