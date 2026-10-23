"""Chat model factory: Amazon Nova through ChatBedrockConverse, or a scripted stub for offline runs.

The stub lets the whole multi-agent pipeline run end to end without AWS (tests, UI work, dry runs).
Each agent supplies its own script, which sees the conversation and the bound tool names and returns
the next AIMessage, including tool calls, exactly like a real model would.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool

from .aws import bedrock_runtime
from .config import get_settings

StubScript = Callable[[list[BaseMessage], list[str]], AIMessage]
_ids = itertools.count(1)


def tool_call(name: str, args: dict) -> dict:
    return {"name": name, "args": args, "id": f"stub-{next(_ids)}", "type": "tool_call"}


def _estimate_tokens(messages: Sequence[BaseMessage]) -> int:
    return sum(len(str(m.content)) for m in messages) // 4


class StubChatModel(BaseChatModel):
    """Deterministic offline model driven by a per-agent script."""

    script: Any
    model_id: str = "stub"
    tool_names: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "tenderlens-stub"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> StubChatModel:
        names = [convert_to_openai_tool(t)["function"]["name"] for t in tools]
        return self.model_copy(update={"tool_names": names})

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:
        message = self.script(messages, self.tool_names)
        tokens_in = _estimate_tokens(messages)
        tokens_out = max(len(str(message.content)) // 4 + 40 * len(message.tool_calls or []), 1)
        message.usage_metadata = {
            "input_tokens": tokens_in,
            "output_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        }
        message.response_metadata = {"model_id": self.model_id, "metrics": {"latencyMs": [5]}}
        return ChatResult(generations=[ChatGeneration(message=message)])


def get_chat_model(kind: str, stub: StubScript | None = None) -> BaseChatModel:
    """kind is 'pro' (reasoning agents) or 'lite' (narrow checks)."""
    settings = get_settings()
    model_id = settings.model_pro if kind == "pro" else settings.model_lite
    if settings.llm_mode == "stub":
        if stub is None:
            raise ValueError("stub mode needs a stub script")
        return StubChatModel(script=stub, model_id=f"stub-{kind}")
    from langchain_aws import ChatBedrockConverse

    # Nova calls tools most reliably with greedy decoding (temperature 0, topK 1), and a structured answer can be
    # long, so the output limit is generous: an answer cut off mid tool call fails the whole step.
    return ChatBedrockConverse(
        model_id=model_id,
        client=bedrock_runtime(),
        temperature=0.0,
        max_tokens=8000 if kind == "pro" else 4000,
        additional_model_request_fields={"inferenceConfig": {"topK": 1}},
    )
