"""Shared boto3 clients, created lazily so tests and offline runs never need AWS credentials."""

from __future__ import annotations

from functools import cache

import boto3
from botocore.config import Config

from .config import get_settings

_RETRY = Config(retries={"max_attempts": 8, "mode": "adaptive"}, read_timeout=300)


@cache
def session() -> boto3.Session:
    settings = get_settings()
    return boto3.Session(profile_name=settings.aws_profile, region_name=settings.region)


@cache
def bedrock_runtime():
    return session().client("bedrock-runtime", config=_RETRY)


@cache
def s3():
    return session().client("s3")


@cache
def dynamodb():
    return session().resource("dynamodb")


@cache
def stepfunctions():
    return session().client("stepfunctions")


@cache
def ssm():
    return session().client("ssm")
