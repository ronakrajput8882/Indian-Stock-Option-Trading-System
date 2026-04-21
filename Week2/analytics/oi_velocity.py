"""
OI Velocity — ΔOI per minute
Detects fresh buildup vs short covering vs long unwinding.
Spike velocity → strong directional signal.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis
import numpy as np

from config.settings import settings

log = logging.getLogger(__name__)


@dataclass
class OIVelocityResult:
    symbol: str
    oi_current: int
    oi_velocity_1m: float      # ΔOI per last 1 min
    oi_velocity_5m: float      # ΔOI per last 5 min
    oi_velocity_15m: float     # ΔOI per last 15 min
    oi_acceleration: float     # 2nd derivative
    signal: str                # BUILDUP / COVERING / UNWINDING / NEUTRAL
    strength: float            # 0-1 normalized signal strength
    timestamp: float

    def to_dict(self) -> dict:
        return self.__dict__


def classify_oi_signal(velocity: float, price_chg: float) -> str:
    """
    Classic OI + Price interpretation:
    OI↑ + Price↑ → Long buildup (bullish)
    OI↑ + Price↓ → Short buildup (bearish)
    OI↓ + Price↑ → Short covering (bullish fading)
    OI↓ + Price↓ → Long unwinding (bearish fading)
    """
    if velocity > 0 and price_chg > 0:
        return "LONG_BUILDUP"
    elif velocity > 0 and price_chg < 0:
        return "SHORT_BUILDUP"
    elif velocity < 0 and price_chg > 0:
        return "SHORT_COVERING"
    elif velocity < 0 and price_chg < 0:
        return "LONG_UNWINDING"
    return "NEUTRAL"


class OIVelocityCalculator:
    """Reads OI time-series from Redis sorted set, computes velocity."""

    def __init__(self, redis: aioredis.Redis):
        self._r = redis

    async def calculate(self, symbol: str) -> Optional[OIVelocityResult]:
        now = time.time()

        # Fetch OI sorted set: scores = timestamps, members = oi values
        # (written by redis_writer.py)
        series_raw = await self._r.zrangebyscore(
            f"oi_series:{symbol}",
            now - 1800,    # last 30 min
            now,
            withscores=True,
        )
        if len(series_raw) < 5:
            log.warning(f"Insufficient OI data for {symbol}: {len(series_raw)} pts")
            return None

        # Parse: [(member_oi, score_ts), ...]
        oi_series = [(float(oi), float(ts)) for oi, ts in series_raw]
        oi_arr = np.array([x[0] for x in oi_series])
        ts_arr = np.array([x[1] for x in oi_series])

        oi_current = int(oi_arr[-1])

        def delta_oi(minutes: int) -> float:
            cutoff = now - minutes * 60
            mask = ts_arr >= cutoff
            if mask.sum() < 2:
                return 0.0
            window = oi_arr[mask]
            return float(window[-1] - window[0])

        v1m = delta_oi(1)
        v5m = delta_oi(5)
        v15m = delta_oi(15)

        # Acceleration = velocity change (1m vs 5m normalized)
        v5m_rate = v5m / 5 if v5m != 0 else 0
        accel = v1m - v5m_rate

        # Get price change from tick
        tick_raw = await self._r.get(f"tick:{symbol}")
        price_chg = 0.0
        if tick_raw:
            tick = json.loads(tick_raw)
            price_chg = tick.get("change", 0.0)

        signal = classify_oi_signal(v1m, price_chg)

        # Normalize strength 0-1 using max seen velocity
        max_oi = float(oi_arr.max()) or 1.0
        strength = min(abs(v1m) / (max_oi * 0.01), 1.0)

        result = OIVelocityResult(
            symbol=symbol,
            oi_current=oi_current,
            oi_velocity_1m=round(v1m, 0),
            oi_velocity_5m=round(v5m, 0),
            oi_velocity_15m=round(v15m, 0),
            oi_acceleration=round(accel, 0),
            signal=signal,
            strength=round(strength, 4),
            timestamp=now,
        )

        await self._r.set(
            f"analytics:oi_velocity:{symbol}",
            json.dumps(result.to_dict()),
            ex=settings.ANALYTICS_TTL,
        )
        log.debug(f"OI Velocity {symbol}: 1m={v1m:.0f} signal={signal}")
        return result