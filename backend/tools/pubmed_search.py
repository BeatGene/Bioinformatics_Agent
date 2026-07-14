"""
PubMed 文献检索封装 — 使用 pymed 库。
NCBI API Key 可选，不用也能检索（但频率受限制）。
"""
import re
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
        pubmed_id = self._extract_pubmed_id(article) or "N/A"

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

    @classmethod
    def _extract_pubmed_id(cls, article: Any) -> str:
        """兼容不同 pymed 版本的 PMID 字段。"""
        for attr in ("pubmed_id", "article_id", "pmid"):
            value = cls._safe_get(article, attr)
            if value:
                return value.splitlines()[0].strip()

        try:
            xml = getattr(article, "_xml", None) or getattr(article, "xml", None)
            if xml is not None:
                elem = xml.find(".//PMID")
                if elem is not None and elem.text:
                    return elem.text.strip()
        except Exception:
            pass

        return ""

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

    @staticmethod
    def _normalize_query(query: str) -> str:
        """修正 PubMed 对带空格短语字段检索的敏感语法。"""
        normalized = query
        phrases = [
            "clinical trial",
            "phase I",
            "phase II",
            "phase III",
            "phase IV",
            "targeted therapy",
        ]
        for phrase in phrases:
            normalized = re.sub(
                rf'(?<!")\b{re.escape(phrase)}\b(?!")(?=\[[^\]]+\])',
                f'"{phrase}"',
                normalized,
                flags=re.IGNORECASE,
            )
        return normalized

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        """按关键词检索 PubMed 文献。

        Args:
            query: 检索关键词，支持 PubMed 高级语法
                  例如: "CRISPR therapy[Title/Abstract] AND 2024[dp]"
            max_results: 返回结果数上限

        Returns:
            文献信息列表，每条包含 pubmed_id, title, abstract, authors, doi 等
        """
        attempted: list[str] = []
        queries = [query, self._normalize_query(query)]

        last_error: Exception | None = None
        for candidate_query in queries:
            if candidate_query in attempted:
                continue
            attempted.append(candidate_query)
            try:
                results = list(self._pubmed.query(candidate_query, max_results=max_results))
                articles = [self._format_article(a) for a in results]
                if not articles:
                    print(f"[PubMed] 查询返回 0 条结果。Query: {candidate_query[:200]}")
                if candidate_query != query:
                    print(f"[PubMed] 使用备用检索式成功。Query: {candidate_query[:200]}")
                return articles
            except Exception as e:
                last_error = e
                print(f"[PubMed] 检索失败: {e}")

        raise RuntimeError(
            f"PubMed 检索失败: {last_error}\n"
            f"Query was: {query[:200]}\n"
            f"Normalized query was: {self._normalize_query(query)[:200]}"
        ) from last_error

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
