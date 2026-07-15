"""
FastAPI 服务 — Bioinformatics Agent REST API + SSE 流式端点。
v2.0: 支持多轮对话、人工干预（HITL）、对话持久化。
"""
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import config, PROJECT_ROOT
from backend.agent.executor import execute_research, resume_research
from backend.agent.graph import get_thread_state, new_thread_id
from backend.db.database import SessionLocal, get_db, init_db
from backend.db.models import Conversation, Message, ResearchRecord

logger = logging.getLogger(__name__)

# ── Lifespan ──


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    init_db()
    logger.info("Database and directories initialized")
    yield


# ── FastAPI App ──

app = FastAPI(
    title="Bioinformatics Agent API",
    description="AI 驱动的生物医学文献智能分析系统 v2.0",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求/响应模型 ──

class ResearchRequest(BaseModel):
    query: str = Field(..., description="研究问题", min_length=5)
    max_papers: int = Field(default=5, ge=2, le=20, description="最大文献数")
    conversation_id: Optional[str] = Field(default=None, description="对话 ID，不传则自动创建新对话")


class ResumeRequest(BaseModel):
    thread_id: str = Field(..., description="对话线程 ID")
    user_action: str = Field(..., description="approve / retry / select / revise")
    feedback: str = Field(default="", description="用户反馈文本")
    adjusted_query: str = Field(default="", description="调整后的检索式")
    selected_ids: list[str] = Field(default_factory=list, description="用户手动选择的 PMID 列表")


class ConversationCreate(BaseModel):
    title: str = Field(default="未命名研究", max_length=200)


# ═══════════════════════════════════════════════════════════════
# 核心研究端点
# ═══════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "Bioinformatics Agent", "version": "2.0.0"}


@app.post("/api/research")
async def research(request: ResearchRequest, db: Session = Depends(get_db)):
    """SSE 流式端点：执行完整研究流程，逐步返回执行状态。

    在 search 完成后会自动暂停（HITL 中断点1），前端需调用 /api/research/resume 继续。
    在 compare 完成后会再次暂停（HITL 中断点2）。
    """
    tid = new_thread_id()

    # 处理 conversation
    conv_id = request.conversation_id
    if not conv_id:
        conv = Conversation(title=request.query[:80])
        db.add(conv)
        db.commit()
        conv_id = conv.id
    else:
        conv = db.query(Conversation).filter_by(id=conv_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="对话不存在")

    # 保存用户消息
    user_msg = Message(conversation_id=conv_id, role="user", content=request.query)
    db.add(user_msg)
    db.commit()

    # 创建研究记录
    record = ResearchRecord(
        conversation_id=conv_id,
        thread_id=tid,
        query=request.query,
        max_papers=request.max_papers,
        status="running",
    )
    db.add(record)
    db.commit()

    async def event_stream() -> AsyncGenerator[str, None]:
        final_snapshot = None
        try:
            async for snapshot in execute_research(query=request.query,max_papers=request.max_papers,thread_id=tid,):
                final_snapshot = snapshot
                data = json.dumps(snapshot, ensure_ascii=False)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)

            # 保存 assistant 消息和研究结果
            if final_snapshot:
                _save_research_result(db, conv_id, tid, final_snapshot, record)

            yield "data: [DONE]\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_snapshot = {
                "thread_id": tid,
                "current_step": "执行出错",
                "plan_summary": "",
                "sub_tasks": [],
                "execution_log": [f"系统错误: {str(e)}"],
                "search_results_count": 0,
                "selected_papers_count": 0,
                "parsed_papers_count": 0,
                "comparison_report": "",
                "final_report": "",
                "errors": [f"{type(e).__name__}: {str(e)}"],
                "papers": [],
                "is_paused": False,
                "pause_point": "",
            }
            error_data = json.dumps(error_snapshot, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/research/resume")
async def research_resume(request: ResumeRequest, db: Session = Depends(get_db)):
    """SSE 流式端点：从 HITL 中断点恢复执行。

    当 graph 在 review_search 或 review_results 暂停后，
    前端收集用户决定（批准/重新搜索/手动选文献），调用此端点继续。
    """
    async def event_stream() -> AsyncGenerator[str, None]:
        final_snapshot = None
        try:
            async for snapshot in resume_research(
                thread_id=request.thread_id,
                user_action=request.user_action,
                feedback=request.feedback,
                adjusted_query=request.adjusted_query,
                selected_ids=request.selected_ids,
            ):
                final_snapshot = snapshot
                data = json.dumps(snapshot, ensure_ascii=False)
                yield f"data: {data}\n\n"
                await asyncio.sleep(0)

            # 更新研究记录
            if final_snapshot:
                record = db.query(ResearchRecord).filter_by(
                    thread_id=request.thread_id
                ).order_by(ResearchRecord.created_at.desc()).first()
                if record:
                    record.final_report = final_snapshot.get("final_report", "")
                    record.state_snapshot = final_snapshot
                    record.status = "paused" if final_snapshot.get("is_paused") else "completed"
                    db.commit()

            yield "data: [DONE]\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_data = json.dumps({
                "thread_id": request.thread_id,
                "current_step": "执行出错",
                "errors": [f"{type(e).__name__}: {str(e)}"],
                "execution_log": [],
                "final_report": "",
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/research/state/{thread_id}")
async def get_research_state(thread_id: str):
    """查询指定线程的当前状态（用于前端恢复断连后的 UI）"""
    state = get_thread_state(thread_id)
    if state is None:
        return JSONResponse({"error": "线程不存在或已过期"}, status_code=404)
    return JSONResponse(state)


@app.post("/api/research/simple")
async def research_simple(request: ResearchRequest):
    """非流式端点：返回完整结果（用于测试）"""
    final_snapshot = None
    async for snapshot in execute_research(
        query=request.query,
        max_papers=request.max_papers,
    ):
        final_snapshot = snapshot

    if final_snapshot is None:
        return JSONResponse({"error": "执行失败"}, status_code=500)

    return JSONResponse(final_snapshot)


# ═══════════════════════════════════════════════════════════════
# 对话管理端点
# ═══════════════════════════════════════════════════════════════

@app.get("/api/conversations")
async def list_conversations(db: Session = Depends(get_db)):
    """获取所有对话列表"""
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(50).all()
    return JSONResponse([c.to_dict() for c in convs])


@app.post("/api/conversations")
async def create_conversation(req: ConversationCreate, db: Session = Depends(get_db)):
    """创建新对话"""
    conv = Conversation(title=req.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return JSONResponse(conv.to_dict(), status_code=201)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    """获取单个对话详情（含消息历史）"""
    conv = db.query(Conversation).filter_by(id=conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    data = conv.to_dict()
    data["messages"] = [m.to_dict() for m in conv.messages]
    data["research_records"] = [r.to_dict() for r in conv.research_records]
    return JSONResponse(data)


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    """删除对话及其关联消息和研究记录"""
    conv = db.query(Conversation).filter_by(id=conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    db.delete(conv)
    db.commit()
    return JSONResponse({"deleted": conv_id})


@app.patch("/api/conversations/{conv_id}")
async def update_conversation(conv_id: str, req: ConversationCreate, db: Session = Depends(get_db)):
    """更新对话标题"""
    conv = db.query(Conversation).filter_by(id=conv_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    conv.title = req.title
    db.commit()
    return JSONResponse(conv.to_dict())


@app.get("/api/conversations/{conv_id}/messages")
async def get_messages(conv_id: str, db: Session = Depends(get_db)):
    """获取对话的所有消息"""
    messages = (
        db.query(Message)
        .filter_by(conversation_id=conv_id)
        .order_by(Message.created_at)
        .limit(200)
        .all()
    )
    return JSONResponse([m.to_dict() for m in messages])


# ═══════════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════════

def _save_research_result(
    db: Session,
    conv_id: str,
    thread_id: str,
    snapshot: dict,
    record: ResearchRecord,
):
    """保存 assistant 消息和研究结果到数据库"""
    final_report = snapshot.get("final_report", "")
    is_paused = snapshot.get("is_paused", False)

    # 保存 assistant 消息
    assistant_content = final_report if final_report else f"研究进行中... (当前步骤: {snapshot.get('current_step', '未知')})"
    assistant_msg = Message(
        conversation_id=conv_id,
        role="assistant",
        content=assistant_content,
        snapshot_json=snapshot,
    )
    db.add(assistant_msg)

    # 更新研究记录
    record.thread_id = thread_id
    record.final_report = final_report if final_report else None
    record.state_snapshot = snapshot
    record.status = "paused" if is_paused else ("completed" if final_report else "running")

    # 更新对话标题（用第一次查询的前80字符）
    conv = db.query(Conversation).filter_by(id=conv_id).first()
    if conv and conv.title == "未命名研究":
        query = snapshot.get("plan_summary", "") or record.query
        conv.title = query[:80] if query else "未命名研究"

    db.commit()


# ═══════════════════════════════════════════════════════════════
# 前端静态文件服务（Docker 单容器部署）
# ═══════════════════════════════════════════════════════════════

_FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    _dist = _FRONTEND_DIST.resolve()
    _assets = _dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{rest:path}")
    async def _spa_fallback(rest: str):
        # 先检查是否为 dist 中的真实文件（favicon.svg 等）
        requested = (_dist / rest).resolve()
        if str(requested).startswith(str(_dist)) and requested.is_file():
            return FileResponse(requested)
        # SPA 兜底
        index = _dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse("Frontend not built. Run: cd frontend && npm run build", status_code=404)
