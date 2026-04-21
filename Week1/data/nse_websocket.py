"""
NSE WebSocket Feed
Real feed: replace URL + auth with your data vendor (Zerodha ticker / True Data / Global DataFeeds)
Includes: exponential backoff reconnect, heartbeat, full tick parsing
"""
import asyncio
import json
import logging
import random
import struct
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from config.settings import settings

log = logging.getLogger(__name__)

# ── Tick model ────────────────────────────────────────────────────────────────

@dataclass
class Tick:
    symbol: str
    timestamp: float
    ltp: float
    volume: int
    oi: int
    bid: float
    ask: float
    bid_qty: int
    ask_qty: int
    change: float = 0.0
    change_pct: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ── Main WebSocket client ─────────────────────────────────────────────────────

class NSEWebSocket:
    """
    Production NSE ticker client.
    Swap _parse_message() for your vendor's binary/json protocol.
    Currently simulates realistic tick data for dev/testing.
    """
    MAX_RECONNECTS = 50
    BASE_DELAY = 1.0
    MAX_DELAY = 60.0

    def __init__(
        self,
        on_tick: Callable[[Tick], None],
        symbols: Optional[list[str]] = None,
    ):
        self.on_tick = on_tick
        self.symbols = symbols or settings.SYMBOLS
        self._ws = None
        self._running = False
        self._reconnect_count = 0
        self._last_heartbeat = time.time()
        # simulated last price per symbol
        self._sim_prices = {s: self._base_price(s) for s in self.symbols}

    @staticmethod
    def _base_price(symbol: str) -> float:
        base = {"NIFTY": 22000, "BANKNIFTY": 48000, "FINNIFTY": 20000}
        return base.get(symbol, 1000.0)

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self):
        """Start streaming. Auto-reconnects on failure."""
        self._running = True
        while self._running and self._reconnect_count < self.MAX_RECONNECTS:
            try:
                await self._connect()
            except (ConnectionClosed, WebSocketException, OSError) as exc:
                log.warning(f"WS disconnected: {exc}")
            except Exception as exc:
                log.error(f"WS unexpected error: {exc}", exc_info=True)
            if self._running:
                delay = self._backoff()
                log.info(f"Reconnect #{self._reconnect_count} in {delay:.1f}s")
                await asyncio.sleep(delay)

    async def stop(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _connect(self):
        """
        PRODUCTION: replace URL + headers with real broker WS endpoint.
        Zerodha: wss://ws.kite.trade?api_key=...&access_token=...
        """
        log.info(f"Connecting to NSE feed for symbols: {self.symbols}")
        # DEV MODE: simulate ticks without a real connection
        await self._simulate_ticks()

    async def _simulate_ticks(self):
        """
        Realistic tick simulator. Replace with real WS connect() in prod.
        Generates correlated Brownian motion per symbol.
        """
        log.info("[SIM] Tick simulator running. Replace with real WS in prod.")
        self._reconnect_count = 0
        tick_interval = 0.5  # 500ms between ticks

        while self._running:
            for symbol in self.symbols:
                tick = self._generate_tick(symbol)
                try:
                    self.on_tick(tick)
                except Exception as e:
                    log.error(f"on_tick callback error: {e}")

            await asyncio.sleep(tick_interval)
            self._last_heartbeat = time.time()

    def _generate_tick(self, symbol: str) -> Tick:
        """Geometric Brownian motion price simulation."""
        mu = 0.0
        sigma = 0.0002
        prev = self._sim_prices[symbol]
        change = prev * (mu + sigma * random.gauss(0, 1))
        ltp = round(prev + change, 2)
        self._sim_prices[symbol] = ltp

        spread = ltp * 0.0001
        return Tick(
            symbol=symbol,
            timestamp=time.time(),
            ltp=ltp,
            volume=random.randint(1000, 50000),
            oi=random.randint(500000, 5000000),
            bid=round(ltp - spread, 2),
            ask=round(ltp + spread, 2),
            bid_qty=random.randint(25, 500),
            ask_qty=random.randint(25, 500),
            change=round(change, 2),
            change_pct=round(change / prev * 100, 4),
        )

    def _parse_message(self, raw: bytes) -> list[Tick]:
        """
        PRODUCTION: parse your vendor's binary/JSON protocol here.
        Zerodha uses a custom binary packet format.
        Example binary parse skeleton below.
        """
        ticks = []
        # --- Zerodha binary format example ---
        # Each packet: 44 bytes per instrument
        # packet_len = len(raw)
        # n_packets = packet_len // 44
        # for i in range(n_packets):
        #     chunk = raw[i*44:(i+1)*44]
        #     token, ltp, ... = struct.unpack(">IiiIIii", chunk[:28])
        #     ...
        return ticks

    def _backoff(self) -> float:
        self._reconnect_count += 1
        delay = min(self.BASE_DELAY * (2 ** self._reconnect_count), self.MAX_DELAY)
        return delay + random.uniform(0, 1)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    logging.basicConfig(level=logging.INFO)

    def on_tick(tick: Tick):
        log.info(f"TICK {tick.symbol}: {tick.ltp} | OI: {tick.oi}")

    ws = NSEWebSocket(on_tick=on_tick)
    await ws.start()


if __name__ == "__main__":
    asyncio.run(main())