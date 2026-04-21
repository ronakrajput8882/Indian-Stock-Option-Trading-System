"""
Max Pain — strike where option writers lose minimum.
Max pain acts as strike magnet near expiry.
Formula: for each candidate strike, sum of intrinsic loss for all OTM/ITM options.
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


@dataclass
class MaxPainResult:
    symbol: str
    max_pain_strike: float
    spot: float
    distance_pct: float         # (spot - max_pain) / spot * 100
    call_pain: dict             # strike → call pain
    put_pain: dict              # strike → put pain
    total_pain: dict            # strike → total pain
    signal: str                 # ABOVE_MAX_PAIN / BELOW_MAX_PAIN / AT_MAX_PAIN
    timestamp: float

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        # Convert float keys to str for JSON
        d["call_pain"] = {str(k): v for k, v in d["call_pain"].items()}
        d["put_pain"] = {str(k): v for k, v in d["put_pain"].items()}
        d["total_pain"] = {str(k): v for k, v in d["total_pain"].items()}
        return d


class MaxPainCalculator:
    def __init__(self, redis: aioredis.Redis):
        self._r = redis

    async def calculate(self, symbol: str) -> Optional[MaxPainResult]:
        raw = await self._r.get(f"options_chain:{symbol}")
        tick_raw = await self._r.get(f"tick:{symbol}")
        if not raw or not tick_raw:
            return None

        chain = json.loads(raw)
        spot = json.loads(tick_raw)["ltp"]

        # Group by strike
        strikes = sorted(set(c["strike"] for c in chain))
        ce_oi = {s: 0 for s in strikes}
        pe_oi = {s: 0 for s in strikes}

        for c in chain:
            if c["option_type"] == "CE":
                ce_oi[c["strike"]] = c.get("oi", 0)
            else:
                pe_oi[c["strike"]] = c.get("oi", 0)

        # For each candidate strike, compute total pain
        call_pain = {}
        put_pain = {}
        total_pain = {}

        for candidate in strikes:
            # Call pain: for each CE strike < candidate, writers lose (candidate - strike) * oi
            cp = sum(
                max(0, candidate - s) * ce_oi[s]
                for s in strikes if s < candidate
            )
            # Put pain: for each PE strike > candidate, writers lose (strike - candidate) * oi
            pp = sum(
                max(0, s - candidate) * pe_oi[s]
                for s in strikes if s > candidate
            )
            call_pain[candidate] = cp
            put_pain[candidate] = pp
            total_pain[candidate] = cp + pp

        max_pain_strike = min(total_pain, key=total_pain.get)
        distance_pct = round((spot - max_pain_strike) / spot * 100, 4)

        if abs(distance_pct) < 0.2:
            signal = "AT_MAX_PAIN"
        elif spot > max_pain_strike:
            signal = "ABOVE_MAX_PAIN"    # price may pull down
        else:
            signal = "BELOW_MAX_PAIN"    # price may pull up

        result = MaxPainResult(
            symbol=symbol,
            max_pain_strike=max_pain_strike,
            spot=spot,
            distance_pct=distance_pct,
            call_pain=call_pain,
            put_pain=put_pain,
            total_pain=total_pain,
            signal=signal,
            timestamp=time.time(),
        )

        await self._r.set(
            f"analytics:max_pain:{symbol}",
            json.dumps(result.to_dict()),
            ex=settings.ANALYTICS_TTL,
        )
        log.info(f"MaxPain {symbol}: strike={max_pain_strike} spot={spot:.0f} → {signal}")
        return result