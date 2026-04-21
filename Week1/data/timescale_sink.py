"""
TimescaleDB Sink — Kafka consumer → TimescaleDB
Batched COPY inserts for high-throughput tick persistence.
"""
import asyncio
import json
import logging
import signal
from datetime import datetime
from typing import Optional

import asyncpg
from confluent_kafka import Consumer, KafkaError

from config.settings import settings

log = logging.getLogger(__name__)


class TimescaleSink:
    BATCH_SIZE = 500
    FLUSH_INTERVAL = 5.0   # seconds

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._tick_buffer: list[dict] = []
        self._running = False
        self._stats = {"inserted": 0, "errors": 0, "batches": 0}

    async def connect(self):
        # Build DSN (asyncpg format)
        dsn = settings.DB_URL.replace("postgresql+asyncpg://", "postgresql://")
        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=settings.DB_POOL_SIZE,
            command_timeout=30,
        )
        log.info("TimescaleDB pool connected")

    async def close(self):
        if self._tick_buffer:
            await self._flush_ticks()
        if self._pool:
            await self._pool.close()

    async def _flush_ticks(self):
        if not self._tick_buffer:
            return
        batch = self._tick_buffer.copy()
        self._tick_buffer.clear()

        records = [
            (
                datetime.utcfromtimestamp(t["timestamp"]),
                t["symbol"],
                t.get("ltp"),
                t.get("volume"),
                t.get("oi"),
                t.get("bid"),
                t.get("ask"),
                t.get("bid_qty"),
                t.get("ask_qty"),
            )
            for t in batch
        ]

        try:
            async with self._pool.acquire() as conn:
                await conn.copy_records_to_table(
                    "ticks",
                    records=records,
                    columns=["time", "symbol", "ltp", "volume", "oi", "bid", "ask", "bid_qty", "ask_qty"],
                )
            self._stats["inserted"] += len(records)
            self._stats["batches"] += 1
            log.debug(f"Flushed {len(records)} ticks to TimescaleDB")
        except Exception as e:
            self._stats["errors"] += 1
            log.error(f"TimescaleDB flush error: {e}", exc_info=True)

    async def add_tick(self, tick: dict):
        self._tick_buffer.append(tick)
        if len(self._tick_buffer) >= self.BATCH_SIZE:
            await self._flush_ticks()

    async def _periodic_flush(self):
        """Background task: flush every FLUSH_INTERVAL seconds."""
        while self._running:
            await asyncio.sleep(self.FLUSH_INTERVAL)
            await self._flush_ticks()
            if self._stats["batches"] % 10 == 0 and self._stats["batches"] > 0:
                log.info(f"Sink stats | {self._stats}")

    async def run(self):
        await self.connect()
        self._running = True

        consumer = Consumer({
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP,
            "group.id": f"{settings.KAFKA_GROUP_ID}-timescale",
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "auto.commit.interval.ms": 5000,
        })
        consumer.subscribe([settings.KAFKA_TICK_TOPIC])

        flush_task = asyncio.create_task(self._periodic_flush())
        log.info("TimescaleDB sink started")

        try:
            while self._running:
                msgs = consumer.consume(num_messages=200, timeout=1.0)
                for msg in msgs:
                    if msg.error():
                        if msg.error().code() != KafkaError._PARTITION_EOF:
                            log.error(f"Kafka error: {msg.error()}")
                        continue
                    try:
                        tick = json.loads(msg.value())
                        await self.add_tick(tick)
                    except Exception as e:
                        log.warning(f"Tick parse error: {e}")
        finally:
            self._running = False
            flush_task.cancel()
            consumer.close()
            await self.close()
            log.info(f"Sink stopped | {self._stats}")

    def stop(self):
        self._running = False


async def main():
    logging.basicConfig(level=logging.INFO)
    sink = TimescaleSink()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, sink.stop)
    await sink.run()


if __name__ == "__main__":
    asyncio.run(main())