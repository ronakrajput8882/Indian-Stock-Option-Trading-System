"""
Kafka Producer — converts NSE ticks → Kafka topics
Symbol-keyed partitioning so same symbol always same partition (ordered).
"""
import asyncio
import json
import logging
import time
from typing import Optional

from confluent_kafka import Producer, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic

from config.settings import settings
from data.nse_websocket import NSEWebSocket, Tick

log = logging.getLogger(__name__)


# ── Kafka helpers ─────────────────────────────────────────────────────────────

def ensure_topics(topics: list[str], partitions: int = 4, replication: int = 1):
    """Create topics if missing."""
    admin = AdminClient({"bootstrap.servers": settings.KAFKA_BOOTSTRAP})
    existing = admin.list_topics(timeout=10).topics
    new_topics = [
        NewTopic(t, num_partitions=partitions, replication_factor=replication)
        for t in topics if t not in existing
    ]
    if new_topics:
        fs = admin.create_topics(new_topics)
        for t, f in fs.items():
            try:
                f.result()
                log.info(f"Created topic: {t}")
            except Exception as e:
                log.warning(f"Topic {t} already exists or error: {e}")


def delivery_report(err, msg):
    if err:
        log.error(f"Delivery failed {msg.topic()}/{msg.partition()}: {err}")
    else:
        log.debug(f"Delivered {msg.topic()}/{msg.partition()} offset={msg.offset()}")


# ── Producer ──────────────────────────────────────────────────────────────────

class TickProducer:
    def __init__(self):
        conf = {
            "bootstrap.servers": settings.KAFKA_BOOTSTRAP,
            "acks": 1,                    # leader ack, balance durability/speed
            "linger.ms": 5,               # micro-batch 5ms
            "batch.size": 65536,
            "compression.type": "lz4",
            "retries": 5,
            "retry.backoff.ms": 200,
        }
        self._producer = Producer(conf)
        self._stats = {"ticks": 0, "errors": 0, "bytes": 0}

    def send_tick(self, tick: Tick):
        """Non-blocking send. Key = symbol → same partition."""
        payload = tick.to_json().encode()
        try:
            self._producer.produce(
                topic=settings.KAFKA_TICK_TOPIC,
                key=tick.symbol.encode(),
                value=payload,
                on_delivery=delivery_report,
            )
            self._stats["ticks"] += 1
            self._stats["bytes"] += len(payload)
        except BufferError:
            log.warning("Kafka buffer full — flushing")
            self._producer.flush(timeout=5)
            self._producer.produce(
                topic=settings.KAFKA_TICK_TOPIC,
                key=tick.symbol.encode(),
                value=payload,
                on_delivery=delivery_report,
            )
        except KafkaException as e:
            self._stats["errors"] += 1
            log.error(f"Kafka produce error: {e}")

    def flush(self, timeout: float = 10.0):
        remaining = self._producer.flush(timeout=timeout)
        if remaining > 0:
            log.warning(f"{remaining} messages still in queue after flush")

    def stats(self) -> dict:
        return self._stats.copy()

    def poll(self):
        self._producer.poll(0)


# ── Pipeline: NSE → Kafka ─────────────────────────────────────────────────────

class NSEKafkaPipeline:
    def __init__(self):
        self._producer = TickProducer()
        self._tick_count = 0
        self._last_log = time.time()

    def on_tick(self, tick: Tick):
        self._producer.send_tick(tick)
        self._producer.poll()  # trigger callbacks
        self._tick_count += 1

        # Log throughput every 60s
        now = time.time()
        if now - self._last_log >= 60:
            stats = self._producer.stats()
            log.info(
                f"Pipeline stats | ticks={stats['ticks']} "
                f"errors={stats['errors']} "
                f"bytes={stats['bytes']:,}"
            )
            self._last_log = now

    async def run(self):
        ensure_topics([settings.KAFKA_TICK_TOPIC, settings.KAFKA_OPTIONS_TOPIC])
        ws = NSEWebSocket(on_tick=self.on_tick)
        log.info("NSE → Kafka pipeline started")
        try:
            await ws.start()
        finally:
            self._producer.flush()
            log.info("Pipeline stopped, Kafka flushed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = NSEKafkaPipeline()
    asyncio.run(pipeline.run())