from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "NSE Algo Trading"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # NSE / Market Data
    NSE_WS_URL: str = "wss://streamer.finance.yahoo.com"  # swap real feed
    NSE_API_KEY: str = ""
    MARKET_OPEN: str = "09:15"
    MARKET_CLOSE: str = "15:30"

    # Kafka
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TICK_TOPIC: str = "nse.ticks"
    KAFKA_OPTIONS_TOPIC: str = "nse.options"
    KAFKA_GROUP_ID: str = "algo-consumer"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    TICK_TTL: int = 86400          # 1 day
    ANALYTICS_TTL: int = 300       # 5 min

    # TimescaleDB
    DB_URL: str = "postgresql+asyncpg://algo:algo123@localhost:5432/nse_algo"
    DB_POOL_SIZE: int = 10

    # FastAPI
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]
    JWT_SECRET: str = "change-me-in-prod-please"
    JWT_EXPIRE_MINUTES: int = 60

    # Zerodha
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_ACCESS_TOKEN: str = ""

    # Fyers
    FYERS_APP_ID: str = ""
    FYERS_SECRET: str = ""
    FYERS_TOKEN: str = ""

    # Risk
    MAX_DAILY_LOSS: float = 10000.0
    MAX_POSITION_SIZE: int = 50
    MAX_OPEN_POSITIONS: int = 5
    MAX_ORDER_VALUE: float = 500000.0
    RISK_PER_TRADE_PCT: float = 0.02   # 2% per trade

    # ML
    MODEL_DIR: str = "ml/saved_models"
    FEATURE_WINDOW: int = 20
    PREDICTION_HORIZON: int = 5         # bars ahead

    # Watchlist
    SYMBOLS: List[str] = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()