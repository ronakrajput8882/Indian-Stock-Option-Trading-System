<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=200&section=header&text=📈%20Indian%20Stock%20Trading%20System&fontSize=42&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Production-Grade%20Options%20Trading%20Engine%20%7C%20FastAPI%20%2B%20Kafka%20%2B%20ML%20Signals%20%2B%20Broker%20Execution&descAlignY=60&descAlign=50" width="100%"/>
<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React%20%2F%20Next.js-Frontend-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://nextjs.org)
[![Kafka](https://img.shields.io/badge/Apache%20Kafka-Streaming-231F20?style=for-the-badge&logo=apachekafka&logoColor=white)](https://kafka.apache.org)
[![Redis](https://img.shields.io/badge/Redis-Pub%2FSub-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-Time--Series-FDB515?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.timescale.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-LSTM-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

</div>

---

## 📌 Project Overview

**NSE Algo Trading System** is a **production-grade probabilistic decision engine** for Indian options markets — not just a trading tool, but a full-stack algorithmic platform competing with institutional infrastructure.

The system ingests live NSE tick data via WebSocket, processes it through a Kafka + Redis pipeline, computes advanced options analytics (PCR, OI Velocity, IV Percentile, Max Pain), generates ML-powered trading signals, and executes orders through Zerodha or Fyers — all in real time.

- **Market:** NSE (National Stock Exchange of India) — Options & Equity Derivatives
- **Approach:** Data pipeline → Analytics → Signal Engine → ML Layer → Broker Execution
- **Brokers Supported:** Zerodha Kite Connect · Fyers v3 · AngleOne
- **Goal:** Build a system that systematically extracts edge from NSE options markets with strict risk controls

---

## 📂 Project Structure

```
Indian-Stock-Option-Trading-System/
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

## 🔄 System Pipeline

```
NSE WebSocket → Kafka Producer → Redis Writer → TimescaleDB
                                     ↓
                              Analytics Engine
                         (PCR · OI Velocity · IV % · Max Pain)
                                     ↓
                           ML Signal Layer
                    (LightGBM · LSTM · Meta-Ensemble)
                                     ↓
                   Signal → Risk Check → Order Placement → Monitor → Exit
```

1️⃣ **Tick Ingestion** — NSE WebSocket feed with auto-reconnect logic

2️⃣ **Streaming** — Kafka producer ingests ticks at high throughput

3️⃣ **Caching** — Redis consumer stores live state for sub-millisecond reads

4️⃣ **Persistence** — TimescaleDB sinks all tick data for backtesting and audit

5️⃣ **Analytics** — PCR, OI Velocity, IV Percentile, Max Pain computed per symbol

6️⃣ **ML Inference** — Real-time feature engineering → confidence score output

7️⃣ **Execution** — Pre-trade risk check → broker order placement → live P&L tracking

---

## 📊 Core Analytics Engine

### Put-Call Ratio (PCR)
```
PCR = Total Put OI / Total Call OI
```

| PCR Value | Signal | Interpretation |
|:---|:---:|:---|
| PCR > 1.2 | 🟢 Strongly Bullish | Hedgers buying puts = market resilience |
| PCR 0.8–1.2 | 🟡 Neutral | Wait for breakout confirmation |
| PCR < 0.8 | 🔴 Bearish | Excess call buying = complacency |

---

### OI Build-Up Logic

| Price | OI | Signal | Action |
|:---:|:---:|:---|:---|
| ↑ Up | ↑ Up | Long Build-up | Trend continuation → **Buy** |
| ↓ Down | ↑ Up | Short Build-up | Bears in control → **Sell** |
| ↑ Up | ↓ Down | Short Covering | Shorts exiting → **Cautious Buy** |
| ↓ Down | ↓ Down | Long Unwinding | Longs exiting → **Caution** |

---

### IV Percentile
```
IV Percentile = (Current IV − Min IV) / (Max IV − Min IV)
```

| IV Percentile | Regime | Strategy |
|:---|:---:|:---|
| > 70 | 🔴 High IV | **SELL** options — collect premium |
| 30–70 | 🟡 Normal IV | Neutral / mixed strategies |
| < 30 | 🟢 Low IV | **BUY** options — cheap premium |

---

### OI Velocity & Max Pain

- **OI Velocity** — `ΔOI / Δt` over 5-min bars → detects institutional accumulation before price moves
- **Max Pain** — Strike price where total option buyer losses are maximized; acts as expiry-week price magnet

---

## 🤖 ML Signal Layer

### Models

```python
# LightGBM — fast gradient-boosted classifier
lgbm = LGBMClassifier(n_estimators=500, learning_rate=0.05)

# PyTorch LSTM — sequential pattern recognition on tick data
lstm = LSTMSignal(input_dim=13, hidden_dim=64, num_layers=2)

# Meta-Ensemble — LogReg stacking over all model outputs
meta = LogisticRegression().fit(stacked_preds, y)
```

| Model | Role | Output |
|:---|:---|:---|
| LightGBM | Gradient-boosted signal classifier | Buy / Sell / Hold |
| PyTorch LSTM | Sequential tick pattern recognition | Directional probability |
| LogReg Ensemble | Meta-stacking all signals | Final confidence score (0–1) |

- Features engineered in real-time from Redis
- Labels derived from forward-return windows
- Evaluation via Sharpe-per-signal and F1 score

---

## 📈 Strategy Engine

### Iron Condor ⭐ Primary Strategy

Best when **IV Percentile > 70** and market is range-bound.

| Leg | Action | Strike |
|:---|:---|:---|
| Sell Call | Sell OTM Call | ~200 pts above spot |
| Buy Call | Buy further OTM Call | Hedge |
| Sell Put | Sell OTM Put | ~200 pts below spot |
| Buy Put | Buy further OTM Put | Hedge |

### Momentum / Directional Trade

Entry only when **both** conditions confirm:
- ✅ Strong OI shift (build-up in direction)
- ✅ Price breakout with above-average volume

### Walk-Forward Optimization (WFO)

Prevents overfitting by validating strategy on rolling out-of-sample windows before any live deployment.

---

## 🎯 Probability of Profit (Black-Scholes)

```python
from scipy.stats import norm
import numpy as np

def black_scholes_pop(S, K, T, r, sigma):
    d2 = (np.log(S/K) + (r - 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
    return round(norm.cdf(d2), 4)  # Prob price stays below K at expiry

# Delta proxy (simpler approximation)
# POP ≈ 1 - abs(Delta)
```

---

## 🛡️ Risk Management

| Rule | Value | Rationale |
|:---|:---:|:---|
| Risk per trade | 1–2% of capital | Survive 50 consecutive losses |
| Daily max loss | 5% of capital | Stop trading, review & reset |
| Max open trades | 3–5 simultaneously | Avoid correlation blowup |
| Stop-loss | Defined at entry | No discretionary exits |

**Position Sizing Formula:**
```
Position Size = Capital × 0.02
```

**⚡ Circuit Breaker** — Redis-backed kill switch halts all order placement the moment the daily loss limit is breached. Zero manual intervention required.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/signal/{symbol}` | Live trading signal for a symbol |
| `POST` | `/trade/{symbol}` | Place order via broker API |
| `GET` | `/pnl` | Current exposure & P&L |
| `WS` | `/ws/ticker` | Real-time tick stream (WebSocket) |

```python
# Example: Strategy Signal Endpoint
@app.post("/signal/{symbol}")
async def get_signal(symbol: str):
    data   = await fetch_option_chain(symbol)
    analytics = process_analytics(data)          # PCR, OI velocity, IV %
    ml_score  = await infer(analytics)           # ML confidence score
    signal    = generate_strategy(analytics, ml_score)
    return signal
```

---

## 🧪 Backtesting

| Component | Details |
|:---|:---|
| Historical data | OPSTRA / NSE archives (daily EOD) |
| Slippage model | 0.03–0.05% per leg minimum |
| Brokerage | Zerodha: ₹20/trade flat |
| Market regimes tested | Trending · Range-bound · Volatile |
| Key metrics | Sharpe ratio · Max drawdown · Win rate · Avg R |
| Validation method | Walk-Forward Optimization (WFO) |

---

## 🔬 Advanced Edge Signals

| Signal | Formula | Use |
|:---|:---|:---|
| OI Velocity | `dOI/dt` over 5-min bars | Detect institutional accumulation early |
| IV Skew | OTM Put IV − OTM Call IV | Market fear index; high = sell calls |
| Delta Imbalance | Net delta across all positions | Monitor directional exposure |
| Gamma Exposure | `Σ(Gamma × OI × 100)` | Predict price pinning near expiry |
| Max Pain | Strike magnet calculation | Expiry-week directional bias |

---

## ⚠️ Known Failure Points

- 🚨 **Bad data** — Stale or incorrect option chain → wrong signals → real losses
- ⏱️ **Latency** — Missed entries at target price; broker API timeouts
- 📉 **Overfitting** — Backtest looks perfect; live trading collapses
- 💸 **Ignoring costs** — Brokerage + slippage + STT eats all edge

---

## 🗓️ Build Roadmap

| Week | Module | Deliverable |
|:---:|:---|:---|
| Week 1 | 📦 Data Pipeline | NSE WebSocket → Kafka → Redis → TimescaleDB |
| Week 2 | 📊 Analytics Engine | PCR, OI Velocity, IV Percentile, Max Pain |
| Week 3 | 🌐 FastAPI + WebSocket | REST API, real-time tick push, JWT auth |
| Week 4 | 📈 Strategy + Backtester | Iron Condor, Momentum, WFO validation |
| Week 5 | 🤖 ML Signal Layer | LightGBM + LSTM + Meta-Ensemble |
| Week 6 | 🔒 Broker + Risk Engine | Order manager, circuit breaker, lifecycle hooks |

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/ronakrajput8882/nse-algo-trading.git
cd nse-algo-trading

# Start infrastructure (Redis · Kafka · TimescaleDB)
docker-compose up -d

# Install Python dependencies
pip install -r requirements.txt

# Configure environment
cp config/.env.example config/.env
# → Add broker API keys, DB URLs, Kafka bootstrap servers

# Run the API server
uvicorn api.main:app --reload
```

The API will be live at `http://localhost:8000` · Docs at `http://localhost:8000/docs`

---

## 🛠️ Tech Stack

| Tool | Use |
|:---|:---|
| Python 3.10+ | Core language |
| FastAPI | Async REST API + WebSocket server |
| React / Next.js | Frontend dashboard |
| Apache Kafka | High-throughput tick ingestion |
| Redis | Live caching, pub/sub, circuit breaker |
| TimescaleDB | Time-series persistence |
| LightGBM | Gradient-boosted ML signal |
| PyTorch | LSTM sequence model |
| scikit-learn | Feature scaling, meta-ensemble |
| Zerodha Kite | Primary broker API |
| Fyers v3 | Secondary broker API |
| Docker | Infrastructure orchestration |

---

## 🔍 Key Insights

- 🧠 **Kafka + Redis pipeline** ensures sub-100ms data availability from NSE tick to analytics output
- 📊 **PCR + OI Velocity together** provide stronger directional signals than either metric alone
- 🤖 **LSTM + LightGBM ensemble** outperforms single models on regime-changing market conditions
- ⚖️ **Iron Condor** is the primary edge — high IV environments on Nifty/BankNifty weekly expiries are frequent and exploitable
- 🔒 **Circuit Breaker** is non-negotiable — it is the difference between a bad day and a blown account
- 🎯 **WFO validation** is the only honest way to know if your backtest means anything

---

<div align="center">

### Connect with me

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://linkedin.com/in/ronakrajput8882)
[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://instagram.com/techwithronak)
[![GitHub](https://img.shields.io/badge/GitHub-100000?style=for-the-badge&logo=github&logoColor=white)](https://github.com/ronakrajput8882)

*If you found this useful, please ⭐ the repo!*

> **Remember:** You are not building a trading tool. You are building a probabilistic decision engine competing with institutions that have spent millions on infrastructure, data, and talent. Every shortcut you take will be exploited by the market.

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6,11,20&height=100&section=footer" width="100%"/>

</div>