"""
Auth — JWT creation/validation + Redis rate limiting
"""
import time
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from config.settings import settings

ALGORITHM = "HS256"
security = HTTPBearer()


# ── Token ─────────────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    sub: str
    exp: float
    role: str = "trader"


def create_access_token(subject: str, role: str = "trader") -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire, "role": role}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


# ── Rate limiter ──────────────────────────────────────────────────────────────

async def rate_limit(
    request: Request,
    limit: int = 60,
    window: int = 60,
) -> None:
    """Sliding window rate limit using Redis."""
    redis: aioredis.Redis = request.app.state.redis
    client_ip = request.client.host
    key = f"rate:{client_ip}:{request.url.path}"
    now = time.time()

    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, now - window)
    pipe.zadd(key, {str(now): now})
    pipe.zcard(key)
    pipe.expire(key, window)
    results = await pipe.execute()
    count = results[2]

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} req/{window}s",
            headers={"Retry-After": str(window)},
        )


# ── Dependency ────────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    return decode_token(credentials.credentials)


async def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user