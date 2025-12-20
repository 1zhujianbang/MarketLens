"""
LLM Client 端口（Port）：
定义 LLM 调用的抽象接口，包括限速、熔断等能力。

适配器层实现具体的 OpenAI/Kimi/Aliyun 等提供商。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


# =============================================================================
# 配置与参数
# =============================================================================


class LLMProviderType(Enum):
    """LLM 提供商类型"""
    OPENAI = "openai"
    KIMI = "kimi"
    ALIYUN = "aliyun"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


@dataclass
class LLMCallConfig:
    """LLM 调用配置"""
    model: str = ""
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout_seconds: int = 120
    retries: int = 3
    retry_delay_seconds: float = 1.0


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str = ""
    model: str = ""
    provider: LLMProviderType = LLMProviderType.OPENAI
    usage: Dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens
    latency_ms: float = 0.0
    raw_response: Optional[Any] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and self.content != ""


# =============================================================================
# 限速器接口
# =============================================================================


class RateLimiter(ABC):
    """限速器抽象接口"""

    @abstractmethod
    def acquire(self) -> None:
        """同步获取令牌（阻塞直到可用）"""
        ...

    @abstractmethod
    async def acquire_async(self) -> None:
        """异步获取令牌"""
        ...

    @abstractmethod
    def try_acquire(self) -> bool:
        """尝试获取令牌（非阻塞，返回是否成功）"""
        ...


# =============================================================================
# 熔断器接口
# =============================================================================


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常工作
    OPEN = "open"  # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 半开，尝试恢复


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5  # 连续失败次数阈值
    recovery_timeout_seconds: float = 60.0  # 熔断后恢复尝试时间
    half_open_max_calls: int = 3  # 半开状态最大尝试次数


class CircuitBreaker(ABC):
    """熔断器抽象接口"""

    @property
    @abstractmethod
    def state(self) -> CircuitState:
        """获取当前状态"""
        ...

    @abstractmethod
    def can_call(self) -> bool:
        """是否允许调用"""
        ...

    @abstractmethod
    def record_success(self) -> None:
        """记录成功调用"""
        ...

    @abstractmethod
    def record_failure(self) -> None:
        """记录失败调用"""
        ...

    @abstractmethod
    def reset(self) -> None:
        """重置熔断器"""
        ...


# =============================================================================
# LLM Client 端口（主接口）
# =============================================================================


class LLMClient(ABC):
    """
    LLM 客户端端口：
    - call: 同步调用
    - call_async: 异步调用
    - call_with_retry: 带重试的调用
    - 内置限速和熔断支持
    """

    @property
    @abstractmethod
    def provider(self) -> LLMProviderType:
        """获取提供商类型"""
        ...

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """获取可用模型列表"""
        ...

    @abstractmethod
    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        """
        同步调用 LLM。
        
        Args:
            prompt: 提示词
            config: 调用配置
            
        Returns:
            LLMResponse
        """
        ...

    @abstractmethod
    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
    ) -> LLMResponse:
        """
        异步调用 LLM。
        
        Args:
            prompt: 提示词
            config: 调用配置
            
        Returns:
            LLMResponse
        """
        ...

    @abstractmethod
    def call_with_retry(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        max_retries: int = 3,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> LLMResponse:
        """
        带重试的调用。
        
        Args:
            prompt: 提示词
            config: 调用配置
            max_retries: 最大重试次数
            on_retry: 重试回调
            
        Returns:
            LLMResponse
        """
        ...

    @abstractmethod
    def set_rate_limiter(self, limiter: RateLimiter) -> None:
        """设置限速器"""
        ...

    @abstractmethod
    def set_circuit_breaker(self, breaker: CircuitBreaker) -> None:
        """设置熔断器"""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        ...


# =============================================================================
# LLM Pool（多提供商池）
# =============================================================================


class LLMClientPool(ABC):
    """
    LLM 客户端池：
    支持多个提供商，自动选择可用的客户端。
    """

    @abstractmethod
    def add_client(self, client: LLMClient) -> None:
        """添加客户端"""
        ...

    @abstractmethod
    def remove_client(self, provider: LLMProviderType) -> None:
        """移除客户端"""
        ...

    @abstractmethod
    def get_client(self, provider: Optional[LLMProviderType] = None) -> Optional[LLMClient]:
        """
        获取客户端。
        
        Args:
            provider: 指定提供商，None 则自动选择
            
        Returns:
            可用的 LLMClient，或 None
        """
        ...

    @abstractmethod
    def call(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        preferred_provider: Optional[LLMProviderType] = None,
    ) -> LLMResponse:
        """
        通过池调用 LLM（自动故障转移）。
        
        Args:
            prompt: 提示词
            config: 调用配置
            preferred_provider: 优先使用的提供商
            
        Returns:
            LLMResponse
        """
        ...

    @abstractmethod
    async def call_async(
        self,
        prompt: str,
        config: Optional[LLMCallConfig] = None,
        preferred_provider: Optional[LLMProviderType] = None,
    ) -> LLMResponse:
        """异步调用"""
        ...

    @abstractmethod
    def list_available(self) -> List[LLMProviderType]:
        """列出可用的提供商"""
        ...
