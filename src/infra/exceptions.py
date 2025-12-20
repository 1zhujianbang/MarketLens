"""
基础设施层 - 异常模块

定义标准异常类和错误处理机制。
"""

from typing import Any, Dict, Optional
from functools import wraps


class NewsAgentException(Exception):
    """新闻智能体基础异常类"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details
        }


class ConfigError(NewsAgentException):
    """配置相关错误"""
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "CONFIG_ERROR", {"config_key": config_key, **kwargs})


class ValidationError(NewsAgentException):
    """数据验证错误"""
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None, **kwargs) -> None:
        super().__init__(message, "VALIDATION_ERROR", {"field": field, "value": value, **kwargs})


class NetworkError(NewsAgentException):
    """网络相关错误"""
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None, **kwargs) -> None:
        super().__init__(message, "NETWORK_ERROR", {"url": url, "status_code": status_code, **kwargs})


class APIError(NewsAgentException):
    """API调用错误"""
    def __init__(self, message: str, api_name: Optional[str] = None, response: Any = None, **kwargs) -> None:
        super().__init__(message, "API_ERROR", {"api_name": api_name, "response": response, **kwargs})


class ProcessingError(NewsAgentException):
    """数据处理错误"""
    def __init__(self, message: str, data_type: Optional[str] = None, data_id: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "PROCESSING_ERROR", {"data_type": data_type, "data_id": data_id, **kwargs})


class FileOperationError(NewsAgentException):
    """文件操作错误"""
    def __init__(self, message: str, file_path: Optional[str] = None, operation: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "FILE_ERROR", {"file_path": file_path, "operation": operation, **kwargs})


class ConcurrencyError(NewsAgentException):
    """并发处理错误"""
    def __init__(self, message: str, task_count: Optional[int] = None, max_workers: Optional[int] = None, **kwargs) -> None:
        super().__init__(message, "CONCURRENCY_ERROR", {"task_count": task_count, "max_workers": max_workers, **kwargs})


class LLMError(NewsAgentException):
    """LLM 调用错误"""
    def __init__(self, message: str, provider: Optional[str] = None, model: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "LLM_ERROR", {"provider": provider, "model": model, **kwargs})


class CircuitBreakerOpenError(NewsAgentException):
    """熔断器打开错误"""
    def __init__(self, message: str = "Circuit breaker is open", **kwargs) -> None:
        super().__init__(message, "CIRCUIT_BREAKER_OPEN", kwargs)


class RateLimitExceededError(NewsAgentException):
    """速率限制超出错误"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: Optional[float] = None, **kwargs) -> None:
        super().__init__(message, "RATE_LIMIT_EXCEEDED", {"retry_after": retry_after, **kwargs})


class StoreError(NewsAgentException):
    """存储操作错误"""
    def __init__(self, message: str, operation: Optional[str] = None, entity_type: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "STORE_ERROR", {"operation": operation, "entity_type": entity_type, **kwargs})


class MigrationError(NewsAgentException):
    """数据迁移错误"""
    def __init__(self, message: str, from_version: Optional[str] = None, to_version: Optional[str] = None, **kwargs) -> None:
        super().__init__(message, "MIGRATION_ERROR", {"from_version": from_version, "to_version": to_version, **kwargs})


# =============================================================================
# 错误处理装饰器
# =============================================================================

def handle_errors(logger=None):
    """
    统一错误处理装饰器

    Args:
        logger: 日志记录器，如果不提供则使用默认日志器
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _logger = logger
            if _logger is None:
                from .logging import get_logger
                _logger = get_logger(__name__)
            try:
                return func(*args, **kwargs)
            except NewsAgentException as e:
                _logger.error(f"业务异常 [{e.error_code}]: {e.message}", extra=e.details)
                raise
            except Exception as e:
                # 未知异常转换为ProcessingError
                error = ProcessingError(f"未知错误: {str(e)}", data_type="unknown")
                _logger.error(f"未处理异常: {str(e)}", exc_info=True)
                raise error from e
        return wrapper
    return decorator


def handle_async_errors(logger=None):
    """
    异步版本的统一错误处理装饰器
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            _logger = logger
            if _logger is None:
                from .logging import get_logger
                _logger = get_logger(__name__)
            try:
                return await func(*args, **kwargs)
            except NewsAgentException as e:
                _logger.error(f"异步业务异常 [{e.error_code}]: {e.message}", extra=e.details)
                raise
            except Exception as e:
                # 未知异常转换为ProcessingError
                error = ProcessingError(f"异步未知错误: {str(e)}", data_type="unknown")
                _logger.error(f"异步未处理异常: {str(e)}", exc_info=True)
                raise error from e
        return wrapper
    return decorator


class ErrorHandler:
    """错误处理工具类"""

    def __init__(self, logger=None):
        if logger is None:
            from .logging import get_logger
            logger = get_logger(__name__)
        self.logger = logger

    def handle_and_log(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """
        处理并记录错误

        Args:
            error: 异常对象
            context: 错误上下文信息
        """
        context = context or {}

        if isinstance(error, NewsAgentException):
            self.logger.error(f"业务异常 [{error.error_code}]: {error.message}",
                            extra={**error.details, **context})
        else:
            self.logger.error(f"系统异常: {str(error)}", extra=context, exc_info=True)

    def create_error_response(self, error: Exception) -> Dict[str, Any]:
        """
        创建错误响应

        Args:
            error: 异常对象

        Returns:
            错误响应字典
        """
        if isinstance(error, NewsAgentException):
            return {
                "success": False,
                "error": error.to_dict()
            }
        else:
            return {
                "success": False,
                "error": {
                    "error_code": "SYSTEM_ERROR",
                    "message": "系统内部错误",
                    "details": {"original_error": str(error)}
                }
            }
