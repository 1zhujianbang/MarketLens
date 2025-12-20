"""
LLM 适配器实现。

提供对各种 LLM 提供商的适配：
- OpenAI (GPT-4, GPT-3.5-turbo)
- Kimi (Moonshot)
- Aliyun (通义千问)
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ...ports.llm_client import (
    CircuitBreaker,
    LLMCallConfig,
    LLMClient,
    LLMClientPool,
    LLMProviderType,
    LLMResponse,
    RateLimiter,
)
from ...infra import (
    TokenBucketRateLimiter,
    SimpleCircuitBreaker,
    utc_now_iso,
)


# =============================================================================
# OpenAI 适配器
# =============================================================================


class OpenAIAdapter(LLMClient):
    """OpenAI LLM 适配器"""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: str = "gpt-4o-mini",
        organization: Optional[str] = None,
    ):
        self._api_key = api_key
        self._base_url = base_url or "https://api.openai.com/v1"
        self._default_model = default_model
        self._organization = organization
        self._rate_limiter: Optional[RateLimiter] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    organization=self._organization,
                )
            except ImportError:
                raise RuntimeError("openai package not installed")

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.OPENAI

    @property
    def available_models(self) -> List[str]:
        return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]

    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        self._ensure_client()
        cfg = config or LLMCallConfig()
        model = cfg.model or self._default_model

        # 熔断检查
        if self._circuit_breaker and not self._circuit_breaker.can_call():
            return LLMResponse(error="Circuit breaker is open")

        # 限速
        if self._rate_limiter:
            self._rate_limiter.acquire()

        start_time = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                timeout=cfg.timeout_seconds,
            )
            latency = (time.monotonic() - start_time) * 1000

            content = response.choices[0].message.content if response.choices else ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            if self._circuit_breaker:
                self._circuit_breaker.record_success()

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider,
                usage=usage,
                latency_ms=latency,
                raw_response=response,
            )
        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            return LLMResponse(error=str(e))

    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        # 简单实现：在线程池中运行同步调用
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.call, prompt, config)

    def call_with_retry(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        max_retries: int = 3,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> LLMResponse:
        cfg = config or LLMCallConfig()
        last_error = None
        for attempt in range(max_retries + 1):
            result = self.call(prompt, cfg)
            if result.success:
                return result
            last_error = Exception(result.error)
            if attempt < max_retries:
                delay = cfg.retry_delay_seconds * (2 ** attempt)
                if on_retry:
                    on_retry(attempt + 1, last_error)
                time.sleep(delay)
        return LLMResponse(error=f"All retries failed: {last_error}")

    def set_rate_limiter(self, limiter: RateLimiter) -> None:
        self._rate_limiter = limiter

    def set_circuit_breaker(self, breaker: CircuitBreaker) -> None:
        self._circuit_breaker = breaker

    def health_check(self) -> bool:
        try:
            result = self.call("ping", LLMCallConfig(max_tokens=5, timeout_seconds=10))
            return result.success
        except Exception:
            return False


# =============================================================================
# Kimi (Moonshot) 适配器
# =============================================================================


class KimiAdapter(LLMClient):
    """Kimi (Moonshot) LLM 适配器"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.moonshot.cn/v1",
        default_model: str = "moonshot-v1-8k",
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = default_model
        self._rate_limiter: Optional[RateLimiter] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                raise RuntimeError("openai package not installed")

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.KIMI

    @property
    def available_models(self) -> List[str]:
        return ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]

    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        self._ensure_client()
        cfg = config or LLMCallConfig()
        model = cfg.model or self._default_model

        if self._circuit_breaker and not self._circuit_breaker.can_call():
            return LLMResponse(error="Circuit breaker is open")

        if self._rate_limiter:
            self._rate_limiter.acquire()

        start_time = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                timeout=cfg.timeout_seconds,
            )
            latency = (time.monotonic() - start_time) * 1000

            content = response.choices[0].message.content if response.choices else ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            if self._circuit_breaker:
                self._circuit_breaker.record_success()

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider,
                usage=usage,
                latency_ms=latency,
            )
        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            return LLMResponse(error=str(e))

    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.call, prompt, config)

    def call_with_retry(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        max_retries: int = 3,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> LLMResponse:
        cfg = config or LLMCallConfig()
        last_error = None
        for attempt in range(max_retries + 1):
            result = self.call(prompt, cfg)
            if result.success:
                return result
            last_error = Exception(result.error)
            if attempt < max_retries:
                delay = cfg.retry_delay_seconds * (2 ** attempt)
                if on_retry:
                    on_retry(attempt + 1, last_error)
                time.sleep(delay)
        return LLMResponse(error=f"All retries failed: {last_error}")

    def set_rate_limiter(self, limiter: RateLimiter) -> None:
        self._rate_limiter = limiter

    def set_circuit_breaker(self, breaker: CircuitBreaker) -> None:
        self._circuit_breaker = breaker

    def health_check(self) -> bool:
        try:
            result = self.call("ping", LLMCallConfig(max_tokens=5, timeout_seconds=10))
            return result.success
        except Exception:
            return False


# =============================================================================
# Aliyun (通义千问) 适配器
# =============================================================================


class AliyunAdapter(LLMClient):
    """Aliyun 通义千问 LLM 适配器"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model: str = "qwen-plus",
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = default_model
        self._rate_limiter: Optional[RateLimiter] = None
        self._circuit_breaker: Optional[CircuitBreaker] = None
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                raise RuntimeError("openai package not installed")

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.ALIYUN

    @property
    def available_models(self) -> List[str]:
        return ["qwen-plus", "qwen-turbo", "qwen-max"]

    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        self._ensure_client()
        cfg = config or LLMCallConfig()
        model = cfg.model or self._default_model

        if self._circuit_breaker and not self._circuit_breaker.can_call():
            return LLMResponse(error="Circuit breaker is open")

        if self._rate_limiter:
            self._rate_limiter.acquire()

        start_time = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=cfg.max_tokens,
                temperature=cfg.temperature,
                timeout=cfg.timeout_seconds,
            )
            latency = (time.monotonic() - start_time) * 1000

            content = response.choices[0].message.content if response.choices else ""
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            }

            if self._circuit_breaker:
                self._circuit_breaker.record_success()

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider,
                usage=usage,
                latency_ms=latency,
            )
        except Exception as e:
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            return LLMResponse(error=str(e))

    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.call, prompt, config)

    def call_with_retry(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        max_retries: int = 3,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> LLMResponse:
        cfg = config or LLMCallConfig()
        last_error = None
        for attempt in range(max_retries + 1):
            result = self.call(prompt, cfg)
            if result.success:
                return result
            last_error = Exception(result.error)
            if attempt < max_retries:
                delay = cfg.retry_delay_seconds * (2 ** attempt)
                if on_retry:
                    on_retry(attempt + 1, last_error)
                time.sleep(delay)
        return LLMResponse(error=f"All retries failed: {last_error}")

    def set_rate_limiter(self, limiter: RateLimiter) -> None:
        self._rate_limiter = limiter

    def set_circuit_breaker(self, breaker: CircuitBreaker) -> None:
        self._circuit_breaker = breaker

    def health_check(self) -> bool:
        try:
            result = self.call("ping", LLMCallConfig(max_tokens=5, timeout_seconds=10))
            return result.success
        except Exception:
            return False


# =============================================================================
# LLM 客户端池实现
# =============================================================================


class DefaultLLMClientPool(LLMClientPool):
    """默认 LLM 客户端池实现"""

    def __init__(self):
        self._clients: Dict[LLMProviderType, LLMClient] = {}
        self._lock = threading.Lock()
        self._priority: List[LLMProviderType] = [
            LLMProviderType.OPENAI,
            LLMProviderType.KIMI,
            LLMProviderType.ALIYUN,
        ]

    def add_client(self, client: LLMClient) -> None:
        with self._lock:
            self._clients[client.provider] = client

    def remove_client(self, provider: LLMProviderType) -> None:
        with self._lock:
            self._clients.pop(provider, None)

    def get_client(self, provider: Optional[LLMProviderType] = None) -> Optional[LLMClient]:
        with self._lock:
            if provider:
                return self._clients.get(provider)
            # 按优先级返回第一个可用的
            for p in self._priority:
                client = self._clients.get(p)
                if client and client.health_check():
                    return client
            # 返回任意一个
            for client in self._clients.values():
                return client
            return None

    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        preferred_provider: Optional[LLMProviderType] = None,
    ) -> LLMResponse:
        # 尝试首选提供商
        if preferred_provider:
            client = self.get_client(preferred_provider)
            if client:
                result = client.call(prompt, config)
                if result.success:
                    return result

        # 故障转移：尝试其他提供商
        with self._lock:
            providers = list(self._clients.keys())

        for provider in providers:
            if provider == preferred_provider:
                continue
            client = self.get_client(provider)
            if client:
                result = client.call(prompt, config)
                if result.success:
                    return result

        return LLMResponse(error="All LLM providers failed")

    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        preferred_provider: Optional[LLMProviderType] = None,
    ) -> LLMResponse:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.call, prompt, config, preferred_provider
        )

    def list_available(self) -> List[LLMProviderType]:
        with self._lock:
            return list(self._clients.keys())


# =============================================================================
# 工厂函数
# =============================================================================


def create_llm_client(
    provider: LLMProviderType,
    api_key: str,
    base_url: Optional[str] = None,
    default_model: Optional[str] = None,
    rate_limit_per_sec: float = 1.0,
    enable_circuit_breaker: bool = True,
) -> LLMClient:
    """
    创建 LLM 客户端。
    
    Args:
        provider: 提供商类型
        api_key: API 密钥
        base_url: 自定义 API 地址
        default_model: 默认模型
        rate_limit_per_sec: 每秒请求限制
        enable_circuit_breaker: 是否启用熔断器
        
    Returns:
        LLMClient 实例
    """
    if provider == LLMProviderType.OPENAI:
        client = OpenAIAdapter(
            api_key=api_key,
            base_url=base_url,
            default_model=default_model or "gpt-4o-mini",
        )
    elif provider == LLMProviderType.KIMI:
        client = KimiAdapter(
            api_key=api_key,
            base_url=base_url or "https://api.moonshot.cn/v1",
            default_model=default_model or "moonshot-v1-8k",
        )
    elif provider == LLMProviderType.ALIYUN:
        client = AliyunAdapter(
            api_key=api_key,
            base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model=default_model or "qwen-plus",
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # 配置限速器
    if rate_limit_per_sec > 0:
        client.set_rate_limiter(TokenBucketRateLimiter(rate_limit_per_sec))

    # 配置熔断器
    if enable_circuit_breaker:
        client.set_circuit_breaker(SimpleCircuitBreaker())

    return client
