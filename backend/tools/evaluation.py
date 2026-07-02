"""
自动化评测脚本 —— 评估 Agent 的检索和提取准确率。
用法：python -m backend.tools.evaluation
"""
import json
import re
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_GOLD_DIR = _DATA_DIR / "gold_standard"
_QUERY_DIR = _DATA_DIR / "test_queries"


def evaluate_extraction_single(predicted: dict, gold: dict) -> dict:
    """
    对单篇文献的提取结果进行逐字段评测。
    返回 {field_level: {precision, recall, f1}, overall_f1}
    """
    fields = [
        "objective", "method", "target", "biomarker", "sample_size",
        "model_system", "key_findings", "result_value", "conclusion",
        "figures_summary", "limitations", "study_design_type",
        "drug_class", "mutation_types",
    ]

    field_scores = {}
    for field in fields:
        pred_val = predicted.get(field, "")
        gold_val = gold.get(field, "")
        score = _field_similarity(pred_val, gold_val)
        field_scores[field] = score

    # 计算宏平均
    precisions = [s["precision"] for s in field_scores.values()]
    recalls = [s["recall"] for s in field_scores.values()]
    f1s = [s["f1"] for s in field_scores.values()]

    return {
        "field_scores": field_scores,
        "macro_precision": sum(precisions) / len(precisions) if precisions else 0,
        "macro_recall": sum(recalls) / len(recalls) if recalls else 0,
        "macro_f1": sum(f1s) / len(f1s) if f1s else 0,
    }


def _field_similarity(pred: str, gold: str) -> dict:
    """计算单个字段的相似度分数"""
    if not gold or not gold.strip():
        # gold 为空，说明该字段不适用。如果 pred 也为空或很短，算满分
        if not pred or len(pred.strip()) < 5:
            return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
        # pred 填了内容但 gold 不需要，不扣分（可能是补充信息）
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}

    if not pred or not pred.strip():
        # gold 有值但 pred 为空
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    # 简单 token overlap 计算
    gold_tokens = set(_tokenize(gold))
    pred_tokens = set(_tokenize(pred))

    if not gold_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    intersection = gold_tokens & pred_tokens
    precision = len(intersection) / len(pred_tokens) if pred_tokens else 0.0
    recall = len(intersection) / len(gold_tokens) if gold_tokens else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {"precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3)}


def _tokenize(text: str) -> list[str]:
    """英文 tokenization，保留有意义的词"""
    text = text.lower()
    # 保留字母数字、连字符、点号（基因名）
    tokens = re.findall(r'[a-z0-9][a-z0-9.\-]*[a-z0-9]|[a-z0-9]', text)
    # 过滤停用词和短词
    stopwords = {"the", "a", "an", "of", "in", "to", "and", "or", "for", "with", "is", "was", "be", "on", "at", "by", "as", "we", "that", "this", "from", "are", "has", "been", "were", "it", "its"}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]


def evaluate_search(predicted_ids: list[str], expected_ids: list[str], k: int = 10) -> dict:
    """评估检索结果"""
    pred_set = set(predicted_ids[:k])
    gold_set = set(expected_ids)

    if not gold_set:
        return {"precision@k": 0, "recall@k": 0, "f1@k": 0}

    intersection = pred_set & gold_set
    precision = len(intersection) / len(pred_set) if pred_set else 0
    recall = len(intersection) / len(gold_set)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        f"precision@{k}": round(precision, 3),
        f"recall@{k}": round(recall, 3),
        f"f1@{k}": round(f1, 3),
    }


def run_full_evaluation(extraction_results: list[dict], search_results: list[dict]) -> str:
    """
    运行完整评测，生成 Markdown 报告。
    extraction_results: [{"pubmed_id": ..., "predicted_fields": {...}, "gold_fields": {...}}]
    search_results: [{"query_id": ..., "predicted_ids": [...], "expected_ids": [...]}]
    """
    lines = ["# Bioinformatics Agent 评测报告\n"]

    # ── 提取评测 ──
    lines.append("## 1. 文献信息提取评测\n")
    lines.append(f"评测文献数：{len(extraction_results)}\n")

    all_f1s = []
    field_f1_sums: dict[str, list] = {}

    for result in extraction_results:
        eval_result = evaluate_extraction_single(
            result.get("predicted_fields", {}),
            result.get("gold_fields", {}),
        )
        all_f1s.append(eval_result["macro_f1"])
        for field, scores in eval_result["field_scores"].items():
            field_f1_sums.setdefault(field, []).append(scores["f1"])

    avg_f1 = sum(all_f1s) / len(all_f1s) if all_f1s else 0
    lines.append(f"**总体宏平均 F1：{avg_f1:.3f}**\n")

    lines.append("### 各字段 F1 得分\n")
    lines.append("| 字段 | 平均 F1 |")
    lines.append("|------|---------|")
    for field in sorted(field_f1_sums.keys()):
        avg = sum(field_f1_sums[field]) / len(field_f1_sums[field])
        lines.append(f"| {field} | {avg:.3f} |")
    lines.append("")

    # ── 检索评测 ──
    lines.append("## 2. 文献检索评测\n")
    lines.append(f"评测查询数：{len(search_results)}\n")

    p_at_10 = []
    r_at_10 = []
    for result in search_results:
        scores = evaluate_search(
            result.get("predicted_ids", []),
            result.get("expected_ids", []),
            k=10,
        )
        p_at_10.append(scores["precision@10"])
        r_at_10.append(scores["recall@10"])

    avg_p = sum(p_at_10) / len(p_at_10) if p_at_10 else 0
    avg_r = sum(r_at_10) / len(r_at_10) if r_at_10 else 0
    lines.append(f"- **Precision@10：{avg_p:.3f}**")
    lines.append(f"- **Recall@10：{avg_r:.3f}**\n")

    # ── 术语校验评测 ──
    lines.append("## 3. 术语校验命中率\n")
    lines.append("（需要运行带 terminology validation 的完整流程后填入数据）\n")

    return "\n".join(lines)


# ── CLI 入口 ──
if __name__ == "__main__":
    # 示例：加载标注数据跑评测
    gold_files = list(_GOLD_DIR.glob("*.json"))
    print(f"找到 {len(gold_files)} 个标注文件")

    # TODO: 实际流程——运行 Agent 提取 → 加载 gold standard → 调用 evaluate
    # 此处仅演示评测报告格式
    sample_report = run_full_evaluation(
        extraction_results=[
            {
                "pubmed_id": "EXAMPLE",
                "predicted_fields": {"target": "EGFR", "method": "RCT phase III"},
                "gold_fields": {"target": "EGFR", "method": "Randomized controlled trial phase III"},
            }
        ],
        search_results=[
            {
                "query_id": "T001",
                "predicted_ids": ["12345678", "23456789"],
                "expected_ids": ["12345678", "34567890"],
            }
        ],
    )
    print(sample_report)
