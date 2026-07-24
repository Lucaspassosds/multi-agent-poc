"""Agent system prompts, externalized from code so wording changes don't touch pipeline logic.

Data lives in the sibling prompts.json; this just loads it once at import time.
"""
import json
from pathlib import Path

PROMPTS: dict[str, str] = json.loads((Path(__file__).parent / "prompts.json").read_text())
