"""
PubMed 检索模板库 —— 优先用预定义模板匹配用户意图，匹配不到再走 LLM 生成。
"""
import json
import re
from pathlib import Path

_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "data" / "search_templates.json"


class SearchTemplateMatcher:
    """检索模板匹配器"""

    def __init__(self):
        self.templates: list[dict] = []
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        if _TEMPLATES_PATH.exists():
            with open(_TEMPLATES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.templates = data.get("templates", [])
        self._loaded = True

    def match(self, user_query: str) -> dict | None:
        """
        尝试将用户查询匹配到预定义的检索模板。
        返回: { template_id, pubmed_query, slots_filled, confidence } 或 None
        """
        if not self._loaded:
            self.load()

        query_lower = user_query.lower()
        best_match = None
        best_score = 0

        for tmpl in self.templates:
            keywords = tmpl.get("trigger_keywords", [])
            # 计算关键词命中数
            hit_count = sum(1 for kw in keywords if kw.lower() in query_lower)
            if hit_count == 0:
                continue

            # 尝试填充 slot
            slots_filled = self._fill_slots(tmpl, user_query)
            fill_rate = sum(1 for v in slots_filled.values() if v) / max(len(slots_filled), 1)

            score = hit_count * 0.4 + fill_rate * 0.6
            if score > best_score:
                best_score = score
                best_match = {
                    "template_id": tmpl["id"],
                    "pubmed_query": tmpl["pubmed_template"].format(**slots_filled),
                    "slots_filled": slots_filled,
                    "confidence": round(best_score, 2),
                }

        if best_match and best_match["confidence"] >= 0.4:
            return best_match
        return None

    def _fill_slots(self, template: dict, user_query: str) -> dict:
        """
        尝试从用户查询中提取 slot 值。
        简单策略：基于常见中文/英文模式提取，医学生定义 slot 时可以标注提取提示。
        """
        slots = template.get("slots", {})
        filled = {}

        for slot_name, slot_hint in slots.items():
            filled[slot_name] = self._extract_slot_value(slot_name, slot_hint, user_query)

        return filled

    def _extract_slot_value(self, slot_name: str, slot_hint: str, query: str) -> str:
        """根据 slot 类型从 query 中提取值"""
        # 常见模式："{中文名}" 或 "英文-缩写" 格式的基因/药物名
        if slot_name in ("target", "drug"):
            # 提取大写缩写词（如 EGFR, PD-L1）或中英文药物名
            match = re.findall(r'\b([A-Z][A-Z0-9][-A-Z0-9]{1,10}(?:\s*[-/]\s*[A-Z0-9]+)?)\b', query)
            if match:
                return match[0]
            # 提取中文 + 英文混合
            match = re.findall(r'([一-鿿]{1,6}(?:靶点|抑制剂|单抗|抗体))', query)
            if match:
                return match[0]

        if slot_name == "disease":
            # 常见疾病名模式
            match = re.findall(
                r'\b([A-Z][a-z]+\s(?:cancer|carcinoma|tumor|disease|syndrome|leukemia|lymphoma|melanoma))',
                query, re.IGNORECASE
            )
            if match:
                return match[0]
            match = re.findall(r'([一-鿿]{2,6}(?:癌|瘤|病|症|综合征))', query)
            if match:
                return match[0]

        if slot_name == "treatment_a":
            # 从 "A vs B" 模式提取
            match = re.findall(r'([一-鿿A-Za-z/]+?)\s*(?:vs|versus|对比|比较|和|与)\s*([一-鿿A-Za-z/]+)', query, re.IGNORECASE)
            if match:
                return match[0][0].strip()

        if slot_name == "treatment_b":
            match = re.findall(r'([一-鿿A-Za-z/]+?)\s*(?:vs|versus|对比|比较|和|与)\s*([一-鿿A-Za-z/]+)', query, re.IGNORECASE)
            if match:
                return match[0][1].strip()

        if slot_name == "model_type":
            for model_term in ["xenograft", "organoid", "cell line", "mouse model", "PDX", "CDX", "knockout"]:
                if model_term.lower() in query.lower():
                    return model_term

        if slot_name == "topic":
            # 直接使用原始查询作为 topic
            return query.strip()

        # 默认：返回原始查询中可能包含的值
        return query[:100]

    def get_all_template_descriptions(self) -> list[dict]:
        """列出所有可用模板，供前端展示"""
        if not self._loaded:
            self.load()
        return [{"id": t["id"], "description": t["description"], "keywords": t.get("trigger_keywords", [])} for t in self.templates]


# 全局单例
template_matcher = SearchTemplateMatcher()
