"""
文献质量评估 —— 基于规则（非 LLM）的评分算法。
综合期刊影响因子分区、研究设计类型、样本量等因素打分。
"""
import re
import json
from pathlib import Path

_TERMINOLOGY_DIR = Path(__file__).resolve().parent.parent / "data" / "terminology"

# ── 期刊影响因子分区参考数据 ──
# 医学生可以扩展此表，或改为从外部文件加载
JOURNAL_TIERS: dict[str, dict] = {
    # Q1 顶级医学期刊
    "new england journal of medicine": {"tier": "Q1", "score": 5, "if_range": "70+"},
    "lancet": {"tier": "Q1", "score": 5, "if_range": "60+"},
    "jama": {"tier": "Q1", "score": 5, "if_range": "50+"},
    "nature medicine": {"tier": "Q1", "score": 5, "if_range": "50+"},
    "nature": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "science": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "cell": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "nature genetics": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "nature biotechnology": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "cancer cell": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "cancer discovery": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "journal of clinical oncology": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "blood": {"tier": "Q1", "score": 4, "if_range": "15+"},
    "clinical cancer research": {"tier": "Q1", "score": 4, "if_range": "10+"},
    "nucleic acids research": {"tier": "Q1", "score": 4, "if_range": "10+"},
    "briefings in bioinformatics": {"tier": "Q1", "score": 4, "if_range": "10+"},
    "bioinformatics": {"tier": "Q1", "score": 4, "if_range": "10+"},
}

# 研究设计类型评分（从 study_designs.json 也会加载）
STUDY_DESIGN_SCORES = {
    "meta_analysis": 5,
    "rct": 5,
    "cohort": 4,
    "case_control": 3,
    "cross_sectional": 2,
    "case_series": 1,
    "in_vivo": 2,
    "in_vitro": 1,
    "unknown": 1,
}


class LiteratureQualityScorer:
    """基于规则对单篇文献质量打分（max=15 分）"""

    def __init__(self):
        self._study_design_patterns: dict = {}
        self._loaded = False

    def load(self):
        if self._loaded:
            return
        # 从 study_designs.json 加载 pattern
        path = _TERMINOLOGY_DIR / "study_designs.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for name, info in data.get("hierarchy", {}).items():
                    if isinstance(info, dict):
                        self._study_design_patterns[name] = info.get("patterns", [])
        self._loaded = True

    def score_journal(self, journal_name: str) -> tuple[int, str]:
        """根据期刊名称返回质量分和分区。返回 (score, tier)"""
        if not journal_name:
            return (1, "unknown")
        name_lower = journal_name.strip().lower()
        # 精确匹配
        if name_lower in JOURNAL_TIERS:
            info = JOURNAL_TIERS[name_lower]
            return (info["score"], info["tier"])
        # 部分匹配
        for j_name, j_info in JOURNAL_TIERS.items():
            if j_name in name_lower or name_lower in j_name:
                return (j_info["score"], j_info["tier"])
        return (2, "unranked")

    def detect_study_design(self, text: str) -> tuple[str, int]:
        """从文本中识别研究设计类型，返回 (type, score)"""
        if not self._loaded:
            self.load()
        if not text:
            return ("unknown", 1)
        text_lower = text.lower()
        for design_name, patterns in self._study_design_patterns.items():
            for pat in patterns:
                if re.search(pat, text_lower, re.IGNORECASE):
                    return (design_name, STUDY_DESIGN_SCORES.get(design_name, 2))
        return ("unknown", 1)

    def score_sample_size(self, sample_size_text: str) -> int:
        """根据样本量文本打分"""
        if not sample_size_text or not sample_size_text.strip():
            return 0
        numbers = re.findall(r'(\d[\d,]*)', sample_size_text)
        if not numbers:
            return 0
        try:
            # 取最大值（可能描述多个组）
            max_n = max(int(n.replace(",", "")) for n in numbers)
            if max_n >= 1000:
                return 3
            elif max_n >= 100:
                return 2
            elif max_n >= 10:
                return 1
            else:
                return 0
        except (ValueError, OverflowError):
            return 0

    def score_pub_date(self, publication_date: str) -> int:
        """根据发表日期打分（越新越高）"""
        if not publication_date:
            return 1
        # 提取年份
        year_match = re.search(r'(\d{4})', str(publication_date))
        if not year_match:
            return 1
        year = int(year_match.group(1))
        current_year = 2026  # 可以改为动态
        age = current_year - year
        if age <= 1:
            return 3
        elif age <= 3:
            return 2
        elif age <= 5:
            return 1
        else:
            return 0

    def score_overall(self, paper: dict) -> dict:
        """对一篇文献进行全面质量评分，返回详细评分 breakdown"""
        journal = paper.get("journal", "")
        journal_score, tier = self.score_journal(journal)

        # 合并 method 和 abstract 来检测研究设计
        method_text = paper.get("method", "") + " " + paper.get("abstract", "")
        design_type, design_score = self.detect_study_design(method_text)

        sample_text = paper.get("sample_size", "")
        sample_score = self.score_sample_size(sample_text)

        pub_date = paper.get("publication_date", "")
        recency_score = self.score_pub_date(pub_date)

        total = journal_score + design_score + sample_score + recency_score

        return {
            "total_score": total,
            "max_score": 14,
            "breakdown": {
                "journal": {"score": journal_score, "max": 5, "detail": f"{journal} ({tier})"},
                "study_design": {"score": design_score, "max": 5, "detail": design_type},
                "sample_size": {"score": sample_score, "max": 3, "detail": sample_text[:80]},
                "recency": {"score": recency_score, "max": 3, "detail": str(pub_date)},
            },
            "quality_label": self._label(total),
        }

    def _label(self, total: int) -> str:
        if total >= 11:
            return "高质量"
        elif total >= 7:
            return "中等质量"
        elif total >= 4:
            return "低质量"
        else:
            return "质量不足"

    def rank_papers(self, papers: list[dict]) -> list[dict]:
        """对文献列表按质量分排序，返回带排序结果的列表"""
        scored = []
        for paper in papers:
            score_result = self.score_overall(paper)
            scored.append({**paper, "quality": score_result})
        scored.sort(key=lambda p: p["quality"]["total_score"], reverse=True)
        return scored


# 全局单例
quality_scorer = LiteratureQualityScorer()
