"""TenderLens domain ontology: the YAML source of truth and the Pydantic models generated from it."""

from functools import cache
from pathlib import Path

import yaml

from .models import *  # noqa: F403
from .models import Category

ONTOLOGY_PATH = Path(__file__).with_name("tenderlens.yaml")


@cache
def load_ontology() -> dict:
    return yaml.safe_load(ONTOLOGY_PATH.read_text(encoding="utf-8"))


def category_definitions() -> dict[Category, str]:
    """Category -> 'Label: definition', used in agent prompts and the search index."""
    cats = load_ontology()["categories"]
    return {Category(key): f"{value['label']}: {value['definition']}" for key, value in cats.items()}
