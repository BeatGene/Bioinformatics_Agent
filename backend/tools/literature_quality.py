"""
文献质量评估 —— 基于规则（非 LLM）的评分算法。
综合期刊影响因子分区、研究设计类型、样本量等因素打分。
"""

import re
import json
from pathlib import Path

_TERMINOLOGY_DIR = Path(__file__).resolve().parent.parent / "data" / "terminology"

# ────────────────────────────────────────────────────────────────
# 中科院/JCR 生物医学常见期刊分区（可继续扩充）
# score：用于质量评分（Q1=5，Q2=4，Q3=3，Q4=2）
# if_range：影响因子大致范围，仅供参考
# ────────────────────────────────────────────────────────────────

JOURNAL_TIERS: dict[str, dict] = {

    # ===== 综合医学 =====
    "new england journal of medicine": {"tier": "Q1", "score": 5, "if_range": "150+"},
    "the lancet": {"tier": "Q1", "score": 5, "if_range": "100+"},
    "lancet": {"tier": "Q1", "score": 5, "if_range": "100+"},
    "jama": {"tier": "Q1", "score": 5, "if_range": "100+"},
    "bmj": {"tier": "Q1", "score": 5, "if_range": "90+"},
    "nature medicine": {"tier": "Q1", "score": 5, "if_range": "80+"},
    "nature": {"tier": "Q1", "score": 5, "if_range": "60+"},
    "science": {"tier": "Q1", "score": 5, "if_range": "60+"},
    "cell": {"tier": "Q1", "score": 5, "if_range": "60+"},

    # ===== Nature 子刊 =====
    "nature genetics": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "nature biotechnology": {"tier": "Q1", "score": 5, "if_range": "35+"},
    "nature methods": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "nature communications": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "nature cancer": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "nature immunology": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "nature neuroscience": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "nature cell biology": {"tier": "Q1", "score": 5, "if_range": "25+"},

    # ===== Cell Press =====
    "cancer cell": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "molecular cell": {"tier": "Q1", "score": 5, "if_range": "20+"},
    "cell reports": {"tier": "Q1", "score": 5, "if_range": "8+"},
    "developmental cell": {"tier": "Q1", "score": 5, "if_range": "10+"},
    "cell stem cell": {"tier": "Q1", "score": 5, "if_range": "20+"},
    "cell metabolism": {"tier": "Q1", "score": 5, "if_range": "25+"},

    # ===== Oncology =====
    "cancer discovery": {"tier": "Q1", "score": 5, "if_range": "35+"},
    "journal of clinical oncology": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "annals of oncology": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "clinical cancer research": {"tier": "Q1", "score": 5, "if_range": "12+"},
    "molecular cancer": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "oncogene": {"tier": "Q1", "score": 4, "if_range": "8+"},
    "journal of the national cancer institute": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "esmo open": {"tier": "Q1", "score": 4, "if_range": "10+"},
    "journal for immunotherapy of cancer": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "breast cancer research": {"tier": "Q1", "score": 4, "if_range": "8+"},

    # ===== 血液学 =====
    "blood": {"tier": "Q1", "score": 5, "if_range": "20+"},
    "blood advances": {"tier": "Q2", "score": 4, "if_range": "7+"},
    "leukemia": {"tier": "Q1", "score": 5, "if_range": "12+"},

    # ===== Genetics / Genomics =====
    "genome biology": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "genome research": {"tier": "Q1", "score": 5, "if_range": "10+"},
    "american journal of human genetics": {"tier": "Q1", "score": 5, "if_range": "10+"},
    "human molecular genetics": {"tier": "Q1", "score": 4, "if_range": "6+"},
    "nucleic acids research": {"tier": "Q1", "score": 5, "if_range": "15+"},

    # ===== Bioinformatics =====
    "bioinformatics": {"tier": "Q1", "score": 4, "if_range": "6+"},
    "briefings in bioinformatics": {"tier": "Q1", "score": 5, "if_range": "12+"},
    "plos computational biology": {"tier": "Q1", "score": 4, "if_range": "5+"},
    "gigascience": {"tier": "Q1", "score": 4, "if_range": "8+"},
    "bmc bioinformatics": {"tier": "Q2", "score": 4, "if_range": "3+"},
    "journal of biomedical informatics": {"tier": "Q1", "score": 4, "if_range": "6+"},

    # ===== Immunology =====
    "immunity": {"tier": "Q1", "score": 5, "if_range": "30+"},
    "journal of experimental medicine": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "journal of immunology": {"tier": "Q2", "score": 4, "if_range": "5+"},
    "frontiers in immunology": {"tier": "Q2", "score": 4, "if_range": "7+"},

    # ===== Neuroscience =====
    "neuron": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "brain": {"tier": "Q1", "score": 5, "if_range": "14+"},
    "journal of neuroscience": {"tier": "Q2", "score": 4, "if_range": "5+"},

    # ===== Pharmacology =====
    "clinical pharmacology and therapeutics": {"tier": "Q1", "score": 5, "if_range": "8+"},
    "pharmacological reviews": {"tier": "Q1", "score": 5, "if_range": "20+"},
    "molecular pharmacology": {"tier": "Q2", "score": 4, "if_range": "5+"},

    # ===== Cardiovascular =====
    "circulation": {"tier": "Q1", "score": 5, "if_range": "35+"},
    "european heart journal": {"tier": "Q1", "score": 5, "if_range": "35+"},
    "journal of the american college of cardiology": {"tier": "Q1", "score": 5, "if_range": "25+"},

    # ===== Infectious Diseases =====
    "clinical infectious diseases": {"tier": "Q1", "score": 5, "if_range": "12+"},
    "lancet infectious diseases": {"tier": "Q1", "score": 5, "if_range": "40+"},
    "emerging infectious diseases": {"tier": "Q1", "score": 4, "if_range": "10+"},

    # ===== Endocrinology =====
    "diabetes care": {"tier": "Q1", "score": 5, "if_range": "15+"},
    "diabetologia": {"tier": "Q1", "score": 5, "if_range": "10+"},

    # ===== Gastroenterology =====
    "gut": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "gastroenterology": {"tier": "Q1", "score": 5, "if_range": "25+"},

    # ===== Respiratory =====
    "american journal of respiratory and critical care medicine": {"tier": "Q1", "score": 5, "if_range": "25+"},
    "thorax": {"tier": "Q1", "score": 5, "if_range": "12+"},

    # ===== 开放获取综合 =====
    "plos one": {"tier": "Q3", "score": 3, "if_range": "3+"},
    "scientific reports": {"tier": "Q2", "score": 4, "if_range": "4+"},
    "bmc medicine": {"tier": "Q1", "score": 5, "if_range": "10+"},
    "bmc genomics": {"tier": "Q2", "score": 4, "if_range": "4+"},
    "frontiers in oncology": {"tier": "Q2", "score": 4, "if_range": "5+"},
    "aging": {"tier": "Q2", "score": 4, "if_range": "5+"},
}

# 研究设计类型评分（医学证据等级）
STUDY_DESIGN_SCORES = {
    "meta_analysis": 5,
    "systematic_review": 5,
    "rct": 5,
    "cohort": 4,
    "case_control": 3,
    "cross_sectional": 2,
    "case_series": 2,
    "case_report": 1,
    "in_vivo": 2,
    "in_vitro": 1,
    "bioinformatics": 2,
    "unknown": 1,
}


from datetime import datetime
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
        """根据期刊名称返回质量分和分区"""

        if not journal_name:
            return (1, "unknown")

        name_lower = journal_name.strip().lower()

        # 精确匹配
        if name_lower in JOURNAL_TIERS:
            info = JOURNAL_TIERS[name_lower]
            return (info["score"], info["tier"])

        # 模糊匹配
        for j_name, j_info in JOURNAL_TIERS.items():
            if j_name in name_lower or name_lower in j_name:
                return (j_info["score"], j_info["tier"])

        return (2, "unranked")

    def detect_study_design(self, text: str) -> tuple[str, int]:
        """识别研究设计类型"""

        if not self._loaded:
            self.load()

        if not text:
            return ("unknown", 1)

        text_lower = text.lower()

        for design_name, patterns in self._study_design_patterns.items():
            for pat in patterns:
                if re.search(pat, text_lower, re.IGNORECASE):
                    return (
                        design_name,
                        STUDY_DESIGN_SCORES.get(design_name, 2)
                    )

        return ("unknown", 1)

    def score_sample_size(self, sample_size_text: str) -> int:
        """根据样本量打分"""

        if not sample_size_text or not sample_size_text.strip():
            return 0

        numbers = re.findall(r"(\d[\d,]*)", sample_size_text)

        if not numbers:
            return 0

        try:
            max_n = max(
                int(n.replace(",", ""))
                for n in numbers
            )

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
        """根据发表年份打分"""

        if not publication_date:
            return 1

        year_match = re.search(r"(\d{4})", str(publication_date))

        if not year_match:
            return 1

        year = int(year_match.group(1))

        current_year = datetime.now().year

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
        """综合质量评分"""

        journal = paper.get("journal", "")
        journal_score, tier = self.score_journal(journal)

        method_text = (
            paper.get("method", "")
            + " "
            + paper.get("abstract", "")
        )

        design_type, design_score = self.detect_study_design(method_text)

        sample_text = paper.get("sample_size", "")
        sample_score = self.score_sample_size(sample_text)

        pub_date = paper.get("publication_date", "")
        recency_score = self.score_pub_date(pub_date)

        total = (
            journal_score
            + design_score
            + sample_score
            + recency_score
        )

        return {
            "total_score": total,
            "max_score": 16,
            "breakdown": {
                "journal": {
                    "score": journal_score,
                    "max": 5,
                    "detail": f"{journal} ({tier})",
                },
                "study_design": {
                    "score": design_score,
                    "max": 5,
                    "detail": design_type,
                },
                "sample_size": {
                    "score": sample_score,
                    "max": 3,
                    "detail": sample_text[:80],
                },
                "recency": {
                    "score": recency_score,
                    "max": 3,
                    "detail": str(pub_date),
                },
            },
            "quality_label": self._label(total),
        }

    def _label(self, total: int) -> str:
        """质量等级"""

        if total >= 13:
            return "高质量"
        elif total >= 9:
            return "中等质量"
        elif total >= 5:
            return "低质量"
        else:
            return "质量不足"

    def rank_papers(self, papers: list[dict]) -> list[dict]:
        """按质量排序"""

        scored = []

        for paper in papers:
            score_result = self.score_overall(paper)

            scored.append(
                {
                    **paper,
                    "quality": score_result,
                }
            )

        scored.sort(
            key=lambda p: p["quality"]["total_score"],
            reverse=True,
        )

        return scored


# 全局单例
quality_scorer = LiteratureQualityScorer()