"""
Unit tests for KeyManager - Secure API Key Management

Note: KeyManager uses singleton pattern, so tests use direct instantiation
with different key_store_path to avoid interference.
"""

import pytest
import tempfile
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# 导入模块以访问类
import src.infra.key_manager as key_manager_module


def create_test_key_manager(key_store_path: Path, master_key: str):
    """
    创建用于测试的 KeyManager 实例
    
    由于 KeyManager 使用 singleton 装饰器，我们需要绕过它来创建独立实例。
    这里通过直接调用类的 __init__ 方法来实现。
    """
    # 获取被 singleton 装饰器包装的原始类
    # singleton 装饰器返回 get_instance 函数，该函数闭包中有原始类
    wrapped_func = key_manager_module.KeyManager
    
    # 创建一个空对象并手动调用 __init__
    # 首先，我们需要获取原始类
    # 由于 singleton 使用 instances[cls] = cls(*args, **kwargs)
    # 我们可以通过传入不同参数使其创建新实例（虽然会复用）
    # 更好的方式：使用 mock 来重置 singleton
    
    # 实际上，由于 KeyManager.__init__ 接受 master_key 参数，
    # 传入 master_key 可以避免调用 _get_master_key()
    # singleton 会基于类返回同一实例，但我们使用 master_key 参数
    return wrapped_func(key_store_path=key_store_path, master_key=master_key)


class TestKeyManager:
    """测试密钥管理器"""

    def setup_method(self):
        """每个测试前的设置"""
        # 使用临时文件作为密钥存储
        self.temp_dir = Path(tempfile.mkdtemp())
        self.key_store_path = self.temp_dir / ".key_store.enc"

        # 使用固定的主密钥进行测试
        self.master_key = "test_master_key_12345678901234567890123456789012"

        # 确保目录存在
        self.key_store_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 获取或创建 KeyManager 实例
        # 由于 singleton 模式，第一次调用会创建实例，后续调用返回同一实例
        # 但我们可以通过手动更新实例属性来"重置"状态
        self.km = create_test_key_manager(self.key_store_path, self.master_key)
        
        # 更新实例的存储路径和重新初始化（模拟新实例）
        self.km.key_store_path = self.key_store_path
        self.km.master_key = self.master_key
        self.km.fernet = self.km._derive_key(self.master_key)
        self.km._key_cache = {}
        self.km._cache_loaded = False
        self.km._ensure_key_store()

    def teardown_method(self):
        """每个测试后的清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_key_manager_initialization(self):
        """测试密钥管理器初始化"""
        # 检查是否创建了存储文件
        assert self.key_store_path.exists()
        assert self.km.fernet is not None

    def test_store_and_get_api_key(self):
        """测试存储和获取API密钥"""
        # 确保存储文件已创建
        assert self.key_store_path.exists()

        # 存储API密钥
        service_name = "test_openai"
        api_key = "sk-test1234567890abcdef"
        metadata = {"model": "gpt-4", "base_url": "https://api.openai.com/v1"}

        self.km.store_api_key(service_name, api_key, metadata)

        # 获取API密钥
        retrieved_key = self.km.get_api_key(service_name)
        assert retrieved_key == api_key

        # 检查元数据
        key_info = self.km.get_key_info(service_name)
        assert key_info is not None
        assert key_info["metadata"]["model"] == "gpt-4"
        assert "encrypted_key" not in key_info  # 确保不返回加密密钥

    def test_delete_api_key(self):
        """测试删除API密钥"""
        # 存储然后删除
        service_name = "test_service_del"
        api_key = "test_key_123"

        self.km.store_api_key(service_name, api_key)
        assert self.km.get_api_key(service_name) == api_key

        # 删除
        result = self.km.delete_api_key(service_name)
        assert result is True

        # 确认已删除
        assert self.km.get_api_key(service_name) is None

    def test_list_services(self):
        """测试列出服务"""
        # 清空之前的服务
        initial_services = self.km.list_services()
        for svc in initial_services:
            self.km.delete_api_key(svc)
        
        # 存储多个服务
        services = {
            "openai_test": "sk-openai123",
            "anthropic_test": "sk-anthropic456",
            "google_test": "sk-google789"
        }

        for name, key in services.items():
            self.km.store_api_key(name, key)

        # 列出服务
        service_list = self.km.list_services()
        assert len(service_list) >= 3
        assert "openai_test" in service_list
        assert "anthropic_test" in service_list
        assert "google_test" in service_list

    def test_rotate_master_key(self):
        """测试轮换主密钥"""
        # 存储测试密钥
        service_name = "test_rotate"
        api_key = "original_key_123"

        self.km.store_api_key(service_name, api_key)
        assert self.km.get_api_key(service_name) == api_key

        # 轮换主密钥
        new_master_key = "new_master_key_12345678901234567890123456789012"
        result = self.km.rotate_master_key(new_master_key)
        assert result is True

        # 验证密钥仍然可以正确解密
        retrieved_key = self.km.get_api_key(service_name)
        assert retrieved_key == api_key

    def test_health_check(self):
        """测试健康检查"""
        health = self.km.health_check()
        assert health["status"] == "healthy"
        assert "service_count" in health
        assert "store_path" in health
        assert health["master_key_configured"] is True

    def test_get_nonexistent_key(self):
        """测试获取不存在的密钥"""
        result = self.km.get_api_key("nonexistent_service_xyz")
        assert result is None

    def test_get_key_info_nonexistent(self):
        """测试获取不存在密钥的信息"""
        result = self.km.get_key_info("nonexistent_service_xyz")
        assert result is None


class TestKeyManagerIntegration:
    """集成测试"""

    def setup_method(self):
        """集成测试设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.key_store_path = self.temp_dir / ".key_store_int.enc"
        self.master_key = "integration_test_master_key_123456789012"
        
        # 创建 KeyManager 实例
        self.km = create_test_key_manager(self.key_store_path, self.master_key)
        
        # 重置状态
        self.km.key_store_path = self.key_store_path
        self.km.master_key = self.master_key
        self.km.fernet = self.km._derive_key(self.master_key)
        self.km._key_cache = {}
        self.km._cache_loaded = False
        self.km._ensure_key_store()

    def teardown_method(self):
        """清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_workflow(self):
        """测试完整的工作流程"""
        # 1. 存储多个API密钥
        services = {
            "openai_gpt4_int": "sk-gpt4-abcdef123456",
            "anthropic_claude_int": "sk-ant-abcdef123456",
            "google_gemini_int": "sk-ggl-abcdef123456"
        }

        metadata_list = {
            "openai_gpt4_int": {"model": "gpt-4", "provider": "openai"},
            "anthropic_claude_int": {"model": "claude-3", "provider": "anthropic"},
            "google_gemini_int": {"model": "gemini-pro", "provider": "google"}
        }

        for name, key in services.items():
            self.km.store_api_key(name, key, metadata_list[name])

        # 2. 验证所有密钥都可以正确获取
        for name, expected_key in services.items():
            retrieved = self.km.get_api_key(name)
            assert retrieved == expected_key

        # 3. 验证元数据
        for name, expected_metadata in metadata_list.items():
            info = self.km.get_key_info(name)
            assert info is not None
            for k, v in expected_metadata.items():
                assert info["metadata"][k] == v

        # 4. 删除一个服务
        self.km.delete_api_key("anthropic_claude_int")
        assert self.km.get_api_key("anthropic_claude_int") is None
        assert self.km.get_api_key("openai_gpt4_int") == services["openai_gpt4_int"]

        # 5. 健康检查
        health = self.km.health_check()
        assert health["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__])
