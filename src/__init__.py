"""
src 包入口（轻量 + 懒加载）。

原则：
- import src 不应触发 agents/functions/utils/core 的重型初始化
- 需要某个子包时再显式 import（或通过 __getattr__ 访问）
"""

from __future__ import annotations

from typing import Any

__version__ = "2.0.0"

_LAZY_SUBPACKAGES = {"agents", "functions", "utils", "core", "storage", "web", "app"}


def __getattr__(name: str) -> Any:  # PEP 562
    if name in _LAZY_SUBPACKAGES:
        import importlib

        m = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = m  # cache
        return m
    raise AttributeError(name)


__all__ = ["__version__", *_LAZY_SUBPACKAGES]
