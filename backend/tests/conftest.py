"""
测试夹具与 Mock 基础设施。

为每个测试函数创建隔离的：
- 临时 SQLite 数据库（不影响生产数据库）
- FastAPI TestClient（覆盖 get_db 依赖）
- LLM / PubMed 的 mock 补丁
"""
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.database import get_db
from backend.db.models import Base

# ═══════════════════════════════════════════════════════════════════════════════
# 数据库夹具
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def test_engine():
    """每个测试函数独立的 SQLite 引擎（存储在临时目录）"""
    tmpdir = tempfile.mkdtemp(prefix="bioagent_test_")
    db_path = Path(tmpdir) / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="function")
def test_session_factory(test_engine):
    """基于临时引擎的 session factory"""
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def client(test_session_factory) -> TestClient:
    """返回覆盖了 get_db 依赖的 FastAPI TestClient"""
    from backend.api.server import app

    def _override_get_db() -> Session:
        db = test_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════════════════════════════════════
# Mock: 模拟 research 执行流（异步生成器）
# ═══════════════════════════════════════════════════════════════════════════════

_SAMPLE_PAPER = {
    "pubmed_id": "40001234",
    "title": "EGFR T790M mutation in non-small cell lung cancer: a phase III trial",
    "abstract": "This study investigated the efficacy of osimertinib...",
    "authors": ["Wang X", "Li Y", "Zhang Z"],
    "journal": "New England Journal of Medicine",
    "publication_date": "2025",
    "doi": "10.1056/NEJMoa2500123",
    "url": "https://pubmed.ncbi.nlm.nih.gov/40001234/",
    "objective": "评估奥希替尼对EGFR T790M突变NSCLC患者的疗效",
    "method": "随机双盲III期临床试验，n=419",
    "target": "EGFR T790M",
    "key_findings": "中位PFS 18.9个月 vs 10.2个月（HR 0.46, p<0.001）",
    "conclusion": "奥希替尼显著改善T790M阳性患者的PFS",
    "validation_warnings": 0,
    "validation_corrections": 0,
}


def _make_snapshot(
    thread_id: str = "mock-thread-001",
    current_step: str = "完成",
    plan_summary: str = "系统性文献调研",
    search_results_count: int = 5,
    selected_papers_count: int = 5,
    parsed_papers_count: int = 5,
    comparison_report: str = "## 对比分析\n\n共性发现...",
    final_report: str = "# 最终报告\n\n这是测试生成的报告。",
    errors: list[str] | None = None,
    is_paused: bool = False,
    pause_point: str = "",
    sub_tasks: list[dict] | None = None,
    papers: list[dict] | None = None,
) -> dict[str, Any]:
    if errors is None:
        errors = []
    if sub_tasks is None:
        sub_tasks = [
            {"id": "planner", "type": "plan", "description": "任务规划", "depends_on": [], "status": "done"},
            {"id": "search", "type": "search", "description": "文献检索与筛选", "depends_on": ["planner"], "status": "done"},
            {"id": "parse", "type": "parse", "description": "文献结构化解析", "depends_on": ["search"], "status": "done"},
            {"id": "compare", "type": "compare", "description": "跨文献对比分析", "depends_on": ["parse"], "status": "done"},
            {"id": "report", "type": "report", "description": "生成综述报告", "depends_on": ["compare"], "status": "done"},
        ]
    if papers is None:
        papers = [_SAMPLE_PAPER]
    return {
        "thread_id": thread_id,
        "current_step": current_step,
        "plan_summary": plan_summary,
        "sub_tasks": sub_tasks,
        "execution_log": [
            "[Planner] 完成。计划: " + plan_summary,
            "[Search Worker] 筛选完成: " + str(selected_papers_count) + " 篇相关文献",
            "[Parser Worker] 完成。共解析 " + str(parsed_papers_count) + " 篇文献",
            "[Reporter] 最终报告生成完毕",
        ],
        "search_results_count": search_results_count,
        "selected_papers_count": selected_papers_count,
        "parsed_papers_count": parsed_papers_count,
        "comparison_report": comparison_report,
        "final_report": final_report,
        "errors": errors,
        "papers": papers,
        "is_paused": is_paused,
        "pause_point": pause_point,
        "user_approved_search": not is_paused,
    }


async def _mock_execute_flow(*args, **kwargs) -> AsyncGenerator[dict[str, Any], None]:
    """模拟 execute_research：yield 两个快照（运行中 → 完成）"""
    tid = kwargs.get("thread_id", "mock-tid")
    query = kwargs.get("query", args[0] if args else "unknown")
    # 快照1：运行中
    yield _make_snapshot(
        thread_id=tid,
        current_step="Planner 规划中",
        plan_summary=f"针对 '{query[:60]}' 的系统性文献调研",
        search_results_count=0,
        selected_papers_count=0,
        parsed_papers_count=0,
        comparison_report="",
        final_report="",
        sub_tasks=[
            {"id": "planner", "type": "plan", "description": "任务规划", "depends_on": [], "status": "running"},
            {"id": "search", "type": "search", "description": "文献检索与筛选", "depends_on": ["planner"], "status": "pending"},
            {"id": "parse", "type": "parse", "description": "文献结构化解析", "depends_on": ["search"], "status": "pending"},
            {"id": "compare", "type": "compare", "description": "跨文献对比分析", "depends_on": ["parse"], "status": "pending"},
            {"id": "report", "type": "report", "description": "生成综述报告", "depends_on": ["compare"], "status": "pending"},
        ],
    )
    # 快照2：完成
    yield _make_snapshot(thread_id=tid)


async def _mock_execute_paused(*args, **kwargs) -> AsyncGenerator[dict[str, Any], None]:
    """模拟 execute_research：在 review_search 处暂停"""
    tid = kwargs.get("thread_id", "mock-tid")
    yield _make_snapshot(
        thread_id=tid,
        current_step="检索完成，找到 5 篇相关文献",
        final_report="",
        is_paused=True,
        pause_point="review_search",
        sub_tasks=[
            {"id": "planner", "type": "plan", "description": "任务规划", "depends_on": [], "status": "done"},
            {"id": "search", "type": "search", "description": "文献检索与筛选", "depends_on": ["planner"], "status": "done"},
            {"id": "parse", "type": "parse", "description": "文献结构化解析", "depends_on": ["search"], "status": "pending"},
            {"id": "compare", "type": "compare", "description": "跨文献对比分析", "depends_on": ["parse"], "status": "pending"},
            {"id": "report", "type": "report", "description": "生成综述报告", "depends_on": ["compare"], "status": "pending"},
        ],
    )


async def _mock_execute_error(*args, **kwargs) -> AsyncGenerator[dict[str, Any], None]:
    """模拟 execute_research：产生错误"""
    tid = kwargs.get("thread_id", "mock-tid")
    yield _make_snapshot(
        thread_id=tid,
        current_step="检索失败",
        search_results_count=0,
        selected_papers_count=0,
        parsed_papers_count=0,
        comparison_report="",
        final_report="",
        errors=["PubMed 检索失败: Connection timeout"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# pytest fixtures：注入 mock
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_research_success():
    """将 execute_research 替换为成功完成的 mock"""
    target = "backend.api.server.execute_research"
    with patch(target, side_effect=_mock_execute_flow) as mock:
        yield mock


@pytest.fixture
def mock_research_paused():
    """将 execute_research 替换为在 review_search 暂停的 mock"""
    target = "backend.api.server.execute_research"
    with patch(target, side_effect=_mock_execute_paused) as mock:
        yield mock


@pytest.fixture
def mock_research_error():
    """将 execute_research 替换为产生错误的 mock"""
    target = "backend.api.server.execute_research"
    with patch(target, side_effect=_mock_execute_error) as mock:
        yield mock


@pytest.fixture
def mock_resume_success():
    """将 resume_research 替换为成功完成的 mock"""
    target = "backend.api.server.resume_research"
    with patch(target, side_effect=_mock_execute_flow) as mock:
        yield mock
