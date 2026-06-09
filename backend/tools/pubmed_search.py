"""
PubMed 文献检索封装 — 使用 pymed 库。
NCBI API Key 可选，不用也能检索（但频率受限制）。
"""
from typing import Any
from pymed import PubMed

from backend.config import config


class PubMedSearch:
    """PubMed 文献检索工具"""

    def __init__(self):
        kwargs: dict[str, str] = {"tool": "BioinformaticsAgent/1.0"}
        if config.PUBMED_EMAIL:
            kwargs["email"] = config.PUBMED_EMAIL
        if config.PUBMED_API_KEY:
            kwargs["api_key"] = config.PUBMED_API_KEY
        self._pubmed = PubMed(**kwargs)

    @staticmethod
    def _safe_get(article: Any, attr: str, default: str = "") -> str:
        """安全获取属性，pymed 不同版本属性名可能不同"""
        try:
            val = getattr(article, attr, None)
            if val is None:
                return default
            return str(val)
        except Exception:
            return default

    def _format_article(self, article: Any) -> dict[str, Any]:
        """将 pymed 的 Article 对象转为统一 dict 格式"""
        pubmed_id = self._safe_get(article, "article_id", "N/A").split("\n")[0]

        # DOI 可能不存在，尝试从 XML 提取
        doi = self._safe_get(article, "doi")
        if not doi:
            doi = self._extract_doi_from_xml(article)

        return {
            "pubmed_id": pubmed_id,
            "title": self._safe_get(article, "title", "N/A"),
            "abstract": self._safe_get(article, "abstract"),
            "authors": [
                f"{a.get('lastname', '')} {a.get('firstname', '')}"
                for a in (getattr(article, "authors", None) or [])
                if a.get("lastname")
            ],
            "journal": self._safe_get(article, "journal"),
            "doi": doi,
            "publication_date": self._safe_get(article, "publication_date"),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
        }

    @staticmethod
    def _extract_doi_from_xml(article: Any) -> str:
        """尝试从 XML 原始数据中提取 DOI"""
        try:
            xml = getattr(article, "_xml", None) or getattr(article, "xml", None)
            if xml is None:
                return ""
            # 在 XML 文本中查找 DOI
            import re
            match = re.search(r'IdType="doi"[^>]*>([^<]+)', str(xml))
            if match:
                return match.group(1).strip()
            # 备用：查找 10.xxxx/ 格式的 DOI
            match = re.search(r'(10\.\d{4,}/[^\s<"]+)', str(xml))
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return ""

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """按关键词检索 PubMed 文献。

        Args:
            query: 检索关键词，支持 PubMed 高级语法
                  例如: "CRISPR therapy[Title/Abstract] AND 2024[dp]"
            max_results: 返回结果数上限

        Returns:
            文献信息列表，每条包含 pubmed_id, title, abstract, authors, doi 等
        """
        try:
            results = list(self._pubmed.query(query, max_results=max_results))
            articles = [self._format_article(a) for a in results]
            if not articles:
                # 诊断信息：看看是不是查询格式问题
                print(f"[PubMed] 查询返回 0 条结果。Query: {query[:200]}")
            return articles
        except Exception as e:
            raise RuntimeError(
                f"PubMed 检索失败: {e}\n"
                f"Query was: {query[:200]}"
            ) from e

    def get_detail(self, pubmed_id: str) -> dict[str, Any] | None:
        """根据 PubMed ID 获取单篇文献详情。

        Returns:
            文献信息 dict，未找到返回 None
        """
        try:
            results = self._pubmed.query(pubmed_id, max_results=1)
            article = next(results, None)
            if article is None:
                return None
            return self._format_article(article)
        except Exception as e:
            raise RuntimeError(f"PubMed 查询 {pubmed_id} 失败: {e}") from e


# 全局单例
pubmed = PubMedSearch()
