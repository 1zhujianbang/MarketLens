"""
基础设施层（Infrastructure Layer）。

提供通用基础能力：
- clock: 统一时间管理
- id_factory: ID 生成与规范化
- migration: Schema 版本管理
- retry: 重试策略
- logging: 日志工具
"""
from __future__ import annotations

import hashlib
import time
import threading
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, List


# =============================================================================
# Clock（统一时间）
# =============================================================================


class Clock(ABC):
    """时间服务抽象接口"""

    @abstractmethod
    def now(self) -> datetime:
        """获取当前 UTC 时间"""
        ...

    @abstractmethod
    def now_iso(self) -> str:
        """获取当前 UTC 时间的 ISO 格式字符串"""
        ...

    @abstractmethod
    def parse_iso(self, val: str) -> Optional[datetime]:
        """解析 ISO 格式时间字符串"""
        ...

    @abstractmethod
    def format_iso(self, dt: datetime) -> str:
        """格式化为 ISO 字符串"""
        ...


class SystemClock(Clock):
    """系统时钟实现"""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def now_iso(self) -> str:
        return self.now().isoformat()

    def parse_iso(self, val: str) -> Optional[datetime]:
        if not val:
            return None
        try:
            dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def format_iso(self, dt: datetime) -> str:
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class MockClock(Clock):
    """测试用模拟时钟"""

    def __init__(self, fixed_time: Optional[datetime] = None):
        self._fixed_time = fixed_time or datetime(2024, 1, 1, tzinfo=timezone.utc)
        self._offset = timedelta()

    def now(self) -> datetime:
        return self._fixed_time + self._offset

    def now_iso(self) -> str:
        return self.now().isoformat()

    def parse_iso(self, val: str) -> Optional[datetime]:
        if not val:
            return None
        try:
            dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def format_iso(self, dt: datetime) -> str:
        if dt is None:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def advance(self, delta: timedelta) -> None:
        """推进时间"""
        self._offset += delta

    def set_time(self, dt: datetime) -> None:
        """设置固定时间"""
        self._fixed_time = dt
        self._offset = timedelta()


# 全局时钟实例（可替换为 MockClock 用于测试）
_clock_instance: Clock = SystemClock()
_clock_lock = threading.Lock()


def get_clock() -> Clock:
    """获取全局时钟实例"""
    return _clock_instance


def set_clock(clock: Clock) -> None:
    """设置全局时钟实例（用于测试）"""
    global _clock_instance
    with _clock_lock:
        _clock_instance = clock


def utc_now() -> datetime:
    """快捷方法：获取当前 UTC 时间"""
    return get_clock().now()


def utc_now_iso() -> str:
    """快捷方法：获取当前 UTC 时间的 ISO 字符串"""
    return get_clock().now_iso()


def parse_iso(val: str) -> Optional[datetime]:
    """快捷方法：解析 ISO 时间"""
    return get_clock().parse_iso(val)


# =============================================================================
# IdFactory（ID 生成与规范化）
# =============================================================================


class IdFactory:
    """ID 工厂：生成和规范化 ID"""

    @staticmethod
    def sha1(text: str) -> str:
        """计算 SHA1 哈希"""
        return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

    @staticmethod
    def entity_id(entity_name: str) -> str:
        """
        生成规范化实体 ID。
        格式：sha1("ent:<normalized_name>")
        """
        name = (entity_name or "").strip()
        return IdFactory.sha1(f"ent:{name}")

    @staticmethod
    def event_id(abstract: str) -> str:
        """
        生成规范化事件 ID。
        格式：sha1("evt:<abstract>")
        """
        a = (abstract or "").strip()
        return IdFactory.sha1(f"evt:{a}")

    @staticmethod
    def mention_id(text: str, source_id: str, timestamp: str) -> str:
        """
        生成提及 ID。
        格式：sha1("mention:<text>:<source_id>:<timestamp>")
        """
        return IdFactory.sha1(f"mention:{text}:{source_id}:{timestamp}")

    @staticmethod
    def run_id() -> str:
        """
        生成运行 ID。
        格式：run_<timestamp>_<random>
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        rand = hashlib.sha1(str(random.random()).encode()).hexdigest()[:8]
        return f"run_{ts}_{rand}"

    @staticmethod
    def decision_hash(payload: dict) -> str:
        """
        生成决策输入哈希（用于去重）。
        """
        import json
        normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return IdFactory.sha1(normalized)

    @staticmethod
    def normalize_name(name: str) -> str:
        """
        规范化名称（用于比较/索引）。
        """
        s = (name or "").strip().lower()
        for ch in [" ", "\t", "\n", "\r", "·", "•", "-", "_", ".", ",",
                   "，", "。", "（", "）", "(", ")", "[", "]", "{", "}", "\"", "'"]:
            s = s.replace(ch, "")
        return s


# =============================================================================
# Migration（Schema 版本管理）
# =============================================================================


@dataclass
class MigrationRecord:
    """迁移记录"""
    version: str
    description: str
    applied_at: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None


class MigrationManager(ABC):
    """
    Schema 迁移管理器抽象接口。
    """

    @abstractmethod
    def get_current_version(self) -> str:
        """获取当前 schema 版本"""
        ...

    @abstractmethod
    def get_pending_migrations(self) -> List[str]:
        """获取待执行的迁移版本"""
        ...

    @abstractmethod
    def apply_migration(self, version: str) -> MigrationRecord:
        """应用迁移"""
        ...

    @abstractmethod
    def apply_all_pending(self) -> List[MigrationRecord]:
        """应用所有待执行迁移"""
        ...

    @abstractmethod
    def rollback(self, version: str) -> MigrationRecord:
        """回滚到指定版本"""
        ...

    @abstractmethod
    def list_applied(self) -> List[MigrationRecord]:
        """列出已应用的迁移"""
        ...


# =============================================================================
# Retry（重试策略）
# =============================================================================


class RetryStrategy(Enum):
    """重试策略类型"""
    FIXED = "fixed"  # 固定间隔
    EXPONENTIAL = "exponential"  # 指数退避
    JITTER = "jitter"  # 带抖动的指数退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retryable_exceptions: tuple = (Exception,)


T = TypeVar("T")


def retry_with_backoff(
    config: RetryConfig,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    重试装饰器。
    
    Args:
        config: 重试配置
        on_retry: 重试回调（接收重试次数和异常）
        
    Returns:
        装饰器
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt < config.max_retries:
                        delay = _calculate_delay(attempt, config)
                        if on_retry:
                            on_retry(attempt + 1, e)
                        time.sleep(delay)
                    else:
                        raise
            raise last_exception  # 不应该到达这里
        return wrapper
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """计算重试延迟"""
    if config.strategy == RetryStrategy.FIXED:
        delay = config.base_delay_seconds
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay_seconds * (2 ** attempt)
    else:  # JITTER
        delay = config.base_delay_seconds * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.5)
        delay += jitter
    return min(delay, config.max_delay_seconds)


async def retry_async(
    func: Callable[..., Any],
    config: RetryConfig,
    *args: Any,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
    **kwargs: Any,
) -> Any:
    """
    异步重试函数。
    """
    import asyncio
    last_exception: Optional[Exception] = None
    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except config.retryable_exceptions as e:
            last_exception = e
            if attempt < config.max_retries:
                delay = _calculate_delay(attempt, config)
                if on_retry:
                    on_retry(attempt + 1, e)
                await asyncio.sleep(delay)
            else:
                raise
    raise last_exception


# =============================================================================
# Token Bucket Rate Limiter（令牌桶限速器）
# =============================================================================


class TokenBucketRateLimiter:
    """令牌桶限速器实现"""

    def __init__(self, rate_per_second: float, burst_size: Optional[int] = None):
        self.rate = rate_per_second
        self.burst_size = burst_size or max(1, int(rate_per_second))
        self._tokens = float(self.burst_size)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """补充令牌"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        new_tokens = elapsed * self.rate
        self._tokens = min(self.burst_size, self._tokens + new_tokens)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> None:
        """获取令牌（阻塞）"""
        with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # 计算需要等待的时间
                wait_time = (tokens - self._tokens) / self.rate
                self._lock.release()
                time.sleep(wait_time)
                self._lock.acquire()

    def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌（非阻塞）"""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def acquire_async(self, tokens: int = 1) -> None:
        """异步获取令牌"""
        import asyncio
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                wait_time = (tokens - self._tokens) / self.rate
            await asyncio.sleep(wait_time)


# =============================================================================
# Simple Circuit Breaker（简单熔断器）
# =============================================================================


class SimpleCircuitBreaker:
    """简单熔断器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._state = "closed"
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            self._check_recovery()
            return self._state

    def _check_recovery(self) -> None:
        """检查是否应该从 open 转为 half_open"""
        if self._state == "open" and self._last_failure_time:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
                self._half_open_calls = 0

    def can_call(self) -> bool:
        with self._lock:
            self._check_recovery()
            if self._state == "closed":
                return True
            if self._state == "half_open":
                return self._half_open_calls < self.half_open_max_calls
            return False  # open

    def record_success(self) -> None:
        with self._lock:
            self._success_count += 1
            if self._state == "half_open":
                self._half_open_calls += 1
                # 半开状态成功，恢复为 closed
                self._state = "closed"
                self._failure_count = 0
            elif self._state == "closed":
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == "half_open":
                # 半开状态失败，重新熔断
                self._state = "open"
            elif self._state == "closed":
                if self._failure_count >= self.failure_threshold:
                    self._state = "open"

    def reset(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_failure_time = None
