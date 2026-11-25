"""Persisted logs and an in-process pub/sub bus for SSE streaming."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger
from app.core.redaction import redact_secrets
from app.database.session import session_scope
from app.models import AgentLog

app_logger = get_logger(__name__)

MAX_LOG_CHARS = 20_000


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, execution_id: int) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2000)
        self._subscribers[execution_id].add(queue)
        return queue

    def unsubscribe(self, execution_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subscribers = self._subscribers.get(execution_id)
        if not subscribers:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(execution_id, None)

    def publish(self, execution_id: int, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(execution_id, set())):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass


bus = EventBus()


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


class ExecutionLogger:
    def __init__(self, execution_id: int, event_bus: EventBus | None = None) -> None:
        self.execution_id = execution_id
        self.bus = event_bus or bus

    def log(self, level: str, message: str, stage: str | None = None) -> None:
        clean = redact_secrets(str(message))[:MAX_LOG_CHARS]
        app_logger.log(
            {"debug": 10, "info": 20, "warning": 30, "error": 40}.get(level, 20),
            "[execution %s] %s",
            self.execution_id,
            clean,
        )
        log_id: int | None = None
        created_at = iso_now()
        try:
            with session_scope() as session:
                entry = AgentLog(
                    execution_id=self.execution_id,
                    level=level,
                    stage=stage,
                    message=clean,
                )
                session.add(entry)
                session.flush()
                log_id = entry.id
                entry_created = entry.created_at
                if entry_created is not None:
                    created_at = entry_created.replace(tzinfo=UTC).isoformat()
        except Exception as exc:  # never let logging kill an execution
            app_logger.warning("Failed to persist execution log: %s", exc)
        self.bus.publish(
            self.execution_id,
            {
                "type": "log",
                "id": log_id,
                "level": level,
                "stage": stage,
                "message": clean,
                "created_at": created_at,
            },
        )

    def debug(self, message: str, stage: str | None = None) -> None:
        self.log("debug", message, stage)

    def info(self, message: str, stage: str | None = None) -> None:
        self.log("info", message, stage)

    def warning(self, message: str, stage: str | None = None) -> None:
        self.log("warning", message, stage)

    def error(self, message: str, stage: str | None = None) -> None:
        self.log("error", message, stage)

    def state(self, status: str, stage: str, **extra: Any) -> None:
        self.bus.publish(
            self.execution_id,
            {"type": "state", "status": status, "stage": stage, "at": iso_now(), **extra},
        )
