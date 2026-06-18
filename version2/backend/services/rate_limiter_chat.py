"""Rate-limiting wrapper for chat endpoints.

Provides per-user rate limiting with token bucket algorithm.
Integrates with FastAPI middleware stack.
"""
import time
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket rate limiter (per-user, per-endpoint)."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: max tokens in bucket
            refill_rate: tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
    
    def allow_request(self) -> bool:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate
        )
        self.last_refill = now
        
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class ChatRateLimiter:
    """Per-user rate limiting for chat operations."""
    
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
    
    def is_allowed(self, user_id: str, endpoint: str, capacity: int = 30, refill_rate: float = 1.0) -> Tuple[bool, Dict]:
        """Check if request is allowed. Returns (allowed, metadata)."""
        key = f"{user_id}:{endpoint}"
        
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(capacity=capacity, refill_rate=refill_rate)
        
        bucket = self.buckets[key]
        allowed = bucket.allow_request()
        
        return allowed, {
            "user_id": user_id,
            "endpoint": endpoint,
            "remaining_tokens": int(bucket.tokens),
            "capacity": bucket.capacity,
        }


chat_rate_limiter = ChatRateLimiter()


def rate_limit_check(user_id: str, endpoint: str) -> Tuple[bool, Dict]:
    """Quick helper: check rate limit for user:endpoint."""
    # Defaults: 30 requests per 30 seconds per endpoint
    allowed, meta = chat_rate_limiter.is_allowed(user_id, endpoint, capacity=30, refill_rate=1.0)
    if not allowed:
        logger.warning(f"Rate limit exceeded for {user_id} on {endpoint}")
    return allowed, meta
