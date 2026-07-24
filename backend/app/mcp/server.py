"""Standalone MCP server (topic: "MCP") — all three primitives.

Exposes the reworked tool registry over the Model Context Protocol (Streamable
HTTP) so ANY MCP-aware client — our own backend, Claude Desktop, an MCP
inspector — can discover and call them. Adds the two primitives most POCs skip:
RESOURCES (URI-addressed context data) and PROMPTS (user-controlled templates ->
slash commands).

Single source of truth: tool coroutines, typed output models, and annotations
are IMPORTED from app/tools/registry.py — this file declares none of them, so
the "write once, reuse anywhere" claim is literally true.

Run as its own container: `python -m app.mcp.server` (docker-compose `mcp`).

Why the backend talks to this over a LOCAL MCP client instead of the Anthropic
API's `mcp_servers` connector: this server lives on the private docker network
with no public URL, and the connector requires a publicly reachable endpoint.
The local-client path is therefore the correct integration here (kept from the
original design).
"""
import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.db import get_pool
from app.skills.loader import list_skills, skill_markdown
from app.tools import registry as r

mcp = FastMCP("support-kb", host="0.0.0.0", port=9000)


def _ann(name: str) -> ToolAnnotations:
    """Wrap the registry's single-source annotation dict in the MCP type."""
    return ToolAnnotations(**r.ANNOTATIONS[name])


# --------------------------------------------------------------------------- #
# Primitive 1 — Tools (thin wrappers; behavior + annotations come from registry)
# --------------------------------------------------------------------------- #
@mcp.tool(annotations=_ann("hybrid_search"), structured_output=True)
async def hybrid_search(query: str, k: int = 5,
                        source_type: str | None = None) -> r.HybridSearchResult:
    """Search the knowledge base and past resolved tickets for relevant passages."""
    return await r.hybrid_search(query=query, k=k, source_type=source_type)


@mcp.tool(annotations=_ann("get_document"), structured_output=True)
async def get_document(document_id: int) -> r.DocumentResult:
    """Fetch the full text of a knowledge-base document by its numeric id."""
    return await r.get_document(document_id=document_id)


@mcp.tool(annotations=_ann("get_ticket"), structured_output=True)
async def get_ticket(ticket_id: str) -> r.TicketResult:
    """Fetch a past resolved ticket and its resolution by ticket id."""
    return await r.get_ticket(ticket_id=ticket_id)


@mcp.tool(annotations=_ann("lookup_customer"), structured_output=True)
async def lookup_customer(customer_id: str | None = None,
                          email: str | None = None) -> r.CustomerResult:
    """Look up a customer by customer_id or email."""
    return await r.lookup_customer(customer_id=customer_id, email=email)


@mcp.tool(annotations=_ann("get_payment_status"), structured_output=True)
async def get_payment_status(payment_id: str) -> r.PaymentStatusResult:
    """Get the status and metadata of a payment by payment_id."""
    return await r.get_payment_status(payment_id=payment_id)


@mcp.tool(annotations=_ann("check_refund_eligibility"), structured_output=True)
async def check_refund_eligibility(payment_id: str) -> r.RefundEligibilityResult:
    """Decide whether a payment can be refunded by running the refund-policy skill script."""
    return await r.check_refund_eligibility(payment_id=payment_id)


@mcp.tool(annotations=_ann("load_skill"), structured_output=True)
async def load_skill(name: str) -> r.SkillBody:
    """Load a skill's full body (level 2)."""
    return await r.load_skill_tool(name=name)


@mcp.tool(annotations=_ann("run_skill_script"), structured_output=True)
async def run_skill_script(name: str, script: str,
                           args: dict | None = None) -> r.SkillScriptResult:
    """Run a bundled skill script (level 3) with JSON args."""
    return await r.run_skill_script_tool(name=name, script=script, args=args)


@mcp.tool(annotations=_ann("escalate"), structured_output=True)
async def escalate(reason: str, ticket_ref: str | None = None,
                   severity: str = "medium") -> r.EscalateResult:
    """Propose escalating to a human (gated — writes nothing; needs approval)."""
    return await r.escalate(ticket_ref=ticket_ref, reason=reason, severity=severity)


# --------------------------------------------------------------------------- #
# Primitive 2 — Resources (application-controlled context data, URI-addressed)
# --------------------------------------------------------------------------- #
@mcp.resource("kb://index", mime_type="application/json")
async def kb_index() -> str:
    """Browsable catalog of KB documents: id, title, source_type."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, title, source_type, external_id FROM documents ORDER BY source_type, id"
    )
    return json.dumps([
        {"id": r_["id"], "title": r_["title"], "source_type": r_["source_type"],
         "external_id": r_["external_id"]}
        for r_ in rows
    ])


@mcp.resource("kb://doc/{doc_id}", mime_type="text/markdown")
async def kb_doc(doc_id: str) -> str:
    """A single KB document as markdown (metadata header + content)."""
    doc = await r.get_document(document_id=int(doc_id))
    if not doc.found:
        return f"# Not found\n\nNo document with id {doc_id}."
    return (f"# {doc.title}\n\n"
            f"_source_type: {doc.source_type}_  \n"
            f"_url: {doc.url or '(synthetic)'}_\n\n{doc.content}")


@mcp.resource("ticket://{external_id}", mime_type="text/markdown")
async def ticket_resource(external_id: str) -> str:
    """A seeded past ticket (precedent) as markdown."""
    t = await r.get_ticket(ticket_id=external_id)
    if not t.found:
        return f"# Not found\n\nNo ticket {external_id}."
    return f"# {t.subject}\n\n{t.content}\n\n---\nmetadata: {json.dumps(t.metadata)}"


@mcp.resource("skill://{name}", mime_type="text/markdown")
async def skill_resource(name: str) -> str:
    """A skill's SKILL.md (ties MCP <-> spec 04)."""
    md = skill_markdown(name)
    return md if md is not None else f"# Not found\n\nNo skill '{name}'."


# --------------------------------------------------------------------------- #
# Primitive 3 — Prompts (user-controlled templates -> slash commands)
# --------------------------------------------------------------------------- #
@mcp.prompt(title="Triage a refund request")
def triage_refund(ticket: str) -> str:
    """Seed a refund-triage conversation for a customer ticket."""
    return (
        "You are a payments support triage assistant. Triage this refund request:\n\n"
        f"{ticket}\n\n"
        "Steps: (1) hybrid_search the KB + past tickets for the refund policy and precedent; "
        "(2) if a payment id is present, call get_payment_status then check_refund_eligibility; "
        "(3) draft a concise, cited, customer-ready reply. If it cannot be resolved, call escalate."
    )


@mcp.prompt(title="Draft a customer reply")
def draft_reply(ticket: str, findings: str = "") -> str:
    """Draft a customer reply from a ticket + retrieved context."""
    return (
        "Draft a warm, concise, customer-ready reply grounded ONLY in the findings below. "
        "Cite article titles in-line. Never invent policy.\n\n"
        f"Ticket:\n{ticket}\n\nFindings:\n{findings or '(retrieve with hybrid_search first)'}"
    )


@mcp.prompt(title="Summarize a ticket thread")
def summarize_thread(thread: str) -> str:
    """Summarize a ticket thread into a short status + next action."""
    return ("Summarize this support thread in 3 bullets (what happened, current status, next action):\n\n"
            f"{thread}")


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
