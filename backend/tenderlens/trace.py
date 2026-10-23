"""Per-run trace: every agent step, model call, tool call, token count, cost and latency.

The same events feed the app's Trace tab, the orchestration evals and the cost governance checks.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import BaseModel, Field

from .config import get_settings, price_for


class TraceEvent(BaseModel):
    run_id: str
    step: str
    agent: str
    kind: str  # agent_start | model_call | tool_call | validation | checkpoint | error | agent_end
    name: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    detail: str = ""
    at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class BudgetExceeded(RuntimeError):
    pass


class Tracer:
    def __init__(self, run_id: str, step: str, tokens_used_before: int = 0):
        self.run_id = run_id
        self.step = step
        self.events: list[TraceEvent] = []
        self.tokens_used = tokens_used_before
        self._lock = threading.RLock()  # parallel agent instances share one tracer

    def add(self, agent: str, kind: str, **fields) -> TraceEvent:
        event = TraceEvent(run_id=self.run_id, step=self.step, agent=agent, kind=kind, **fields)
        with self._lock:
            self.events.append(event)
            self.tokens_used += fields.get("tokens_in", 0) + fields.get("tokens_out", 0)
        return event

    def check_budget(self) -> None:
        budget = get_settings().run_token_budget
        if self.tokens_used >= budget:
            raise BudgetExceeded(f"run token budget of {budget:,} reached ({self.tokens_used:,} used)")

    @contextmanager
    def agent(self, agent: str, detail: str = ""):
        self.check_budget()
        start = time.perf_counter()
        self.add(agent, "agent_start", detail=detail)
        try:
            yield
        except Exception as exc:
            self.add(agent, "error", name=type(exc).__name__, detail=str(exc)[:500])
            raise
        finally:
            self.add(agent, "agent_end", latency_ms=int((time.perf_counter() - start) * 1000))

    def record_messages(self, agent: str, messages: list[BaseMessage]) -> None:
        """Turn an agent's message history into model_call and tool_call events."""
        for message in messages:
            if isinstance(message, AIMessage):
                usage = message.usage_metadata or {}
                meta = message.response_metadata or {}
                model_id = meta.get("model_id") or meta.get("model_name") or ""
                tin, tout = usage.get("input_tokens", 0), usage.get("output_tokens", 0)
                pin, pout = price_for(model_id or get_settings().model_pro)
                latency = meta.get("metrics", {}).get("latencyMs", [0])
                self.add(
                    agent,
                    "model_call",
                    name=model_id,
                    tokens_in=tin,
                    tokens_out=tout,
                    cost_usd=round(tin / 1000 * pin + tout / 1000 * pout, 6),
                    latency_ms=int(latency[0] if isinstance(latency, list) and latency else latency or 0),
                    detail=", ".join(tc["name"] for tc in message.tool_calls or []),
                )
            elif isinstance(message, ToolMessage):
                self.add(
                    agent,
                    "tool_call",
                    name=message.name or "",
                    detail=str(message.content)[:300],
                )

    @property
    def cost_usd(self) -> float:
        return round(sum(e.cost_usd for e in self.events), 6)
