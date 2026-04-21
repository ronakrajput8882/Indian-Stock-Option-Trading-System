"""
Redis Writer — Kafka consumer → Redis
Stores: latest tick, OHLCV bar, rolling OI, rolling volume
Keys:
  tick:{symbol}         → latest tick JSON (TTL 24h)
  ohlcv:{symbol}:{tf}  → latest bar JSON
  oi_series:{symbol}   → Redis sorted set (ts → oi)
  vol_series:{symbol}  → Redis sorted set (ts → volume)
"""
import asyncio
import json
import logging
import signal
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis
from confluent_kafka import Consumer, KafkaError, KafkaException

from config.settings import settings

log = logging.getLogger(__name__)


# ── OHLCV aggregator ──────────────────────────────────────────────────────────

@dataclass
class OHLCVBar:
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: int
    ts: float       # bar start timestamp
    tf: str = "1m"

    def to_dict(self) -> dict:
        return self.__dict__


class BarAggregator:
    """Aggregate ticks into 1-min OHLCV bars."""

    def __init__(self, tf_seconds: int = 60):
        self.tf = tf_seconds
        self._bars: dict[str, dict] = {}

    def push(self, tick: dict) -> Optional[OHLCVBar]:
        """Returns completed bar if interval rolled, else None."""
        symbol = tick["symbol"]
        ts = tick["timestamp"]
        bar_ts = (ts // self.tf) * self.tf  # floor to bar boundary

        if symbol not in self._bars or self._bars[symbol]["ts"] != bar_ts:
            completed = None
            if symbol in self._bars:
                b = self._bars[symbol]
                completed = OHLCVBar(
                    symbol=symbol,
                    open=b["open"], high=b["high"],
                    low=b["low"], close=b["close"],
                    volume=b["volume"], oi=b["oi"],
                    ts=b["ts"], tf="1m"
                )
            # start new bar
            self._bars[symbol] = {
                "ts": bar_ts, "open": tick["ltp"], "high": tick["ltp"],
                "low": tick["ltp"], "close": tick["ltp"],
                "volume": tick["volume"], "oi": tick["oi"],
            }
            return completed

        # update existing bar
        b = self._bars[symbol]
        b["high"] = max(b["high"], tick["ltp"])
        b["low"] = min(b["low"], tick["ltp"])
        b["close"] = tick["ltp"]
        b["volume"] += tick["volume"]
        b["oi"] = tick["oi"]
        return None


# ── Redis writer ──────────────────────────────────────────────────────────────

class RedisWriter:
    OI_SERIES_LEN = 390    # full trading day minutes
    VOL_SERIES_LEN = 390

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._agg = BarAggregator(tf_seconds=60)
        self._stats = defaultdict(int)

    async def connect(self):
        self._redis = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        await self._redis.ping()
        log.info("Redis connected")

    async def close(self):
        if self._redis:
            await self._redis.aclose()

    async def write_tick(self, tick: dict):
        symbol = tick["symbol"]
        pipe = self._redis.pipeline(transaction=False)

        # Latest tick
        pipe.set(f"tick:{symbol}", json.dumps(tick), ex=settings.TICK_TTL)

        # OI sorted set (score=timestamp, member=oi_value)
        pipe.zadd(f"oi_series:{symbol}", {str(tick["oi"]): tick["timestamp"]})
        pipe.zremrangebyrank(f"oi_series:{symbol}", 0, -self.OI_SERIES_LEN - 1)

        # Volume sorted set
        pipe.zadd(f"vol_series:{symbol}", {str(tick["volume"]): tick["timestamp"]})
        pipe.zremrangebyrank(f"vol_series:{symbol}", 0, -self.VOL_SERIES_LEN - 1)

        # OHLCV bar
        bar = self._agg.push(tick)
        if bar:
            pipe.set(f"ohlcv:{symbol}:1m", json.dumps(bar.to_dict()), ex=settings.TICK_TTL)
            pipe.lpush(f"ohlcv_hist:{symbol}:1m", json.dumps(bar.to_dict()))
            pipe.ltrim(f"ohlcv_hist:{symbol}:1m", 0, 999)  # keep 1000 bars

        await pipe.execute()
        self._stats["writes"] += 1


# ── Kafka consumer loop ───────────────────────────────────────────────────────

class KafkaRedisConsumer:
    POLL_TIMEOUT = 1.0
    BATCH_SIZE = 100

    def __init__(self):
        self._writer = RedisWriter()
        self._running = False
        self._consumer: Optional[Consumer] = None

    def _make_consumer(self) -> Consumer:
        return Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP,
            "group.id": settings.KAFKA_GROUP_ID,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
            "max.poll.interval.ms": 300000,
            "session.timeout.ms": 30000,
        })

    async def run(self):
        await self._writer.connect()
        self._consumer = self._make_consumer()
        self._consumer.subscribe([settings.KAFKA_TICK_TOPIC])
        self._running = True

        log.info(f"Kafka consumer subscribed to {settings.KAFKA_TICK_TOPIC}")

        try:
            while self._running:
                msgs = self._consumer.consume(
                    num_messages=self.BATCH_SIZE,
                    timeout=self.POLL_TIMEOUT,
                )
                tasks = []
                for msg in msgs:
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        log.error(f"Kafka error: {msg.error()}")
                        continue
                    try:
                        tick = json.loads(msg.value().decode())
                        tasks.append(self._writer.write_tick(tick))
                    except json.JSONDecodeError as e:
                        log.warning(f"JSON decode error: {e}")

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

        finally:
            self._consumer.close()
            await self._writer.close()
            log.info(f"Consumer stopped | stats: {dict(self._writer._stats)}")

    def stop(self):
        self._running = False


async def main():
    logging.basicConfig(level=logging.INFO)
    consumer = KafkaRedisConsumer()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, consumer.stop)

    await consumer.run()


if __name__ == "__main__":
    asyncio.run(main())