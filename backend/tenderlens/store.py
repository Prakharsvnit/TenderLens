"""The blackboard: typed agent messages, run records and trace events.

LocalStore writes to a folder (runs/<runId>/); AwsStore uses S3 for messages and files and DynamoDB
for run records, trace events and quotas. Agents never talk to each other directly; each one writes a
typed message here and the orchestrator passes the next agent its key.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from .config import get_settings
from .ontology.models import MESSAGE_TYPES, Envelope
from .trace import TraceEvent

M = TypeVar("M", bound=Envelope)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    # --- files -------------------------------------------------------------------------------
    def put_bytes(self, key: str, data: bytes) -> None:
        raise NotImplementedError

    def get_bytes(self, key: str) -> bytes:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    # --- typed messages ---------------------------------------------------------------------
    def put_message(self, message: Envelope) -> str:
        key = f"runs/{message.run_id}/{type(message).__name__}.json"
        self.put_bytes(key, message.model_dump_json(indent=1).encode())
        return key

    def get_message(self, run_id: str, cls: type[M]) -> M:
        raw = self.get_bytes(f"runs/{run_id}/{cls.__name__}.json")
        message = MESSAGE_TYPES[cls.__name__].model_validate_json(raw)  # schema check on read
        return message  # type: ignore[return-value]

    def put_json(self, key: str, value: Any) -> None:
        payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
        self.put_bytes(key, json.dumps(payload, indent=1, default=str).encode())

    def get_json(self, key: str) -> Any:
        return json.loads(self.get_bytes(key))

    # --- run records, trace, quotas -----------------------------------------------------------
    def update_run(self, run_id: str, **fields: Any) -> dict:
        raise NotImplementedError

    def get_run(self, run_id: str) -> dict:
        raise NotImplementedError

    def list_runs(self, owner: str | None = None) -> list[dict]:
        raise NotImplementedError

    def append_trace(self, events: list[TraceEvent]) -> None:
        raise NotImplementedError

    def get_trace(self, run_id: str) -> list[dict]:
        raise NotImplementedError

    def increment_quota(self, day: str) -> int:
        raise NotImplementedError

    def append_audit(self, run_id: str, actor: str, action: str, detail: dict) -> None:
        events = self._audit(run_id)
        events.append({"at": _now(), "actor": actor, "action": action, "detail": detail})
        self.put_json(f"runs/{run_id}/audit.json", events)

    def _audit(self, run_id: str) -> list:
        key = f"runs/{run_id}/audit.json"
        return self.get_json(key) if self.exists(key) else []


class LocalStore(Store):
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key.removeprefix("runs/")

    def put_bytes(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def update_run(self, run_id: str, **fields: Any) -> dict:
        key = f"runs/{run_id}/run.json"
        run = self.get_json(key) if self.exists(key) else {"run_id": run_id, "created_at": _now()}
        run.update(fields, updated_at=_now())
        self.put_json(key, run)
        return run

    def get_run(self, run_id: str) -> dict:
        return self.get_json(f"runs/{run_id}/run.json")

    def list_runs(self, owner: str | None = None) -> list[dict]:
        runs = [json.loads(p.read_text()) for p in self.root.glob("*/run.json")]
        runs = [r for r in runs if owner is None or r.get("owner") == owner]
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)

    def append_trace(self, events: list[TraceEvent]) -> None:
        if not events:
            return
        path = self._path(f"runs/{events[0].run_id}/trace.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for event in events:
                fh.write(event.model_dump_json() + "\n")

    def get_trace(self, run_id: str) -> list[dict]:
        path = self._path(f"runs/{run_id}/trace.jsonl")
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def increment_quota(self, day: str) -> int:
        key = f"runs/_quota/{day}.json"
        count = (self.get_json(key)["count"] if self.exists(key) else 0) + 1
        self.put_json(key, {"count": count})
        return count


def _to_ddb(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str), parse_float=Decimal)


def _from_ddb(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda d: float(d) if d % 1 else int(d)))


class AwsStore(Store):
    """S3 for messages and files; one DynamoDB table (PK/SK) for runs, trace, quotas."""

    def __init__(self, bucket: str, table: str):
        from . import aws

        self.bucket = bucket
        self.s3 = aws.s3()
        self.table = aws.dynamodb().Table(table)

    def put_bytes(self, key: str, data: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get_bytes(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.s3.exceptions.ClientError:
            return False

    def update_run(self, run_id: str, **fields: Any) -> dict:
        fields = {**fields, "updated_at": _now()}
        names = {f"#{k}": k for k in fields}
        values = {f":{k}": _to_ddb(v) for k, v in fields.items()}
        sets = ", ".join(f"#{k} = :{k}" for k in fields)
        result = self.table.update_item(
            Key={"PK": f"RUN#{run_id}", "SK": "META"},
            UpdateExpression=f"SET {sets}, #run_id = :run_id, #created_at = if_not_exists(#created_at, :now)",
            ExpressionAttributeNames={**names, "#run_id": "run_id", "#created_at": "created_at"},
            ExpressionAttributeValues={**values, ":run_id": run_id, ":now": _now()},
            ReturnValues="ALL_NEW",
        )
        return _from_ddb(result["Attributes"])

    def get_run(self, run_id: str) -> dict:
        item = self.table.get_item(Key={"PK": f"RUN#{run_id}", "SK": "META"}).get("Item")
        if not item:
            raise KeyError(run_id)
        return _from_ddb(item)

    def list_runs(self, owner: str | None = None) -> list[dict]:
        from boto3.dynamodb.conditions import Attr

        scan = self.table.scan(FilterExpression=Attr("SK").eq("META"))
        runs = [_from_ddb(i) for i in scan.get("Items", [])]
        runs = [r for r in runs if owner is None or r.get("owner") == owner]
        return sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)

    def append_trace(self, events: list[TraceEvent]) -> None:
        with self.table.batch_writer() as batch:
            for n, event in enumerate(events):
                item = _to_ddb(event.model_dump())
                item.update(PK=f"RUN#{event.run_id}", SK=f"TRACE#{event.at}#{n:04d}")
                batch.put_item(Item=item)

    def get_trace(self, run_id: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        items, kwargs = (
            [],
            {"KeyConditionExpression": Key("PK").eq(f"RUN#{run_id}") & Key("SK").begins_with("TRACE#")},
        )
        while True:
            page = self.table.query(**kwargs)
            items.extend(page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return [_from_ddb(i) for i in items]

    def increment_quota(self, day: str) -> int:
        result = self.table.update_item(
            Key={"PK": f"QUOTA#{day}", "SK": "GLOBAL"},
            UpdateExpression="ADD #c :one",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(result["Attributes"]["count"])


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        settings = get_settings()
        if settings.store == "aws":
            _store = AwsStore(settings.bucket or "", settings.table or "")
        else:
            _store = LocalStore(settings.local_dir)
    return _store


def set_store(store: Store) -> None:
    global _store
    _store = store
