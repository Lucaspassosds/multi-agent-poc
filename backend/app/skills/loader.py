"""Skills (topic: "skills") — packaged, on-demand expertise via filesystem SKILL.md.

Progressive disclosure: by default only a skill's one-line description sits in context
(list_skills); the full body is loaded (load_skill) only when a step decides it's relevant.
This is the provider-agnostic approach (works on Gemini now); the native Anthropic Agent
Skills API is the deferred, Claude-only alternative.
"""
# ── Concept: SKILLS ── filesystem SKILL.md, progressive disclosure: one-line descriptions in context, full body loaded on demand.
from pathlib import Path

# loader.py now lives inside app/skills/, so the SKILL.md data sits in the sibling definitions/ dir.
_SKILLS_DIR = Path(__file__).parent / "definitions"


def _parse(md: str) -> tuple[dict, str]:
    """Split simple `---` YAML-ish frontmatter (key: value) from the body."""
    meta: dict[str, str] = {}
    body = md
    if md.startswith("---"):
        _, fm, body = md.split("---", 2)
        for line in fm.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta, body.strip()


def list_skills() -> list[dict]:
    """One-line descriptions only (what stays in context by default)."""
    out = []
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        meta, _ = _parse(skill_md.read_text())
        out.append({"name": meta.get("name", skill_md.parent.name),
                    "description": meta.get("description", "")})
    return out


def load_skill(name: str) -> str | None:
    """Full skill body — loaded on demand when a task calls for it."""
    path = (_SKILLS_DIR / name / "SKILL.md").resolve()
    if _SKILLS_DIR.resolve() not in path.parents or not path.exists():
        return None
    _, body = _parse(path.read_text())
    return body
