"""
Put/Call Ratio (PCR) — Volume & OI based
PCR > 1.2 → bearish sentiment | PCR < 0.7 → bullish sentiment
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis

from config.settings import settings

log = logging.getLogger(__name__)


@dataclass
class PCRResult:
    symbol: str
    pcr_oi: float           # OI-based PCR
    pcr_volume: float       # Volume-based PCR
    put_oi: int
    call_oi: int
    put_volume: int
    call_volume: int
    signal: str             # BULLISH / BEARISH / NEUTRAL
    timestamp: float

    def to_dict(self) -> dict:
        return self.__dict__


def interpret_pcr(pcr_oi: float) -> str:
    if pcr_oi > 1.3:
        return "BEARISH"
    elif pcr_oi < 0.7:
        return "BULLISH"
    else:
        return "NEUTRAL"


class PCRCalculator:
    """
    Reads options chain from Redis.
    Key format: options_chain:{symbol} → JSON list of option records.
    Each record: {strike, option_type, oi, volume, expiry}
    """

    def __init__(self, redis: aioredis.Redis):
        self._r = redis

    async def calculate(self, symbol: str) -> Optional[PCRResult]:
        import time

        raw = await self._r.get(f"options_chain:{symbol}")
        if not raw:
            log.warning(f"No options chain found for {symbol}")
            return None

        chain: list[dict] = json.loads(raw)

        put_oi = sum(c["oi"] for c in chain if c["option_type"] == "PE")
        call_oi = sum(c["oi"] for c in chain if c["option_type"] == "CE")
        put_vol = sum(c.get("volume", 0) for c in chain if c["option_type"] == "PE")
        call_vol = sum(c.get("volume", 0) for c in chain if c["option_type"] == "CE")

        if call_oi == 0 or call_vol == 0:
            log.warning(f"Zero call OI/volume for {symbol}, skipping PCR")
            return None

        pcr_oi = round(put_oi / call_oi, 4)
        pcr_vol = round(put_vol / call_vol, 4) if call_vol > 0 else 0.0

        result = PCRResult(
            symbol=symbol,
            pcr_oi=pcr_oi,
            pcr_volume=pcr_vol,
            put_oi=put_oi,
            call_oi=call_oi,
            put_volume=put_vol,
            call_volume=call_vol,
            signal=interpret_pcr(pcr_oi),
            timestamp=time.time(),
        )

        # Persist to Redis
        await self._r.set(
            f"analytics:pcr:{symbol}",
            json.dumps(result.to_dict()),
            ex=settings.ANALYTICS_TTL,
        )
        log.info(f"PCR {symbol}: OI={pcr_oi:.3f} Vol={pcr_vol:.3f} → {result.signal}")
        return result


# ── Seed fake options chain (dev/test) ────────────────────────────────────────

async def seed_fake_chain(redis: aioredis.Redis, symbol: str, atm: float = 22000):
    """Seed Redis with a fake options chain for testing."""
    import random, time
    chain = []
    for strike_offset in range(-10, 11):
        strike = atm + strike_offset * 50
        for opt_type in ("CE", "PE"):
            oi_base = max(0, int(random.gauss(500000, 200000)))
            vol_base = max(0, int(oi_base * random.uniform(0.1, 0.4)))
            chain.append({
                "strike": strike,
                "option_type": opt_type,
                "oi": oi_base,
                "volume": vol_base,
                "expiry": "2025-01-30",
                "ltp": random.uniform(50, 500),
                "iv": random.uniform(10, 40),
            })
    await redis.set(f"options_chain:{symbol}", json.dumps(chain), ex=3600)
    log.info(f"Seeded fake options chain for {symbol} ({len(chain)} strikes)")