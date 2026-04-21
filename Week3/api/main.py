"""
FastAPI Application — main entry point
Lifespan: starts analytics engine + data pipeline background tasks.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.signals import router as signals_router
from api.routes.trades import router as trades_router
from api.routes.pnl import router as pnl_router
from api.ws.ticker import router as ws_router
from analytics.engine import AnalyticsEngine
from config.settings import settings

log = logging.getLogger(__name__)
logging.basicConfig(level=settings.LOG_LEVEL)


# ── App state ─────────────────────────────────────────────────────────────────

class AppState:
    redis: aioredis.Redis = None
    analytics: AnalyticsEngine = None


state = AppState()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Starting NSE Algo Trading API")

    # Redis pool
    state.redis = await aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50,
    )
    app.state.redis = state.redis

    # Analytics engine (background task)
    state.analytics = AnalyticsEngine()
    analytics_task = asyncio.create_task(state.analytics.run())

    log.info("✅ Services started")
    yield

    # Shutdown
    state.analytics.stop()
    analytics_task.cancel()
    await state.redis.aclose()
    log.info("👋 API shutdown complete")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="NSE Algo Trading API",
    version="1.0.0",
    description="Institutional-grade options analytics + execution engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(signals_router, prefix="/api/v1", tags=["Signals"])
app.include_router(trades_router, prefix="/api/v1", tags=["Trades"])
app.include_router(pnl_router, prefix="/api/v1", tags=["P&L"])
app.include_router(ws_router, tags=["WebSocket"])


@app.get("/health")
async def health():
    redis_ok = False
    try:
        await app.state.redis.ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": redis_ok,
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        workers=1,
        log_level=settings.LOG_LEVEL.lower(),
    )