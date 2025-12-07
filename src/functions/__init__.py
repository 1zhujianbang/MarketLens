# 自动导入所有子模块以确保工具被注册
import pkgutil
import importlib

__all__ = []

# 动态导入当前目录下的所有模块
for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
    importlib.import_module(f".{module_name}", __package__)

