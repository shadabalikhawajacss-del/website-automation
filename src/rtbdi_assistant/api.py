from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .answers import answer_from_exports
from .automation.playwright_runner import BrowserConfig, PlaywrightReportRunner
from .cli import _download_or_fallback_export
from .home import answer_home_question, extract_home_snapshot
from .intent import ConversationMemory
from .llm import select_live_intent
from .models import DateRange
from .planner import plan_question


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    answer: str
    canonical_question: str
    memory_used: bool
    reports_used: list[str]
    date_range: dict[str, str]
    rows_used: int
    notes: list[str] = []


def create_app() -> FastAPI:
    app = FastAPI(title="RT BDI AI Reporting Assistant")
    cors_origins = [origin.strip() for origin in os.getenv("RTBDI_CORS_ORIGINS", "*").split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "browser": "playwright-chromium"}

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        memory_dir = Path(os.getenv("RTBDI_MEMORY_DIR", ".rtbdi-api-memory"))
        memory_dir.mkdir(parents=True, exist_ok=True)
        safe_session = "".join(ch for ch in request.session_id if ch.isalnum() or ch in {"-", "_"}) or "default"
        memory_path = memory_dir / f"{safe_session}.json"
        memory = ConversationMemory.load(memory_path)
        with TemporaryDirectory() as tmpdir:
            intent = select_live_intent(request.question, memory)
            if intent.needs_clarification:
                return ChatResponse(
                    answer=intent.needs_clarification,
                    canonical_question=intent.canonical_question,
                    memory_used=intent.memory_used,
                    reports_used=[],
                    date_range={},
                    rows_used=0,
                    notes=[intent.reasoning] if intent.reasoning else [],
                )
            config = BrowserConfig.from_env(downloads_dir=Path(tmpdir) / "downloads")
            if intent.report_ids == ("home_dashboard",):
                try:
                    async with PlaywrightReportRunner(config) as runner:
                        page = await runner.new_page()
                        if not config.storage_state:
                            await runner.login(page)
                        await page.goto(config.base_url, wait_until="domcontentloaded")
                        snapshot = await extract_home_snapshot(page)
                    result = answer_home_question(intent.canonical_question, snapshot)
                    memory.update(result.context)
                    memory.save(memory_path)
                    return ChatResponse(
                        answer=result.answer,
                        canonical_question=intent.canonical_question,
                        memory_used=intent.memory_used,
                        reports_used=list(result.reports_used),
                        date_range={
                            "start": result.date_range.start.isoformat(),
                            "end": result.date_range.end.isoformat(),
                            "label": result.date_range.label,
                        },
                        rows_used=result.rows_used,
                        notes=list(result.notes),
                    )
                except Exception as exc:
                    raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

            plan = plan_question(intent.canonical_question)
            if plan.needs_clarification:
                return ChatResponse(
                    answer=plan.needs_clarification,
                    canonical_question=intent.canonical_question,
                    memory_used=intent.memory_used,
                    reports_used=[],
                    date_range={"start": plan.date_range.start.isoformat(), "end": plan.date_range.end.isoformat(), "label": plan.date_range.label},
                    rows_used=0,
                    notes=list(plan.notes),
                )

            try:
                exports = {}
                async with PlaywrightReportRunner(config) as runner:
                    for report_id in intent.report_ids:
                        from .knowledge import load_knowledge

                        report = load_knowledge().get(report_id)
                        page = await runner.new_page()
                        if not config.storage_state:
                            await runner.login(page)
                        await runner.open_report(page, report)
                        await runner.set_date_range(page, plan.date_range, required=False)
                        await runner.generate(page, required=False)
                        exports[report_id] = await _download_or_fallback_export(runner, page, report_id)
                result = answer_from_exports(intent.canonical_question, exports)
                memory.update(result.context)
                memory.save(memory_path)
                return ChatResponse(
                    answer=result.answer,
                    canonical_question=intent.canonical_question,
                    memory_used=intent.memory_used,
                    reports_used=list(result.reports_used),
                    date_range={
                        "start": result.date_range.start.isoformat(),
                        "end": result.date_range.end.isoformat(),
                        "label": result.date_range.label,
                    },
                    rows_used=result.rows_used,
                    notes=list(result.notes),
                )
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

    @app.get("/home-snapshot")
    async def home_snapshot() -> dict:
        try:
            config = BrowserConfig.from_env()
            async with PlaywrightReportRunner(config) as runner:
                page = await runner.new_page()
                if not config.storage_state:
                    await runner.login(page)
                await page.goto(config.base_url, wait_until="domcontentloaded")
                snapshot = await extract_home_snapshot(page)
                return {
                    "url": snapshot.url,
                    "top_stores": snapshot.top_stores,
                    "period_summary": snapshot.period_summary,
                    "today_snapshot": snapshot.today_snapshot,
                    "previous_day_rows": snapshot.previous_day_rows,
                    "chart_tables": snapshot.chart_tables,
                }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("rtbdi_assistant.api:app", host="0.0.0.0", port=8000)
