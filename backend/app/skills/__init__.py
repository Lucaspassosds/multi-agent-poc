"""Skills (progressive disclosure) — public surface for the SKILL.md loader.

Re-exports the loader so call sites keep `from app.skills import ...`.
Skill *data* lives in definitions/<name>/SKILL.md; the loader lives in loader.py.
"""
from app.skills.loader import list_skills, load_skill  # noqa: F401

__all__ = ["list_skills", "load_skill"]
