"""
测试对话管理端点：CRUD 对话 + 消息查询。

所有这些测试都使用真实的测试数据库（SQLite 临时文件），不依赖外部 API。
"""
import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/conversations — 创建对话
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreateConversation:

    def test_create_with_title(self, client):
        resp = client.post("/api/conversations", json={"title": "EGFR突变研究"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "EGFR突变研究"
        assert "id" in data
        assert data["status"] == "active"
        assert data["message_count"] == 0
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_default_title(self, client):
        """不传 title 时使用默认值"""
        resp = client.post("/api/conversations", json={})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "未命名研究"

    def test_create_with_long_title(self, client):
        """超长标题应被 Pydantic 验证拒绝（max 200 字符）"""
        long_title = "研" * 250
        resp = client.post("/api/conversations", json={"title": long_title})
        # ConversationCreate.title Field(max_length=200)，超长应返回 422
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/conversations — 列表查询
# ═══════════════════════════════════════════════════════════════════════════════

class TestListConversations:

    def test_list_empty(self, client):
        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_multiple(self, client):
        # 创建3个对话
        client.post("/api/conversations", json={"title": "研究A"})
        client.post("/api/conversations", json={"title": "研究B"})
        client.post("/api/conversations", json={"title": "研究C"})

        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        # 按 updated_at 倒序，最后创建的在最前
        assert data[0]["title"] == "研究C"
        assert data[2]["title"] == "研究A"

    def test_list_limit_50(self, client):
        """验证最多返回 50 条"""
        for i in range(55):
            client.post("/api/conversations", json={"title": f"研究{i}"})
        resp = client.get("/api/conversations")
        assert len(resp.json()) == 50


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/conversations/{conv_id} — 查看单个对话
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetConversation:

    def test_get_existing(self, client):
        create_resp = client.post("/api/conversations", json={"title": "测试对话"})
        conv_id = create_resp.json()["id"]

        resp = client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "测试对话"
        assert "messages" in data
        assert "research_records" in data
        assert isinstance(data["messages"], list)
        assert isinstance(data["research_records"], list)

    def test_get_nonexistent(self, client):
        resp = client.get("/api/conversations/nonexistent-id-12345")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "对话不存在"


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /api/conversations/{conv_id} — 更新对话标题
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateConversation:

    def test_update_title(self, client):
        create_resp = client.post("/api/conversations", json={"title": "旧标题"})
        conv_id = create_resp.json()["id"]

        resp = client.patch(f"/api/conversations/{conv_id}", json={"title": "新标题"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "新标题"

        # 验证持久化
        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.json()["title"] == "新标题"

    def test_update_nonexistent(self, client):
        resp = client.patch("/api/conversations/nonexistent", json={"title": "X"})
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# DELETE /api/conversations/{conv_id} — 删除对话
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeleteConversation:

    def test_delete_existing(self, client):
        create_resp = client.post("/api/conversations", json={"title": "待删除"})
        conv_id = create_resp.json()["id"]

        resp = client.delete(f"/api/conversations/{conv_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == conv_id

        # 确认已删除
        get_resp = client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent(self, client):
        resp = client.delete("/api/conversations/nonexistent")
        assert resp.status_code == 404

    def test_delete_cascades_messages(self, client, test_session_factory):
        """删除对话时，关联的消息也一并删除"""
        # 创建对话
        create_resp = client.post("/api/conversations", json={"title": "级联删除测试"})
        conv_id = create_resp.json()["id"]

        # 手动插入一条消息（模拟researcher端点的行为）
        from backend.db.models import Message
        db = test_session_factory()
        msg = Message(conversation_id=conv_id, role="user", content="test query")
        db.add(msg)
        db.commit()
        db.close()

        # 删除对话
        client.delete(f"/api/conversations/{conv_id}")

        # 验证消息也被删除
        db = test_session_factory()
        count = db.query(Message).filter_by(conversation_id=conv_id).count()
        db.close()
        assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/conversations/{conv_id}/messages — 获取消息列表
# ═══════════════════════════════════════════════════════════════════════════════

class TestGetMessages:

    def test_get_messages_empty(self, client):
        create_resp = client.post("/api/conversations", json={"title": "空对话"})
        conv_id = create_resp.json()["id"]

        resp = client.get(f"/api/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_messages_with_data(self, client, test_session_factory):
        """对话中有消息时可以查询到"""
        create_resp = client.post("/api/conversations", json={"title": "含消息的对话"})
        conv_id = create_resp.json()["id"]

        # 插入消息
        from backend.db.models import Message
        db = test_session_factory()
        for i, (role, content) in enumerate([
            ("user", "研究EGFR突变"),
            ("assistant", "好的，检索到5篇文献..."),
            ("user", "请对比分析"),
        ]):
            msg = Message(conversation_id=conv_id, role=role, content=content)
            db.add(msg)
        db.commit()
        db.close()

        resp = client.get(f"/api/conversations/{conv_id}/messages")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 3
        assert data[0]["role"] == "user"
        assert data[0]["content"] == "研究EGFR突变"
        assert data[1]["role"] == "assistant"
        assert data[2]["role"] == "user"

    def test_get_messages_nonexistent_conv(self, client):
        """不存在的对话返回空消息列表（或 404，取决于实现）"""
        resp = client.get("/api/conversations/nonexistent/messages")
        # 当前实现不检查对话是否存在，直接返回空消息列表
        assert resp.status_code == 200
        assert resp.json() == []

    def test_messages_ordered_by_created_at(self, client, test_session_factory):
        """消息按创建时间升序排列"""
        create_resp = client.post("/api/conversations", json={"title": "排序测试"})
        conv_id = create_resp.json()["id"]

        from backend.db.models import Message
        db = test_session_factory()
        msg1 = Message(conversation_id=conv_id, role="user", content="第一条")
        msg2 = Message(conversation_id=conv_id, role="assistant", content="第二条")
        msg3 = Message(conversation_id=conv_id, role="user", content="第三条")
        db.add_all([msg1, msg2, msg3])
        db.commit()
        db.close()

        resp = client.get(f"/api/conversations/{conv_id}/messages")
        data = resp.json()
        assert data[0]["content"] == "第一条"
        assert data[1]["content"] == "第二条"
        assert data[2]["content"] == "第三条"


# ═══════════════════════════════════════════════════════════════════════════════
# 边界条件测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationEdgeCases:

    def test_create_empty_json(self, client):
        resp = client.post("/api/conversations", json={})
        assert resp.status_code == 201

    def test_create_extra_fields_ignored(self, client):
        """多余的字段应被忽略"""
        resp = client.post("/api/conversations", json={
            "title": "正常标题",
            "extra_field": "should be ignored",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "正常标题"
        assert "extra_field" not in data

    def test_delete_then_get(self, client):
        """删除后再查询应返回 404"""
        create_resp = client.post("/api/conversations", json={"title": "临时"})
        conv_id = create_resp.json()["id"]
        client.delete(f"/api/conversations/{conv_id}")
        resp = client.get(f"/api/conversations/{conv_id}")
        assert resp.status_code == 404

    def test_double_delete_idempotent(self, client):
        """两次删除同一个对话"""
        create_resp = client.post("/api/conversations", json={"title": "两次删除"})
        conv_id = create_resp.json()["id"]
        resp1 = client.delete(f"/api/conversations/{conv_id}")
        assert resp1.status_code == 200
        resp2 = client.delete(f"/api/conversations/{conv_id}")
        assert resp2.status_code == 404
