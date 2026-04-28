"""
Analytics Engine — orchestrates PCR + OI Velocity + IV + MaxPain
Runs every INTERVAL seconds during market hours.
Publishes composite signal to Redis pub/sub channel.
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Optional

import redis.asyncio as aioredis

from analytics.pcr import PCRCalculator, seed_fake_chain
from analytics.oi_velocity import OIVelocityCalculator
from analytics.iv_percentile import IVPercentileCalculator
from analytics.max_pain import MaxPainCalculator
from config.settings import settings

log = logging.getLogger(__name__)


@dataclass
class CompositeSignal:
    symbol: str
    pcr_signal: str
    oi_signal: str
    iv_regime: str
    max_pain_signal: str
    composite: str          # STRONG_BULL / BULL / NEUTRAL / BEAR / STRONG_BEAR
    score: float            # -2 to +2
    timestamp: float

    def to_dict(self) -> dict:
        return self.__dict__


def compute_composite(pcr_signal, oi_signal, iv_regime, max_pain_signal) -> tuple[str, float]:
    score = 0.0
    weights = {
        # PCR
        "BULLISH": +0.5, "BEARISH": -0.5, "NEUTRAL": 0,
        # OI
        "LONG_BUILDUP": +0.5, "SHORT_COVERING": +0.25,
        "SHORT_BUILDUP": -0.5, "LONG_UNWINDING": -0.25,
        # Max pain
        "BELOW_MAX_PAIN": +0.25, "ABOVE_MAX_PAIN": -0.25, "AT_MAX_PAIN": 0,
    }
    score += weights.get(pcr_signal, 0)
    score += weights.get(oi_signal, 0)
    score += weights.get(max_pain_signal, 0)

    if score >= 1.0:
        return "STRONG_BULL", score
    elif score >= 0.25:
        return "BULL", score
    elif score <= -1.0:
        return "STRONG_BEAR", score
    elif score <= -0.25:
        return "BEAR", score
    return "NEUTRAL", score


def is_market_hours() -> bool:
    now = datetime.now().time()
    open_t = dtime(9, 15)
    close_t = dtime(15, 30)
    return open_t <= now <= close_t


class AnalyticsEngine:
    INTERVAL = 30  # seconds between each analytics run

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._pcr: Optional[PCRCalculator] = None
        self._oi: Optional[OIVelocityCalculator] = None
        self._iv: Optional[IVPercentileCalculator] = None
        self._mp: Optional[MaxPainCalculator] = None
        self._running = False

    async def connect(self):
        self._redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        self._pcr = PCRCalculator(self._redis)
        self._oi = OIVelocityCalculator(self._redis)
        self._iv = IVPercentileCalculator(self._redis)
        self._mp = MaxPainCalculator(self._redis)
        log.info("Analytics engine connected to Redis")

    async def _seed_dev_data(self):
        """Seed fake options chain for dev/test."""
        atm_map = {"NIFTY": 22000, "BANKNIFTY": 48000, "FINNIFTY": 20000}
        for symbol in settings.SYMBOLS:
            await seed_fake_chain(self._redis, symbol, atm_map.get(symbol, 22000))

    async def run_once(self, symbol: str) -> Optional[CompositeSignal]:
        try:
            pcr = await self._pcr.calculate(symbol)
            oi = await self._oi.calculate(symbol)
            iv = await self._iv.calculate(symbol)
            mp = await self._mp.calculate(symbol)

            if not all([pcr, oi]):
                log.warning(f"Missing analytics for {symbol}, skipping composite")
                return None

            composite, score = compute_composite(
                pcr.signal,
                oi.signal,
                iv.regime if iv else "NORMAL",
                mp.signal if mp else "NEUTRAL",
            )

            sig = CompositeSignal(
                symbol=symbol,
                pcr_signal=pcr.signal,
                oi_signal=oi.signal,
                iv_regime=iv.regime if iv else "UNKNOWN",
                max_pain_signal=mp.signal if mp else "UNKNOWN",
                composite=composite,
                score=round(score, 4),
                timestamp=time.time(),
            )

            # Publish to Redis pub/sub for WebSocket subscribers
            await self._redis.set(
                f"signal:{symbol}",
                json.dumps(sig.to_dict()),
                ex=settings.ANALYTICS_TTL,
            )
            await self._redis.publish("signals", json.dumps(sig.to_dict()))
            log.info(f"Signal {symbol}: {composite} (score={score:.2f})")
            return sig

        except Exception as e:
            log.error(f"Analytics error for {symbol}: {e}", exc_info=True)
            return None

    async def run(self):
        await self.connect()
        self._running = True

        # Seed dev data once
        await self._seed_dev_data()

        log.info(f"Analytics engine running | symbols={settings.SYMBOLS} interval={self.INTERVAL}s")

        while self._running:
            if not is_market_hours():
                log.debug("Outside market hours, sleeping 60s")
                await asyncio.sleep(60)
                continue

            tasks = [self.run_once(sym) for sym in settings.SYMBOLS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, res in zip(settings.SYMBOLS, results):
                if isinstance(res, Exception):
                    log.error(f"Analytics failed for {sym}: {res}")

            await asyncio.sleep(self.INTERVAL)

    def stop(self):
        self._running = False


