"""
生物医学术语词典与规则校验引擎。
加载 data/terminology/*.json，对 LLM 提取结果做规则兜底校验。
"""
import json
import re
from pathlib import Path
from typing import Any

_TERMINOLOGY_DIR = Path(__file__).resolve().parent.parent / "data" / "terminology"


class BiomedicalTerminology:
    """生物医学术语词典 + 校验规则引擎"""

    def __init__(self):
        self.targets: dict = {}
        self.mutations: dict = {}
        self.model_systems: dict = {}
        self.drug_classes: dict = {}
        self.study_designs: dict = {}
        self.validation_rules: dict = {}
        self._alias_to_standard: dict[str, str] = {}  # 别名 → 标准名映射
        self._all_known_terms: set[str] = set()
        self._loaded = False

    def load(self):
        """加载所有术语 JSON 文件"""
        if self._loaded:
            return
        self.targets = self._read_json("targets.json")
        self.mutations = self._read_json("mutations.json")
        self.model_systems = self._read_json("model_systems.json")
        self.drug_classes = self._read_json("drug_classes.json")
        self.study_designs = self._read_json("study_designs.json")
        self.validation_rules = self._read_json("validation_rules.json")
        self._build_alias_index()
        self._loaded = True

    def _read_json(self, filename: str) -> dict:
        path = _TERMINOLOGY_DIR / filename
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── 别名索引构建 ──
    def _build_alias_index(self):
        """遍历 targets.json 所有分类，构建 alias → standard name 映射"""
        self._alias_to_standard.clear()
        self._all_known_terms.clear()
        for category in self.targets.values():
            if not isinstance(category, dict):
                continue
            names = category.get("names", [])
            aliases_map = category.get("aliases", {})
            for std_name in names:
                self._all_known_terms.add(std_name.lower())
                self._alias_to_standard[std_name.lower()] = std_name
            for std_name, alias_list in aliases_map.items():
                self._all_known_terms.add(std_name.lower())
                self._alias_to_standard[std_name.lower()] = std_name
                for alias in alias_list:
                    self._alias_to_standard[alias.lower()] = std_name
                    self._all_known_terms.add(alias.lower())

    # ── 靶点/基因名校验 ──
    def lookup_target(self, text: str) -> dict:
        """在靶点词典中查找文本。返回 {found, standard_name, confidence}"""
        if not text or not text.strip():
            return {"found": False, "standard_name": "", "confidence": 0.0}
        text_lower = text.strip().lower()
        # 精确匹配别名
        if text_lower in self._alias_to_standard:
            return {"found": True, "standard_name": self._alias_to_standard[text_lower], "confidence": 1.0}
        # 模糊匹配（子串）
        for alias, std in self._alias_to_standard.items():
            if alias in text_lower or text_lower in alias:
                return {"found": True, "standard_name": std, "confidence": 0.7}
        # 检查是否包含已知 term
        for term in self._all_known_terms:
            if term in text_lower:
                return {"found": True, "standard_name": term.upper(), "confidence": 0.5}
        return {"found": False, "standard_name": "", "confidence": 0.0}

    def validate_target(self, extracted_target: str) -> dict:
        """校验 target 字段，返回 {valid, standard_name, warning}"""
        if not extracted_target or not extracted_target.strip():
            return {"valid": True, "standard_name": "", "warning": "靶点字段为空"}
        result = self.lookup_target(extracted_target)
        if not result["found"]:
            return {
                "valid": False,
                "standard_name": extracted_target,
                "warning": f"[待核实] '{extracted_target}' 不在已知靶点词典中，请人工确认",
            }
        return {"valid": True, "standard_name": result["standard_name"], "warning": ""}

    # ── 突变类型识别 ──
    def detect_mutation_types(self, text: str) -> list[str]:
        """从文本中检测提到的突变类型，返回突变类型名列表"""
        found = []
        for category in self.mutations.values():
            if not isinstance(category, dict):
                continue
            for mut_name, mut_info in category.items():
                if not isinstance(mut_info, dict):
                    continue
                patterns = mut_info.get("patterns", [])
                for pat in patterns:
                    if re.search(pat, text, re.IGNORECASE):
                        found.append(mut_name)
                        break
        return list(set(found))

    # ── 模型系统识别 ──
    def detect_model_type(self, text: str) -> dict:
        """从 method/model_system 文本中识别实验模型类型。返回 {type, subtype, confidence}"""
        if not text:
            return {"type": "unknown", "subtype": "", "confidence": 0.0}

        # 遍历 model_systems.json 的所有层级
        for category_name, category in self.model_systems.items():
            if not isinstance(category, dict):
                continue
            for model_name, model_info in category.items():
                if not isinstance(model_info, dict):
                    continue
                # 有 subtypes 的情况（如 mouse_models）
                subtypes = model_info.get("subtypes", {})
                if subtypes:
                    for sub_name, sub_info in subtypes.items():
                        if not isinstance(sub_info, dict):
                            continue
                        for pat in sub_info.get("patterns", []):
                            if re.search(pat, text, re.IGNORECASE):
                                return {"type": model_name, "subtype": sub_name, "confidence": 0.9}
                # 没有 subtype 的情况
                for pat in model_info.get("patterns", []):
                    if re.search(pat, text, re.IGNORECASE):
                        return {"type": model_name, "subtype": "", "confidence": 0.8}
        return {"type": "unknown", "subtype": "", "confidence": 0.0}

    # ── 药物分类识别 ──
    def detect_drug_class(self, text: str) -> list[str]:
        """从文本中识别药物分类"""
        found = []
        for category_name, category in self.drug_classes.items():
            if not isinstance(category, dict):
                continue
            for class_name, class_info in category.items():
                if not isinstance(class_info, dict):
                    continue
                for pat in class_info.get("patterns", []):
                    if re.search(pat, text, re.IGNORECASE):
                        found.append(f"{category_name}/{class_name}")
                        break
        return found

    # ── 研究设计类型识别 ──
    def detect_study_design(self, text: str) -> dict:
        """从文本中识别研究设计类型，返回 {type, evidence_level, score}"""
        hierarchy = self.study_designs.get("hierarchy", {})
        for design_name, design_info in hierarchy.items():
            if not isinstance(design_info, dict):
                continue
            for pat in design_info.get("patterns", []):
                if re.search(pat, text, re.IGNORECASE):
                    return {
                        "type": design_name,
                        "evidence_level": design_info.get("evidence_level", 5),
                        "score": design_info.get("score", 1),
                    }
        return {"type": "unknown", "evidence_level": 5, "score": 0}

    # ── 批量字段校验（核心接口） ──
    def validate_extraction(self, pubmed_id: str, fields: dict) -> dict:
        """
        对 LLM 提取的一篇文献的所有字段进行规则校验。
        返回: { pubmed_id, warnings: [{field, level, message}], corrections: [{field, original, suggested}] }
        """
        if not self._loaded:
            self.load()

        warnings = []
        corrections = []

        # Target 校验
        target = fields.get("target", "")
        target_result = self.validate_target(target)
        if not target_result["valid"]:
            warnings.append({"field": "target", "level": "WARN", "message": target_result["warning"]})
        if target_result["standard_name"] and target_result["standard_name"] != target:
            corrections.append({"field": "target", "original": target, "suggested": target_result["standard_name"]})

        # Biomarker 校验
        biomarker = fields.get("biomarker", "")
        if biomarker and biomarker.strip():
            detected = self.detect_mutation_types(biomarker)
            if not detected:
                # 也尝试在靶点词典中查找
                bm_result = self.lookup_target(biomarker)
                if not bm_result["found"]:
                    warnings.append({
                        "field": "biomarker",
                        "level": "SOFT",
                        "message": f"生物标志物 '{biomarker[:60]}' 不在已知词典中"
                    })

        # Method → 识别研究方法类型
        method = fields.get("method", "")
        if method:
            design = self.detect_study_design(method)
            if design["type"] == "unknown":
                warnings.append({
                    "field": "method",
                    "level": "SOFT",
                    "message": "未识别出明确的研究设计类型（RCT/队列/病例对照等）"
                })
            else:
                corrections.append({
                    "field": "method_design_type",
                    "original": "",
                    "suggested": design["type"],
                })

        # Model system 校验
        model = fields.get("model_system", "")
        if model and model.strip():
            model_result = self.detect_model_type(model)
            if model_result["type"] == "unknown":
                warnings.append({
                    "field": "model_system",
                    "level": "SOFT",
                    "message": f"模型系统 '{model[:80]}' 未匹配已知类型"
                })

        # Result value 校验——是否包含统计指标
        result_val = fields.get("result_value", "")
        if result_val and result_val.strip():
            has_stats = re.search(
                r'(p\s*[<=>]|HR\s*=|OR\s*=|RR\s*=|CI\s*=|95%.*CI|hazard ratio|odds ratio|relative risk|\d+%|\(\s*95%\s*|p\s*=\s*0)',
                result_val, re.IGNORECASE
            )
            if not has_stats:
                warnings.append({
                    "field": "result_value",
                    "level": "SOFT",
                    "message": "缺少统计指标（p值/HR/OR/RR/CI），可能为定性描述而非数值结果"
                })

        # Sample size 校验
        sample_size = fields.get("sample_size", "")
        if sample_size and sample_size.strip():
            numbers = re.findall(r'\d[\d,]*', sample_size)
            if not numbers:
                warnings.append({"field": "sample_size", "level": "WARN", "message": "样本量字段未提取到数值"})

        return {
            "pubmed_id": pubmed_id,
            "warnings": warnings,
            "corrections": corrections,
            "warning_count": len(warnings),
            "correction_count": len(corrections),
        }

    # ── 在报告中注入校验标记 ──
    def annotate_report_fields(self, fields: dict, validation: dict) -> dict:
        """给字段添加校验标记，供前端高亮显示"""
        annotated = dict(fields)
        warnings_by_field: dict[str, list] = {}
        for w in validation.get("warnings", []):
            warnings_by_field.setdefault(w["field"], []).append(w)

        for field, warns in warnings_by_field.items():
            current = annotated.get(field, "")
            tags = " ".join(f"[{w['level']}: {w['message']}]" for w in warns)
            annotated[field + "_validation"] = tags

        return annotated


# 全局单例
terminology = BiomedicalTerminology()
