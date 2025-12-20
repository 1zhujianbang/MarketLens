"""
基础设施层 - 日志模块

提供统一的日志配置和管理。
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict


class LoggerManager:
    """统一日志管理器"""

    _loggers: Dict[str, logging.Logger] = {}
    _configured: bool = False
    _log_file: Optional[Path] = None

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取或创建配置好的logger

        Args:
            name: logger名称，通常使用 __name__

        Returns:
            配置好的logger实例
        """
        if not cls._configured:
            cls._configure_logging()

        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)

        return cls._loggers[name]

    @classmethod
    def _configure_logging(cls):
        """统一日志配置"""
        if cls._configured:
            return

        # 根日志器配置
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # 避免重复添加处理器
        if root_logger.handlers:
            cls._configured = True
            return

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # 文件处理器 (可选，延迟初始化)
        if cls._log_file:
            cls._add_file_handler_internal(cls._log_file, root_logger)

        cls._configured = True

    @classmethod
    def _add_file_handler_internal(cls, log_file: Path, logger: logging.Logger) -> None:
        """内部方法：添加文件处理器"""
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"文件日志配置失败: {e}")

    @classmethod
    def set_log_file(cls, log_file: Path) -> None:
        """设置日志文件路径"""
        cls._log_file = log_file
        if cls._configured:
            cls._add_file_handler_internal(log_file, logging.getLogger())

    @classmethod
    def set_level(cls, level: str) -> None:
        """设置全局日志级别"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }

        if level.upper() in level_map:
            logging.getLogger().setLevel(level_map[level.upper()])

    @classmethod
    def add_file_handler(cls, file_path: Path, level: str = 'INFO') -> None:
        """添加额外的文件处理器"""
        try:
            file_handler = logging.FileHandler(file_path, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)

            level_map = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL
            }
            file_handler.setLevel(level_map.get(level.upper(), logging.INFO))

            logging.getLogger().addHandler(file_handler)
        except Exception as e:
            logging.getLogger('LoggerManager').warning(f"添加文件处理器失败: {e}")

    @classmethod
    def get_all_loggers(cls) -> Dict[str, logging.Logger]:
        """获取所有已创建的logger（调试用）"""
        return cls._loggers.copy()

    @classmethod
    def reset(cls) -> None:
        """重置日志配置（测试用）"""
        cls._loggers.clear()
        cls._configured = False
        cls._log_file = None


# 快捷函数
def get_logger(name: str) -> logging.Logger:
    """获取日志器的快捷方法"""
    return LoggerManager.get_logger(name)


def set_log_level(level: str) -> None:
    """设置日志级别的快捷方法"""
    LoggerManager.set_level(level)
