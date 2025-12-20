#!/usr/bin/env python3
"""
测试LLM客户端池是否正常工作
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from src.adapters.llm.pool import DefaultLLMPool
from src.ports.llm_client import LLMCallConfig


def test_llm_pool():
    """测试LLM客户端池"""
    print("=== 测试LLM客户端池 ===")
    
    # 创建LLM池实例
    pool = DefaultLLMPool()
    
    # 查看加载的客户端
    print(f"加载的客户端数量: {len(pool.clients)}")
    for i, client in enumerate(pool.clients):
        print(f"  客户端 {i+1}: {client.name} ({client.provider_type.value}) - {client.model}")
    
    # 查看服务列表
    services = pool.list_services()
    print(f"\n服务列表:")
    for service in services:
        print(f"  名称: {service['name']}")
        print(f"  模型: {service['model']}")
        print(f"  提供商: {service['provider']}")
        print(f"  熔断状态: {service['circuit_state']}")
        print(f"  禁用直到: {service['disabled_until']}")
        print()
    
    # 测试调用
    if pool.clients:
        print("=== 测试LLM调用 ===")
        prompt = "请用一句话回答：你是谁？"
        config = LLMCallConfig(max_tokens=100, timeout_seconds=30, retries=2)
        
        try:
            response = pool.call(prompt, config)
            print(f"调用成功: {response.success}")
            print(f"内容: {response.content}")
            print(f"提供商: {response.provider}")
            print(f"模型: {response.model}")
            if response.error:
                print(f"错误: {response.error}")
        except Exception as e:
            print(f"调用失败: {e}")
    else:
        print("没有可用的客户端")


if __name__ == "__main__":
    test_llm_pool()