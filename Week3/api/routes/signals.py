"""
GET /signal/{symbol} — returns composite analytics signal
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.auth import get_current_user, rate_limit
from config.settings import settings

router = APIRouter()


@router.get("/signal/{symbol}")
async def get_signal(
    symbol: str,
    request: Request,
    _: None = Depends(rate_limit),
):
    symbol = symbol.upper()
    if symbol not in settings.SYMBOLS:
        raise HTTPException(404, f"Symbol {symbol} not in watchlist")

    redis = request.app.state.redis
    raw = await redis.get(f"signal:{symbol}")
    if not raw:
        raise HTTPException(404, "No signal yet — analytics engine may be initializing")

    signal = json.loads(raw)

    # Enrich with PCR, OI, IV sub-signals
    sub_signals = {}
    for key in ["pcr", "oi_velocity", "iv", "max_pain"]:
        sub_raw = await redis.get(f"analytics:{key}:{symbol}")
        if sub_raw:
            sub_signals[key] = json.loads(sub_raw)

    return {
        "symbol": symbol,
        "signal": signal,
        "sub_signals": sub_signals,
    }


@router.get("/signals")
async def list_signals(request: Request, _: None = Depends(rate_limit)):
    """Get signals for all watched symbols."""
    redis = request.app.state.redis
    result = {}
    for symbol in settings.SYMBOLS:
        raw = await redis.get(f"signal:{symbol}")
        if raw:
            result[symbol] = json.loads(raw)
    return result


@router.get("/tick/{symbol}")
async def get_tick(symbol: str, request: Request):
    """Latest tick for symbol."""
    redis = request.app.state.redis
    raw = await redis.get(f"tick:{symbol.upper()}")
    if not raw:
        raise HTTPException(404, "No tick data")
    return json.loads(raw)