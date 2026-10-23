"""Runtime settings, read from environment variables so the same code runs locally and in Lambda."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    region: str = field(default_factory=lambda: _env("TL_REGION", "us-west-2"))
    aws_profile: str | None = field(default_factory=lambda: os.environ.get("TL_AWS_PROFILE"))
    # Amazon Nova models through US cross-region inference profiles.
    model_pro: str = field(default_factory=lambda: _env("TL_MODEL_PRO", "us.amazon.nova-pro-v1:0"))
    model_lite: str = field(default_factory=lambda: _env("TL_MODEL_LITE", "us.amazon.nova-lite-v1:0"))
    embed_model: str = field(default_factory=lambda: _env("TL_EMBED_MODEL", "amazon.titan-embed-text-v2:0"))
    # "bedrock" calls real models; "stub" uses scripted offline models for tests and dry runs.
    llm_mode: str = field(default_factory=lambda: _env("TL_LLM_MODE", "bedrock"))
    embedder: str = field(default_factory=lambda: _env("TL_EMBEDDER", "hash"))
    guardrail_id: str | None = field(default_factory=lambda: os.environ.get("TL_GUARDRAIL_ID"))
    guardrail_version: str = field(default_factory=lambda: _env("TL_GUARDRAIL_VERSION", "DRAFT"))
    # Storage: "local" writes to a folder; "aws" uses S3 + DynamoDB.
    store: str = field(default_factory=lambda: _env("TL_STORE", "local"))
    local_dir: Path = field(default_factory=lambda: Path(_env("TL_LOCAL_DIR", str(REPO_ROOT / "runs"))))
    bucket: str | None = field(default_factory=lambda: os.environ.get("TL_BUCKET"))
    table: str | None = field(default_factory=lambda: os.environ.get("TL_TABLE"))
    library_dir: Path = field(
        default_factory=lambda: Path(_env("TL_LIBRARY_DIR", str(REPO_ROOT / "data" / "library")))
    )
    index_path: Path = field(
        default_factory=lambda: Path(
            _env("TL_INDEX_PATH", str(REPO_ROOT / "data" / "library" / "index.json"))
        )
    )
    policy_path: Path = field(
        default_factory=lambda: Path(
            _env("TL_POLICY_PATH", str(REPO_ROOT / "data" / "policy" / "bid_policy.json"))
        )
    )
    # Governance: budgets per run and per agent.
    run_token_budget: int = field(default_factory=lambda: int(_env("TL_RUN_TOKEN_BUDGET", "600000")))
    agent_model_calls: int = field(default_factory=lambda: int(_env("TL_AGENT_MODEL_CALLS", "12")))
    agent_tool_calls: int = field(default_factory=lambda: int(_env("TL_AGENT_TOOL_CALLS", "20")))
    max_rewrite_rounds: int = field(default_factory=lambda: int(_env("TL_MAX_REWRITE_ROUNDS", "2")))
    assess_batch_size: int = field(default_factory=lambda: int(_env("TL_ASSESS_BATCH", "10")))
    grounding_threshold: float = field(default_factory=lambda: float(_env("TL_GROUNDING_THRESHOLD", "0.6")))


# Approximate on-demand prices in USD per 1,000 tokens, used only for the cost shown in the trace.
# Override with TL_PRICE_<MODEL> if list prices change.
PRICES_PER_1K: dict[str, tuple[float, float]] = {
    "nova-pro": (0.0008, 0.0032),
    "nova-lite": (0.00006, 0.00024),
    "nova-micro": (0.000035, 0.00014),
    "titan-embed": (0.00002, 0.0),
}


def price_for(model_id: str) -> tuple[float, float]:
    for key, price in PRICES_PER_1K.items():
        if key in model_id:
            return price
    return (0.0, 0.0)


@cache
def get_settings() -> Settings:
    return Settings()
