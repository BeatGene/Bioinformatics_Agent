"""
测试核心研究端点：SSE 流式 / 非流式 / 恢复 / 状态查询。

execute_research 和 resume_research 通过 conftest.py 的 mock 替换，
不依赖真实的 DeepSeek API 或 PubMed。

注意：/api/research/simple 是一个极简端点，不依赖数据库（无 Depends(get_db)），
      不会自动创建 Conversation / Message / ResearchRecord。
      适合快速功能验证，但不是完整的端到端流程。
"""
import json
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/research/state/{thread_id} — 状态查询
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchState:

    def test_state_nonexistent_thread(self, client):
        """SqliteSaver 对未知线程返回空状态（非 None），端点返回 200 + 空快照"""
        resp = client.get("/api/research/state/nonexistent-thread")
        # SqliteSaver.get_state() 返回空 StateSnapshot，get_thread_state 将其序列化为快照
        assert resp.status_code == 200
        data = resp.json()
        # 空快照中 thread_id 为空字符串
        assert data["thread_id"] == ""
        assert data["current_step"] == ""


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/research/simple — 非流式端点（极简，不操作数据库）
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchSimple:

    def test_returns_final_snapshot(self, client, mock_research_success):
        """非流式端点应返回完整的最终快照"""
        resp = client.post("/api/research/simple", json={
            "query": "EGFR mutation lung cancer treatment",
            "max_papers": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == "mock-tid"  # mock 默认 thread_id
        assert data["current_step"] == "完成"
        assert "final_report" in data
        assert data["final_report"] != ""
        assert data["errors"] == []

    def test_returns_error_on_failure(self, client, mock_research_error):
        """当 execute_research 产出错误时仍返回 200，调用方自行判断 errors 字段"""
        resp = client.post("/api/research/simple", json={
            "query": "test query",
            "max_papers": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) > 0

    def test_validation_min_query_length(self, client):
        """query 至少需要 5 个字符"""
        resp = client.post("/api/research/simple", json={
            "query": "ab",
            "max_papers": 5,
        })
        assert resp.status_code == 422

    def test_validation_max_papers_range(self, client):
        """max_papers 必须在 2-20 之间"""
        resp = client.post("/api/research/simple", json={
            "query": "valid query text here",
            "max_papers": 1,
        })
        assert resp.status_code == 422

        resp = client.post("/api/research/simple", json={
            "query": "valid query text here",
            "max_papers": 21,
        })
        assert resp.status_code == 422

    def test_default_max_papers(self, client, mock_research_success):
        """不传 max_papers 时使用默认值 5"""
        resp = client.post("/api/research/simple", json={
            "query": "EGFR mutation treatment options",
        })
        assert resp.status_code == 200

    def test_no_database_side_effects(self, client, mock_research_success, test_session_factory):
        """/simple 端点不操作数据库——不应创建 Conversation"""
        resp = client.post("/api/research/simple", json={
            "query": "novel immunotherapy approaches for melanoma",
        })
        assert resp.status_code == 200

        from backend.db.models import Conversation
        db = test_session_factory()
        convs = db.query(Conversation).all()
        db.close()
        assert len(convs) == 0  # /simple 不创建对话

    def test_conversation_id_not_validated_in_simple(self, client, mock_research_success):
        """/simple 端点不校验 conversation_id——传入任意值均返回 200"""
        resp = client.post("/api/research/simple", json={
            "query": "test query here",
            "conversation_id": "fake-conv-id-999",
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/research — SSE 流式端点（完整流程，包含数据库操作）
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchSSE:

    def test_sse_content_type(self, client, mock_research_success):
        """SSE 端点应返回 text/event-stream（FastAPI 会自动追加 charset）"""
        resp = client.post("/api/research", json={
            "query": "CRISPR gene editing clinical trials",
            "max_papers": 5,
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

    def test_sse_cache_headers(self, client, mock_research_success):
        """SSE 应有正确的缓存控制头"""
        resp = client.post("/api/research", json={
            "query": "PD-L1 inhibitor resistance mechanisms",
            "max_papers": 3,
        })
        assert resp.headers["cache-control"] == "no-cache"
        assert resp.headers["connection"] == "keep-alive"
        assert resp.headers["x-accel-buffering"] == "no"

    def test_sse_stream_produces_multiple_events(self, client, mock_research_success):
        """SSE 流应产生多个事件（mock 产生 2 个快照 + [DONE]）"""
        resp = client.post("/api/research", json={
            "query": "biomarker discovery for early cancer detection",
            "max_papers": 5,
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert len(events) >= 2
        assert events[-1] == "[DONE]"

    def test_sse_events_are_valid_json(self, client, mock_research_success):
        """每个 SSE 数据事件（[DONE] 除外）应为有效 JSON"""
        resp = client.post("/api/research", json={
            "query": "single cell RNA sequencing cancer",
            "max_papers": 3,
        })
        for event in _parse_sse(resp.text):
            if event == "[DONE]":
                continue
            data = json.loads(event)
            assert "thread_id" in data
            assert "current_step" in data
            assert "execution_log" in data

    def test_sse_snapshots_show_progress(self, client, mock_research_success):
        """快照应展示执行进度：第一个快照非'完成' → 最后一个快照为'完成'"""
        resp = client.post("/api/research", json={
            "query": "microbiome influence on immunotherapy",
            "max_papers": 5,
        })
        snapshots = []
        for event in _parse_sse(resp.text):
            if event == "[DONE]":
                break
            snapshots.append(json.loads(event))

        assert len(snapshots) >= 2
        assert snapshots[0]["current_step"] != "完成"
        assert snapshots[0]["final_report"] == ""
        assert snapshots[-1]["current_step"] == "完成"
        assert snapshots[-1]["final_report"] != ""

    def test_sse_creates_conversation_and_messages(self, client, mock_research_success, test_session_factory):
        """SSE 研究应自动创建 Conversation + user Message + assistant Message"""
        client.post("/api/research", json={
            "query": "CAR-T cell therapy solid tumors",
            "max_papers": 5,
        })

        from backend.db.models import Conversation, Message
        db = test_session_factory()
        conv = db.query(Conversation).first()
        assert conv is not None
        assert conv.title == "CAR-T cell therapy solid tumors"

        msgs = db.query(Message).filter_by(conversation_id=conv.id).all()
        assert len(msgs) >= 2  # user + assistant
        roles = [m.role for m in msgs]
        assert "user" in roles
        assert "assistant" in roles
        db.close()

    def test_sse_error_handling(self, client, mock_research_error):
        """execute_research 抛出异常时，SSE 应返回带 errors 的快照并以 [DONE] 正常结束"""
        resp = client.post("/api/research", json={
            "query": "this will cause an error in research",
            "max_papers": 5,
        })
        events = _parse_sse(resp.text)
        assert "[DONE]" in events

        error_found = any(
            event != "[DONE]" and json.loads(event).get("errors")
            for event in events
        )
        assert error_found, "应在 SSE 流中找到包含 errors 的快照"

    def test_sse_paused_at_review_search(self, client, mock_research_paused):
        """流程在 review_search 暂停时，SSE 应推送 is_paused=True 的快照"""
        resp = client.post("/api/research", json={
            "query": "EGFR inhibitor resistance",
            "max_papers": 5,
        })
        snapshots = [
            json.loads(event) for event in _parse_sse(resp.text)
            if event != "[DONE]"
        ]
        paused = [s for s in snapshots if s.get("is_paused")]
        assert len(paused) >= 1
        assert paused[0]["pause_point"] == "review_search"


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/research/resume — 恢复 SSE 流式端点
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchResume:

    def test_resume_sse_format(self, client, mock_resume_success):
        """恢复端点应返回 SSE 流"""
        resp = client.post("/api/research/resume", json={
            "thread_id": "test-thread-123",
            "user_action": "approve",
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        events = _parse_sse(resp.text)
        assert "[DONE]" in events

    def test_resume_approve_action(self, client, mock_resume_success):
        """user_action='approve' 应成功恢复执行"""
        resp = client.post("/api/research/resume", json={
            "thread_id": "test-thread-456",
            "user_action": "approve",
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert len(events) >= 2
        assert events[-1] == "[DONE]"

    def test_resume_retry_action(self, client, mock_resume_success):
        """user_action='retry' 应传递 feedback 和 adjusted_query"""
        resp = client.post("/api/research/resume", json={
            "thread_id": "test-thread-789",
            "user_action": "retry",
            "feedback": "结果不够精准，需要更关注T790M突变",
            "adjusted_query": "EGFR T790M mutation osimertinib resistance",
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1] == "[DONE]"

    def test_resume_select_action(self, client, mock_resume_success):
        """user_action='select' 应传递 selected_ids"""
        resp = client.post("/api/research/resume", json={
            "thread_id": "test-thread-012",
            "user_action": "select",
            "selected_ids": ["40000001", "40000002", "40000003"],
        })
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert events[-1] == "[DONE]"

    def test_resume_validation_missing_thread_id(self, client):
        """缺少必填字段 thread_id 应返回 422"""
        resp = client.post("/api/research/resume", json={
            "user_action": "approve",
        })
        assert resp.status_code == 422

    def test_resume_validation_invalid_action(self, client, mock_resume_success):
        """无效 user_action 值不触发 Pydantic 枚举校验（当前仅验证类型为 str）"""
        resp = client.post("/api/research/resume", json={
            "thread_id": "test-123",
            "user_action": "invalid_action_xyz",
        })
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# 端到端流程测试：SSE research → DB → conversations
# ═══════════════════════════════════════════════════════════════════════════════

class TestEndToEnd:

    def test_full_flow_sse(self, client, mock_research_success, test_session_factory):
        """端到端 SSE：研究 → 对话 → 消息 → 研究记录"""
        resp = client.post("/api/research", json={
            "query": "liquid biopsy circulating tumor DNA",
            "max_papers": 3,
        })
        assert resp.status_code == 200

        from backend.db.models import Conversation, Message, ResearchRecord
        db = test_session_factory()

        # 1. 验证对话
        conv = db.query(Conversation).first()
        assert conv is not None
        assert conv.title == "liquid biopsy circulating tumor DNA"

        # 2. 验证消息
        msgs = db.query(Message).filter_by(conversation_id=conv.id).all()
        assert len(msgs) >= 2
        roles = [m.role for m in msgs]
        assert "user" in roles
        assert "assistant" in roles

        # 3. 验证研究记录
        records = db.query(ResearchRecord).filter_by(conversation_id=conv.id).all()
        assert len(records) == 1
        assert records[0].status in ("completed", "running")
        db.close()

    def test_full_flow_sse_then_query_api(self, client, mock_research_success):
        """SSE 研究后可通过 conversation API 查询到完整数据"""
        # 执行研究
        client.post("/api/research", json={
            "query": "NGS-based cancer genomic profiling",
            "max_papers": 5,
        })

        # 通过 API 查询
        convs = client.get("/api/conversations").json()
        assert len(convs) == 1
        conv_id = convs[0]["id"]

        # 查询对话详情
        conv_detail = client.get(f"/api/conversations/{conv_id}").json()
        assert len(conv_detail["messages"]) >= 2
        assert len(conv_detail["research_records"]) == 1

        # 查询消息
        messages = client.get(f"/api/conversations/{conv_id}/messages").json()
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles

        # 验证研究记录
        record = conv_detail["research_records"][0]
        assert record["query"] == "NGS-based cancer genomic profiling"
        assert record["status"] in ("completed", "running")


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_sse(text: str) -> list[str]:
    """解析 SSE text/event-stream 响应，提取 data: 字段值"""
    events = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            events.append(line[6:])
        elif line == "data:":
            events.append("")
    return events
