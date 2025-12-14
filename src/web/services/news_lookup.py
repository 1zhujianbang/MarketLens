from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from src.web import utils


@dataclass(frozen=True)
class NewsItem:
    news_id: str
    title: str
    url: str
    content: str
    published_at: str
    source: Dict[str, Any]


def find_news_by_id(news_id: str) -> Optional[NewsItem]:
    """Best-effort lookup from tmp raw news files (local-first).

    NOTE: raw news is currently stored under data/tmp/raw_news/*.jsonl.
    This search is optimized for correctness over speed (files are typically few).
    """
    if not news_id:
        return None
    files = utils.get_raw_news_files()
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                for line in fp:
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if str(obj.get("id") or "") == str(news_id):
                        return NewsItem(
                            news_id=str(news_id),
                            title=str(obj.get("title") or ""),
                            url=str(obj.get("url") or ""),
                            content=str(obj.get("content") or ""),
                            published_at=str(obj.get("datetime") or obj.get("publishedAt") or ""),
                            source=(obj.get("source") or {}) if isinstance(obj.get("source"), dict) else {},
                        )
        except Exception:
            continue
    return None


