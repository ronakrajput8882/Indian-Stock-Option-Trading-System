# 🇮🇳 NSE Algo Trading System

> A production-grade probabilistic decision engine for NSE options trading — not just a tool, but a full-stack system competing with institutional infrastructure.

---

## 📌 Overview

This system combines real-time NSE tick data, advanced analytics (PCR, OI Velocity, IV Percentile, Max Pain), a multi-strategy signal engine, ML-powered signal layer, and broker API execution into a single cohesive platform. Built with a FastAPI backend, React/Next.js frontend, TimescaleDB for time-series persistence, Kafka for tick streaming, and Redis for caching and pub/sub — it is designed to be deployed, not just demoed.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React / Next.js |
| Backend | FastAPI (async) + WebSocket |
| Data Pipeline | NSE WebSocket → Kafka → Redis → TimescaleDB |
| Analytics Engine | Python (PCR, OI Velocity, IV Percentile, Max Pain) |
| ML Signal Layer | LightGBM, PyTorch LSTM, LogReg Meta-Ensemble |
| Strategy Engine | Iron Condor, Momentum, Walk-Forward Backtester |
| Execution | Zerodha Kite Connect / Fyers v3 |
| Infrastructure | Docker (Redis, Kafka, TimescaleDB) |

---

## 📁 Project Structure

```
nse-algo-trading/
│
├── 📦 Week 1 — Data Pipeline
│   ├── data/
│   │   ├── nse_websocket.py       # NSE feed, reconnect logic
│   │   ├── kafka_producer.py      # tick → Kafka
│   │   ├── redis_writer.py        # Kafka consumer → Redis
│   │   └── timescale_sink.py      # Redis → TimescaleDB
│
├── 📊 Week 2 — Analytics Engine
│   ├── analytics/
│   │   ├── pcr.py                 # Put/Call ratio
│   │   ├── oi_velocity.py         # ΔOI per min
│   │   ├── iv_percentile.py       # IV rank vs 1yr window
│   │   ├── max_pain.py            # strike magnet calc
│   │   └── engine.py              # orchestrate all → Redis
│
├── 🌐 Week 3 — FastAPI + WebSocket
│   ├── api/
│   │   ├── main.py                # FastAPI app, CORS, lifespan
│   │   ├── routes/
│   │   │   ├── signals.py         # GET /signal/{symbol}
│   │   │   ├── trades.py          # POST /trade/{symbol}
│   │   │   └── pnl.py             # GET /pnl
│   │   ├── ws/
│   │   │   └── ticker.py          # WebSocket tick push
│   │   └── auth.py                # JWT + Redis rate limit
│
├── 📈 Week 4 — Strategy + Backtester
│   ├── strategy/
│   │   ├── base.py                # abstract Strategy class
│   │   ├── iron_condor.py
│   │   └── momentum.py
│   ├── backtest/
│   │   ├── engine.py              # historical replay
│   │   ├── metrics.py             # Sharpe, max DD, win rate
│   │   └── walk_forward.py        # WFO validation
│
├── 🤖 Week 5 — ML Signal Layer
│   ├── ml/
│   │   ├── features/
│   │   │   ├── engineer.py        # feature matrix from Redis
│   │   │   └── labels.py          # forward-return labels
│   │   ├── models/
│   │   │   ├── lgbm_signal.py     # LightGBM classifier
│   │   │   ├── lstm_signal.py     # PyTorch LSTM
│   │   │   └── meta_ensemble.py   # LogReg stacking
│   │   ├── train.py
│   │   ├── infer.py               # real-time → conf score
│   │   └── eval.py                # Sharpe per signal, F1
│
├── 🔒 Week 6 — Broker + Risk
│   ├── broker/
│   │   ├── adapters/
│   │   │   ├── base.py            # BrokerBase ABC
│   │   │   ├── zerodha.py         # Kite Connect
│   │   │   └── fyers.py           # Fyers v3
│   │   ├── order_manager.py       # place/cancel/track
│   │   └── position_tracker.py    # live P&L, Greeks
│   ├── risk/
│   │   ├── engine.py              # pre + post trade checks
│   │   ├── limits.py              # RISK_CONFIG dict
│   │   └── circuit_breaker.py     # Redis kill switch
│   └── scheduler/
│       └── lifecycle.py           # market open/close hooks
│
├── config/
│   ├── settings.py                # pydantic BaseSettings
│   └── .env                       # API keys, DB URLs
├── docker-compose.yml             # Redis, Kafka, TimescaleDB
├── requirements.txt
└── README.md
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/signal/{symbol}` | Live trading signal for a symbol |
| `POST` | `/trade/{symbol}` | Place order via broker API |
| `GET` | `/pnl` | Current P&L across all positions |
| `WS` | `/ws/ticker` | Real-time tick stream (WebSocket) |

---

## 📊 Core Analytics Engine

### Put-Call Ratio (PCR)
```
PCR = Total Put OI / Total Call OI
```
- `PCR > 1.2` → Strongly Bullish
- `PCR 0.8–1.2` → Neutral
- `PCR < 0.8` → Bearish

### OI Build-Up Logic
| Price | OI | Signal | Action |
|---|---|---|---|
| ↑ Up | ↑ Up | Long Build-up | Buy |
| ↓ Down | ↑ Up | Short Build-up | Sell |
| ↑ Up | ↓ Down | Short Covering | Cautious Buy |
| ↓ Down | ↓ Down | Long Unwinding | Caution |

### IV Percentile
```
IV Percentile = (Current IV - Min IV) / (Max IV - Min IV)
```
- `> 70` → High IV → **Sell** options (collect premium)
- `30–70` → Normal IV → Neutral / mixed strategies
- `< 30` → Low IV → **Buy** options (cheap premium)

### Max Pain
Strike price at which total option buyer losses are maximized — acts as a price magnet near expiry.

### OI Velocity
```
OI Velocity = ΔOI / Δt  (per 5-min bar)
```
Detects early institutional accumulation before price moves.

---

## 📐 Strategy Engine

### Iron Condor
Best when IV Percentile > 70 and market is range-bound.
- Sell OTM Call + Buy further OTM Call
- Sell OTM Put + Buy further OTM Put

### Momentum
Directional trade requiring both:
- Strong OI shift (build-up in direction)
- Price breakout confirmed with above-average volume

### Walk-Forward Optimization (WFO)
Prevents overfitting by validating the strategy on rolling out-of-sample windows before live deployment.

---

## 🎯 Probability of Profit (Black-Scholes)

```python
from scipy.stats import norm
import numpy as np

def black_scholes_pop(S, K, T, r, sigma):
    d2 = (np.log(S/K) + (r - 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return round(norm.cdf(d2), 4)
```

---

## 🤖 ML Signal Layer

| Model | Role |
|---|---|
| LightGBM | Fast gradient-boosted classifier for signal generation |
| PyTorch LSTM | Sequential pattern recognition on tick data |
| LogReg Ensemble | Meta-model stacking all signals → final confidence score |

Features are engineered in real-time from Redis. Labels are forward-return based. Evaluation uses Sharpe-per-signal and F1 score.

---

## 🛡️ Risk Management

| Rule | Value | Rationale |
|---|---|---|
| Risk per trade | 1–2% of capital | Survive 50 consecutive losses |
| Daily max loss | 5% of capital | Stop and review |
| Max open trades | 3–5 | Avoid correlation blowup |
| Stop-loss | Defined at entry | No discretionary exits |

**Position Sizing:**
```
Position Size = Capital × 0.02
```

**Circuit Breaker:** Redis-backed kill switch halts all order placement instantly when the daily loss limit is breached.

---

## ⚡ Execution Pipeline

```
Signal → Risk Check → Order Placement → Monitor → Exit
```

**Supported Brokers:**
- Zerodha Kite Connect API
- Fyers v3 API
- AngleOne API

**Real-Time Stack:**
- FastAPI with `async/await` for non-blocking I/O
- Kafka for high-throughput tick ingestion
- Redis pub/sub for live data distribution
- WebSockets for browser real-time updates
- TimescaleDB for time-series persistence

---

## 🧪 Backtesting

| Component | Details |
|---|---|
| Historical data | OPSTRA / NSE archives (EOD) |
| Slippage model | 0.03–0.05% per leg |
| Brokerage | Zerodha: ₹20/trade flat |
| Market regimes | Trending, range-bound, volatile |
| Key metrics | Sharpe ratio, max drawdown, win rate, avg R |
| Validation | Walk-Forward Optimization (WFO) |

---

## 🔬 Advanced Edge Signals

| Signal | Formula | Use |
|---|---|---|
| OI Velocity | `dOI/dt` over 5-min bars | Detect institutional accumulation |
| IV Skew | OTM Put IV − OTM Call IV | Market fear index |
| Delta Imbalance | Net delta across all positions | Monitor directional exposure |
| Gamma Exposure | `Σ(Gamma × OI × 100)` | Predict pinning near expiry |
| Max Pain | Strike magnet calc | Expiry-week price bias |

---

## ⚠️ Known Failure Points

- **Bad data** — Stale or incorrect option chain → wrong signals → real losses
- **Latency** — Missed entries; broker API timeouts
- **Overfitting** — Backtest looks perfect; live trading collapses
- **Ignoring costs** — Brokerage + slippage + STT eats all edge

---

## 🚀 Getting Started

```bash
# Clone the repo
git clone https://github.com/your-username/nse-algo-trading.git
cd nse-algo-trading

# Start infrastructure
docker-compose up -d        # Redis, Kafka, TimescaleDB

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example config/.env
# → Add broker API keys, DB URLs, Kafka bootstrap servers

# Run the API server
uvicorn api.main:app --reload
```

---

## 🗓️ Build Roadmap

| Week | Module | Deliverable |
|---|---|---|
| Week 1 | Data Pipeline | NSE WebSocket → Kafka → Redis → TimescaleDB |
| Week 2 | Analytics Engine | PCR, OI Velocity, IV Percentile, Max Pain |
| Week 3 | FastAPI + WebSocket | REST API, real-time tick push, JWT auth |
| Week 4 | Strategy + Backtester | Iron Condor, Momentum, WFO validation |
| Week 5 | ML Signal Layer | LightGBM + LSTM + Meta-Ensemble |
| Week 6 | Broker + Risk | Order manager, circuit breaker, lifecycle hooks |

---

## 📜 License

MIT License. Use at your own risk. This is not financial advice.

---

>