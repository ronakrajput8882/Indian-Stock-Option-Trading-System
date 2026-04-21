"""
IV Percentile & IV Rank
IV Rank  = (current_IV - min_IV_1yr) / (max_IV_1yr - min_IV_1yr) * 100
IV %ile  = % of days in past year where IV was lower than today

High IV Rank (>50) → sell premium strategies (iron condor, strangle)
Low IV Rank (<20)  → buy premium strategies (long straddle, debit spreads)
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import redis.asyncio as aioredis

from config.settings import settings

log = logging.getLogger(__name__)

# Redis key storing daily IV closes for 1yr window
# Format: sorted set score=date_ordinal, member=iv_close
IV_HISTORY_KEY = "iv_history:{symbol}"
IV_HISTORY_DAYS = 252   # trading days in a year


@dataclass
class IVResult:
    symbol: str
    current_iv: float
    iv_rank: float          # 0-100
    iv_percentile: float    # 0-100
    iv_min_1yr: float
    iv_max_1yr: float
    iv_mean_1yr: float
    regime: str             # HIGH / NORMAL / LOW
    timestamp: float

    def to_dict(self) -> dict:
        return self.__dict__


def iv_regime(iv_rank: float) -> str:
    if iv_rank >= 50:
        return "HIGH"
    elif iv_rank <= 20:
        return "LOW"
    return "NORMAL"


class IVPercentileCalculator:
    def __init__(self, redis: aioredis.Redis):
        self._r = redis

    async def get_current_iv(self, symbol: str) -> Optional[float]:
        """Compute ATM IV from options chain."""
        raw = await self._r.get(f"options_chain:{symbol}")
        if not raw:
            return None
        chain = json.loads(raw)
        # ATM = nearest strike to spot
        tick_raw = await self._r.get(f"tick:{symbol}")
        spot = json.loads(tick_raw)["ltp"] if tick_raw else None
        if not spot:
            return None

        atm_records = sorted(chain, key=lambda x: abs(x["strike"] - spot))[:4]
        ivs = [c["iv"] for c in atm_records if c.get("iv", 0) > 0]
        return float(np.mean(ivs)) if ivs else None

    async def update_iv_history(self, symbol: str, iv: float):
        """Add today's ATM IV to rolling 1yr history."""
        from datetime import date
        ordinal = date.today().toordinal()
        key = IV_HISTORY_KEY.format(symbol=symbol)
        await self._r.zadd(key, {str(round(iv, 4)): ordinal})
        # Keep only last 252 trading days
        count = await self._r.zcard(key)
        if count > IV_HISTORY_DAYS:
            await self._r.zremrangebyrank(key, 0, count - IV_HISTORY_DAYS - 1)

    async def calculate(self, symbol: str) -> Optional[IVResult]:
        current_iv = await self.get_current_iv(symbol)
        if not current_iv:
            log.warning(f"Cannot compute current IV for {symbol}")
            return None

        await self.update_iv_history(symbol, current_iv)

        key = IV_HISTORY_KEY.format(symbol=symbol)
        history_raw = await self._r.zrange(key, 0, -1, withscores=False)
        if len(history_raw) < 10:
            log.warning(f"Insufficient IV history for {symbol}: {len(history_raw)} days")
            return None

        history = np.array([float(v) for v in history_raw])
        iv_min = float(history.min())
        iv_max = float(history.max())
        iv_mean = float(history.mean())

        iv_rank = round(
            (current_iv - iv_min) / (iv_max - iv_min) * 100 if iv_max > iv_min else 50.0, 2
        )
        iv_pctile = round(float(np.mean(history < current_iv)) * 100, 2)

        result = IVResult(
            symbol=symbol,
            current_iv=round(current_iv, 2),
            iv_rank=iv_rank,
            iv_percentile=iv_pctile,
            iv_min_1yr=round(iv_min, 2),
            iv_max_1yr=round(iv_max, 2),
            iv_mean_1yr=round(iv_mean, 2),
            regime=iv_regime(iv_rank),
            timestamp=time.time(),
        )

        await self._r.set(
            f"analytics:iv:{symbol}",
            json.dumps(result.to_dict()),
            ex=settings.ANALYTICS_TTL,
        )
        log.info(f"IV {symbol}: current={current_iv:.1f}% rank={iv_rank:.1f} → {result.regime}")
        return result