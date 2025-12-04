import random
import json
import os
import time
from openai import OpenAI
from ..utils.tool_function import tools
tools=tools()
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from pathlib import Path
class LLMAPIPool:
    def __init__(self):
        PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
        dotenv_path = PROJECT_ROOT / "config" / ".env.local"
        load_dotenv(dotenv_path)
        self.clients = []
        self._load_clients()
        if not self.clients:
            raise ValueError("[LLM请求] ❌ 未配置任何有效的 LLM API")

    def _load_clients(self):
        try:
            apis_config = os.getenv("AGENT1_LLM_APIS")
            apis = json.loads(apis_config)
            for cfg in apis:
                if not cfg.get("enabled", True):
                    continue
                try:
                    client = OpenAI(
                        api_key=cfg["api_key"],
                        base_url=cfg["base_url"]
                    )
                    self.clients.append({
                        "name": cfg["name"],
                        "client": client,
                        "model": cfg["model"]
                    })
                except Exception as e:
                    tools.log(f"[LLM请求] ⚠️ 跳过无效 API 配置 {cfg.get('name')}: {e}")
        except Exception as e:
            tools.log(f"[LLM请求] ❌ 解析 AGENT1_LLM_APIS 失败: {e}")

    def call(self, prompt: str, max_tokens: int = 1500, timeout: int = 55, retries: int = 2) -> Optional[str]:
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
            name, client, model = choice["name"], choice["client"], choice["model"]

            try:
                tools.log(f"[LLM请求] 尝试 API [{name}] (第 {attempt+1} 次)")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    timeout=timeout,
                    stream=False
                )
                content = response.choices[0].message.content.strip()
                tools.log(f"[LLM请求] ✅ API [{name}] 成功返回")
                return content

            except Exception as e:
                tools.log(f"[LLM请求] ❌ API [{name}] 失败: {e}")
                available.remove(choice)  # 临时剔除故障节点
                if attempt < retries and len(available) == 0:
                    available = self.clients.copy()  # 无可用时重新启用所有

            time.sleep(2 ** attempt)  # 指数退避

        tools.log("[LLM请求] 💥 所有 API 尝试均失败")
        return None