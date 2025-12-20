"""
基础设施层 - 语义实体匹配器

使用 sentence-transformers 进行跨语言实体语义匹配
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Tuple
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class SemanticEntityMatcher:
    """
    基于语义嵌入的实体匹配器
    
    特点：
    - 支持中英文跨语言匹配
    - 识别语义相似实体（如 "纽约时报" vs "New York Times"）
    - 使用轻量级多语言模型
    """
    
    _instance: Optional[SemanticEntityMatcher] = None
    _model = None
    _model_loaded = False
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """延迟初始化（避免导入时加载模型）"""
        pass
    
    def _load_model(self):
        """延迟加载模型"""
        if self._model_loaded:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            import os
            
            # 使用轻量级多语言模型
            # paraphrase-multilingual-MiniLM-L12-v2: 约420MB
            # - 支持50+种语言（包括中英文）
            # - 性能优秀，速度较快
            model_name = 'paraphrase-multilingual-MiniLM-L12-v2'
            
            logger.info(f"[SemanticMatcher] 正在加载语义模型: {model_name}")
            
            # 配置国内镜像加速（如果需要）
            # 优先使用环境变量 HF_ENDPOINT
            hf_endpoint = os.environ.get('HF_ENDPOINT')
            if hf_endpoint:
                logger.info(f"[SemanticMatcher] 使用镜像源: {hf_endpoint}")
            else:
                logger.info("[SemanticMatcher] 首次加载需要下载模型（约420MB），请耐心等待...")
                logger.info("[SemanticMatcher] 如果下载超时，请设置环境变量 HF_ENDPOINT 使用镜像源")
            
            # 设置较长的超时时间
            self._model = SentenceTransformer(
                model_name,
                cache_folder=None,  # 使用默认缓存目录
                use_auth_token=False
            )
            self._model_loaded = True
            
            logger.info(f"[SemanticMatcher] ✅ 模型加载成功")
            
        except ImportError:
            logger.warning(
                "[SemanticMatcher] ⚠️ sentence-transformers 未安装，无法使用语义匹配功能\n"
                "安装命令: pip install sentence-transformers"
            )
            self._model_loaded = False
        except Exception as e:
            logger.error(f"[SemanticMatcher] ❌ 模型加载失败: {e}")
            logger.error("[SemanticMatcher] 网络问题？请尝试：")
            logger.error("  1. 设置镜像源: set HF_ENDPOINT=https://hf-mirror.com (Windows)")
            logger.error("  2. 或手动下载模型到缓存目录")
            logger.error("  3. 或暂时禁用语义匹配功能")
            self._model_loaded = False
    
    def is_available(self) -> bool:
        """检查语义匹配器是否可用"""
        if not self._model_loaded:
            self._load_model()
        return self._model is not None
    
    def encode(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        编码文本为语义向量
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量矩阵，shape: (len(texts), embedding_dim)
            如果模型不可用，返回 None
        """
        if not self.is_available():
            return None
        
        try:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return embeddings
        except Exception as e:
            logger.error(f"[SemanticMatcher] 编码失败: {e}")
            return None
    
    def similarity(self, text1: str, text2: str) -> Optional[float]:
        """
        计算两个文本的语义相似度
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            相似度分数 (0-1)，如果模型不可用返回 None
        """
        embeddings = self.encode([text1, text2])
        if embeddings is None:
            return None
        
        # 计算余弦相似度
        from sklearn.metrics.pairwise import cosine_similarity
        sim = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        
        # 转换到 0-1 范围（余弦相似度范围是 -1 到 1）
        return (sim + 1) / 2
    
    def batch_similarity_matrix(self, entities: List[str]) -> Optional[np.ndarray]:
        """
        批量计算实体间的语义相似度矩阵
        
        Args:
            entities: 实体列表
            
        Returns:
            相似度矩阵，shape: (len(entities), len(entities))
            如果模型不可用，返回 None
        """
        embeddings = self.encode(entities)
        if embeddings is None:
            return None
        
        from sklearn.metrics.pairwise import cosine_similarity
        sim_matrix = cosine_similarity(embeddings)
        
        # 转换到 0-1 范围
        return (sim_matrix + 1) / 2
    
    def find_similar_entities(
        self, 
        query_entity: str, 
        candidate_entities: List[str],
        threshold: float = 0.7
    ) -> List[Tuple[str, float]]:
        """
        在候选实体中查找与查询实体语义相似的实体
        
        Args:
            query_entity: 查询实体
            candidate_entities: 候选实体列表
            threshold: 相似度阈值
            
        Returns:
            [(entity, score), ...] 按相似度降序排列
        """
        if not candidate_entities:
            return []
        
        all_entities = [query_entity] + candidate_entities
        sim_matrix = self.batch_similarity_matrix(all_entities)
        
        if sim_matrix is None:
            return []
        
        # 第一行是查询实体与所有候选实体的相似度
        query_scores = sim_matrix[0, 1:]
        
        # 筛选并排序
        results = [
            (entity, float(score))
            for entity, score in zip(candidate_entities, query_scores)
            if score >= threshold
        ]
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# 全局单例
_semantic_matcher: Optional[SemanticEntityMatcher] = None


def get_semantic_matcher() -> SemanticEntityMatcher:
    """获取语义匹配器单例"""
    global _semantic_matcher
    if _semantic_matcher is None:
        _semantic_matcher = SemanticEntityMatcher()
    return _semantic_matcher
