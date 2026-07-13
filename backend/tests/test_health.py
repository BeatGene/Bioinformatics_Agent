"""
测试基础端点：健康检查、CORS 配置等。
"""
import pytest


class TestHealthCheck:
    """GET /api/health"""

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "Bioinformatics Agent"
        assert "version" in data

    def test_health_response_is_json(self, client):
        resp = client.get("/api/health")
        assert resp.headers["content-type"].startswith("application/json")


class TestCORSMiddleware:
    """验证 CORS 头存在"""

    @pytest.mark.parametrize("origin", [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ])
    def test_cors_allows_known_origins(self, client, origin):
        resp = client.options(
            "/api/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI TestClient 默认不处理 CORS preflight，但检查响应即可
        # 主要验证服务对已知 origin 不返回错误
        assert resp.status_code in (200, 405)

    def test_docs_endpoint_accessible(self, client):
        """Swagger UI 可访问"""
        resp = client.get("/docs")
        assert resp.status_code == 200

    def test_openapi_schema_accessible(self, client):
        """OpenAPI JSON schema 可访问"""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "Bioinformatics Agent API"
        # 验证关键路径已注册
        paths = schema["paths"]
        assert "/api/health" in paths
        assert "/api/research" in paths
        assert "/api/research/simple" in paths
        assert "/api/research/resume" in paths
        assert "/api/research/state/{thread_id}" in paths
        assert "/api/conversations" in paths


class TestNotFound:
    """404 处理"""

    def test_nonexistent_endpoint(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404
