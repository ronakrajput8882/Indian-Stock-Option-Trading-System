"""
GET /pnl — live and historical P&L
"""
import json
import time

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/pnl")
async def get_pnl(request: Request):
    redis = request.app.state.redis
    positions = {}

    for symbol in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
        pos_raw = await redis.get(f"position:{symbol}")
        if not pos_raw:
            continue
        pos = json.loads(pos_raw)
        if pos["qty"] == 0:
            continue

        tick_raw = await redis.get(f"tick:{symbol}")
        ltp = json.loads(tick_raw)["ltp"] if tick_raw else pos["avg_price"]
        unrealized = (ltp - pos["avg_price"]) * pos["qty"]
        positions[symbol] = {
            "qty": pos["qty"],
            "avg_price": round(pos["avg_price"], 2),
            "ltp": round(ltp, 2),
            "unrealized_pnl": round(unrealized, 2),
        }

    # Realized P&L from trades history
    trades_raw = await redis.lrange("trades:history", 0, 499)
    realized = 0.0
    for t in trades_raw:
        trade = json.loads(t)
        realized += trade.get("pnl", 0.0)

    total_unrealized = sum(p["unrealized_pnl"] for p in positions.values())
    return {
        "realized_pnl": round(realized, 2),
        "unrealized_pnl": round(total_unrealized, 2),
        "total_pnl": round(realized + total_unrealized, 2),
        "positions": positions,
        "timestamp": time.time(),
    }


@router.get("/pnl/daily")
async def get_daily_pnl(request: Request):
    """Returns daily P&L breakdown from TimescaleDB. Stub returns Redis data."""
    redis = request.app.state.redis
    trades_raw = await redis.lrange("trades:history", 0, 499)
    trades = [json.loads(t) for t in trades_raw]
    daily = {}
    for t in trades:
        day = time.strftime("%Y-%m-%d", time.localtime(t.get("timestamp", time.time())))
        daily.setdefault(day, 0.0)
        daily[day] += t.get("pnl", 0.0)
    return {"daily_pnl": daily}