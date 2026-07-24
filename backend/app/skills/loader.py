"""Skills (topic: "skills") — a real library with 3-level progressive disclosure.

Level 1 (always in context): each skill's name + one-line description + allowed-tools
         (list_skills) — cheap, so the base prompt never carries skill bodies.
Level 2 (on relevance):      the SKILL.md body (load_skill) — loaded when a skill is selected.
Level 3 (on demand):         bundled references/ and executable scripts/ (run_skill_script) —
         loaded/run only when the body calls for them.

Provider-agnostic (works on Gemini now); the native Anthropic Agent Skills API is the
deferred, Claude-only alternative.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import yaml

_SKILLS_DIR = Path(__file__).parent / "definitions"


def _parse(md: str) -> tuple[dict, str]:
    """Split real YAML frontmatter (--- ... ---) from the markdown body."""
    if md.startswith("---"):
        parts = md.split("---", 2)
        if len(parts) == 3:
            meta = yaml.safe_load(parts[1]) or {}
            return (meta if isinstance(meta, dict) else {}), parts[2].strip()
    return {}, md.strip()


def _skill_dir(name: str) -> Path | None:
    """Resolve + containment-check a skill directory under definitions/."""
    path = (_SKILLS_DIR / name).resolve()
    if _SKILLS_DIR.resolve() not in path.parents and path != _SKILLS_DIR.resolve():
        return None
    return path if (path / "SKILL.md").exists() else None


def list_skills() -> list[dict]:
    """Level 1: names + one-line descriptions + allowed-tools (what stays in context)."""
    out = []
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = _parse(skill_md.read_text())
        out.append({
            "name": meta.get("name", skill_md.parent.name),
            "description": meta.get("description", ""),
            "allowed_tools": meta.get("allowed-tools", []),
        })
    return out


def skill_meta(name: str) -> dict | None:
    d = _skill_dir(name)
    if d is None:
        return None
    meta, _ = _parse((d / "SKILL.md").read_text())
    return meta


def load_skill(name: str) -> str | None:
    """Level 2: the full SKILL.md body — loaded on demand when a task calls for it."""
    d = _skill_dir(name)
    if d is None:
        return None
    _, body = _parse((d / "SKILL.md").read_text())
    return body


def skill_markdown(name: str) -> str | None:
    """The raw SKILL.md (frontmatter + body) — for the skill:// MCP resource."""
    d = _skill_dir(name)
    return (d / "SKILL.md").read_text() if d else None


def list_scripts(name: str) -> list[str]:
    """Level 3 discovery: executable scripts bundled with a skill."""
    d = _skill_dir(name)
    if d is None or not (d / "scripts").is_dir():
        return []
    return sorted(p.name for p in (d / "scripts").glob("*.py"))


async def run_skill_script(name: str, script: str, args: dict | None = None) -> dict:
    """Level 3 execution: run a bundled script in a subprocess, passing args as JSON
    on argv[1] and parsing JSON from stdout. Returns {"ok": bool, "output"|"error": ...}.

    Containment: the script must resolve inside this skill's scripts/ dir — no traversal."""
    d = _skill_dir(name)
    if d is None:
        return {"ok": False, "error": f"unknown skill {name}"}
    script_path = (d / "scripts" / script).resolve()
    if (d / "scripts").resolve() not in script_path.parents or not script_path.exists():
        return {"ok": False, "error": f"script {script} not found in skill {name}"}

    proc = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path), json.dumps(args or {}),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {"ok": False, "error": stderr.decode()[:500] or f"exit {proc.returncode}"}
    try:
        return {"ok": True, "output": json.loads(stdout.decode())}
    except json.JSONDecodeError:
        return {"ok": False, "error": f"non-JSON script output: {stdout.decode()[:300]}"}
