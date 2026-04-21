"""
POST /trade/{symbol} — place paper or live trade
GET  /trade/history  — recent trades
"""
import json
import time
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth import get_current_user, TokenData
from broker.order_manager import OrderManager
from risk.engine import RiskEngine

router = APIRouter()


class TradeRequest(BaseModel):
    side: Literal["BUY", "SELL"]
    qty: int = Field(gt=0, le=500)
    order_type: Literal["MARKET", "LIMIT"] = "MARKET"
    price: Optional[float] = None       # required for LIMIT
    product: Literal["MIS", "NRML"] = "MIS"
    strategy: Optional[str] = None
    paper: bool = True                  # paper trade by default


class TradeResponse(BaseModel):
    order_id: str
    symbol: str
    side: str
    qty: int
    status: str
    price: Optional[float]
    timestamp: float


@router.post("/trade/{symbol}", response_model=TradeResponse)
async def place_trade(
    symbol: str,
    req: TradeRequest,
    request: Request,
    user: TokenData = Depends(get_current_user),
):
    symbol = symbol.upper()
    redis = request.app.state.redis

    # Risk check
    risk = RiskEngine(redis)
    await risk.pre_trade_check(
        symbol=symbol,
        side=req.side,
        qty=req.qty,
        price=req.price or 0,
    )

    if req.paper:
        # Paper trade — store in Redis
        order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
        tick_raw = await redis.get(f"tick:{symbol}")
        fill_price = req.price
        if not fill_price and tick_raw:
            fill_price = json.loads(tick_raw).get("ltp", 0)

        trade = {
            "order_id": order_id,
            "symbol": symbol,
            "side": req.side,
            "qty": req.qty,
            "price": fill_price,
            "status": "COMPLETE",
            "strategy": req.strategy,
            "broker": "PAPER",
            "timestamp": time.time(),
            "user": user.sub,
        }
        await redis.lpush("trades:history", json.dumps(trade))
        await redis.ltrim("trades:history", 0, 999)

        # Update position
        pos_key = f"position:{symbol}"
        pos_raw = await redis.get(pos_key)
        position = json.loads(pos_raw) if pos_raw else {"qty": 0, "avg_price": 0}
        if req.side == "BUY":
            new_qty = position["qty"] + req.qty
            position["avg_price"] = (
                (position["avg_price"] * position["qty"] + fill_price * req.qty) / new_qty
                if new_qty > 0 else fill_price
            )
            position["qty"] = new_qty
        else:
            position["qty"] = position["qty"] - req.qty

        await redis.set(pos_key, json.dumps(position), ex=86400)
        return TradeResponse(**trade)

    else:
        # Live trade via broker
        manager = OrderManager(broker=user.role)
        order_id = await manager.place_order(
            symbol=symbol,
            side=req.side,
            qty=req.qty,
            order_type=req.order_type,
            price=req.price,
            product=req.product,
        )
        return TradeResponse(
            order_id=order_id,
            symbol=symbol,
            side=req.side,
            qty=req.qty,
            status="PENDING",
            price=req.price,
            timestamp=time.time(),
        )


@router.get("/trade/history")
async def trade_history(request: Request, limit: int = 50):
    redis = request.app.state.redis
    raw_list = await redis.lrange("trades:history", 0, limit - 1)
    return [json.loads(r) for r in raw_list]