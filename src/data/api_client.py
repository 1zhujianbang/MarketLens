import aiohttp
import asyncio
import random
import json
import os
import time
from typing import Optional, Dict, Any
from ..utils.tool_function import tools
tools=tools()
from dotenv import load_dotenv
from pathlib import Path
class DataAPIPool:
    def __init__(self):
        PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
        dotenv_path = PROJECT_ROOT / "config" / ".env.local"
        load_dotenv(dotenv_path)
        self.clients = []
        self._load_clients()
        if not self.clients:
            raise ValueError("[数据获取] ❌ 未配置任何有效的 数据源 API")

    def _load_clients(self):
        try:
            apis_config = os.getenv("DATA_APIS")
            apis = json.loads(apis_config)
            for cfg in apis:
                if not cfg.get("enabled", True):
                    continue
                try:
                    self.clients.append({
                        "name": cfg["name"],
                        "base_url": cfg["base_url"]
                    })
                    pass
                except Exception as e:
                    tools.log(f"[数据获取] ⚠️ 跳过无效 API 配置 {cfg.get('name')}: {e}")
        except Exception as e:
            tools.log(f"[数据获取] ❌ 解析 DATA_APIS 失败: {e}")

    async def call(self, prompt: str, max_tokens: int = 1500, timeout: int = 55, retries: int = 2) -> Optional[str]:
        """
        尝试调用 API 池中的服务，直到成功或耗尽重试次数。
        返回 raw LLM content (str)，由调用方解析 JSON。
        """
        available = self.clients.copy()
        if not available:
            return None

        for attempt in range(retries + 1):
            if not available:
                available = self.clients.copy()  # 重置候选池

            # 随机选一个（简单负载均衡），也可改为 round-robin
            choice = random.choice(available)
            name, url = choice["name"], choice["base_url"]

            try:
                tools.log(f"[数据请求] 尝试 API [{name}] (第 {attempt+1} 次)")
                async with self.session.get(url) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"API请求失败: {response.status} - {error_text}")
                    
                    result = await response.json()
                    tools.log(f"[数据获取] ✅ API [{name}] 成功返回")
                    return result
                    
            except aiohttp.ClientError as e:
                tools.log("[数据获取] ❌ API [{name}] 失败: {e}")
            except json.JSONDecodeError as e:
                tools.log("[数据获取] ❌ API [{name}] 失败: {e}")
            time.sleep(2 ** attempt)  # 指数退避

        tools.log("[数据获取] 💥 所有 API 尝试均失败")
        return None