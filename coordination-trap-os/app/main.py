"""FastAPI application: API endpoints (for n8n + UI) and the Jinja dashboard for
the AI-Native Relationship & Events Operating System (Golden Gate Institute)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import agents, briefing, config, context_builder as cb, db, executive, inbox, registry, seed
from . import workgraph as wg

app = FastAPI(title="Golden Gate :: AI-Native Relationship & Events OS", version="0.2.0")

# Allow a browser front end (e.g. a v0 / Vercel app) to call the API. With "*"
# we must not also send credentials, which is fine for this no-auth prototype.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials="*" not in config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE / "templates"))

CONTEXT_TYPES = ["org_profile", "positioning", "principle", "rule"]
AGENT_KEYS = {k: attr for k, attr in briefing.PIPELINE}


@app.on_event("startup")
def _startup() -> None:
    db.init_db()
    if not wg.all_nodes():
        seed.load(reset=True)


# ===========================================================================
# System
# ===========================================================================
@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": app.version, "llm_provider": config.LLM_PROVIDER,
            "nodes": len(wg.all_nodes()), "as_of": config.DEMO_TODAY}


@app.post("/admin/reseed")
def reseed() -> dict[str, Any]:
    return {"status": "reseeded", "graph": seed.load(reset=True)}


@app.post("/admin/llm-test")
def llm_test(provider: str | None = None) -> dict[str, Any]:
    from .llm import llm

    sample = {"headline": "The Curve 2027 is BEHIND on confirmed attendance.",
              "bullets": ["168 of 250 confirmed, 27 days out.",
                          "3 VIP invitations unanswered (Demis, EU AI Office, Fei).",
                          "No keynote locked; viewpoint balance not yet cleared."]}
    text = llm.narrate("Event Operations Agent", "Summarize event readiness for the leadership team.",
                       sample, provider=provider)
    return {"provider_requested": (provider or config.LLM_PROVIDER).lower(),
            "fell_back_to_mock": "using mock" in text, "output": text}


# ===========================================================================
# Work Graph
# ===========================================================================
@app.get("/workgraph")
def get_workgraph() -> dict[str, Any]:
    return {"summary": wg.graph_summary(), "nodes": wg.all_nodes(), "edges": wg.all_edges()}


@app.get("/workgraph/node/{node_id:path}")
def get_node(node_id: str) -> dict[str, Any]:
    node = wg.get_node(node_id)
    if not node:
        raise HTTPException(404, f"node not found: {node_id}")
    return {"node": node, "out": wg.neighbors(node_id, direction="out"),
            "in": wg.neighbors(node_id, direction="in"), "history": wg.node_history(node_id)}


# ===========================================================================
# Goals (company → department → role cascade)
# ===========================================================================
@app.get("/goals")
def get_goals() -> dict[str, Any]:
    return {"goal_tree": wg.goal_tree(), "flat": wg.nodes_by_type("goal")}


@app.post("/goals")
def upsert_goal(payload: dict[str, Any]) -> dict[str, Any]:
    import re

    scope = payload.get("scope", "company")
    gid = payload.get("id") or "goal:" + re.sub(r"[^a-z0-9]+", "-", payload.get("title", "goal").lower()).strip("-")[:48]
    data = {"scope": scope, **payload.get("data", {})}
    if payload.get("owner_role"):
        data["owner_role"] = payload["owner_role"]
    wg.upsert_node(gid, "goal", payload["title"], payload.get("status", "draft"), data)
    if payload.get("owner"):
        wg.add_edge(gid, "owned_by", payload["owner"])
    if payload.get("parent"):
        wg.add_edge(payload["parent"], "cascades_to", gid)
    wg.log_event(payload.get("source", "api"), "log", f"Upserted goal: {payload['title']}", node_id=gid)
    return {"id": gid, "status": payload.get("status", "draft")}


@app.post("/goals/{goal_id:path}/cascade")
def cascade_goal(goal_id: str) -> dict[str, Any]:
    return {"parent": goal_id, "proposed": agents.STRATEGY.propose_cascade(goal_id)}


@app.post("/goals/{goal_id:path}/review")
def review_goal(goal_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    node = wg.get_node(goal_id)
    if not node:
        raise HTTPException(404, f"goal not found: {goal_id}")
    decision = payload.get("decision", "approve")
    new_title = payload.get("title", node["title"])
    new_status = {"approve": "active", "reject": "rejected", "edit": node["status"]}.get(decision, node["status"])
    data = {**node["data"], **payload.get("data", {}), "reviewed_by": payload.get("reviewed_by", "human")}
    wg.upsert_node(goal_id, "goal", new_title, new_status, data)
    wg.log_event(f"human:{payload.get('reviewed_by','lead')}", "approval",
                 f"Goal {goal_id} {decision} → {new_status}", node_id=goal_id)
    return {"id": goal_id, "status": new_status}


# ===========================================================================
# Organizational Context (Memory + Rules)
# ===========================================================================
@app.get("/context")
def get_context() -> dict[str, Any]:
    return {t: wg.nodes_by_type(t) for t in CONTEXT_TYPES}


@app.post("/context")
def upsert_context(payload: dict[str, Any]) -> dict[str, Any]:
    import re

    ntype = payload.get("type")
    if ntype not in CONTEXT_TYPES:
        raise HTTPException(400, f"type must be one of {CONTEXT_TYPES}")
    cid = payload.get("id") or "ctx:" + re.sub(r"[^a-z0-9]+", "-", payload.get("title", "item").lower()).strip("-")[:48]
    wg.upsert_node(cid, ntype, payload["title"], payload.get("status", "active"), payload.get("data", {}))
    wg.log_event(payload.get("source", "api"), "log", f"Upserted context [{ntype}]: {payload['title']}", node_id=cid)
    return {"id": cid, "type": ntype}


# ===========================================================================
# Briefing
# ===========================================================================
@app.get("/briefings/daily")
def daily_brief(refresh: bool = True) -> dict[str, Any]:
    if not refresh:
        latest = _latest_brief()
        if latest:
            return latest
    return briefing.generate_daily_brief(persist=True)


@app.get("/briefings/latest")
def latest_brief() -> dict[str, Any]:
    latest = _latest_brief()
    if not latest:
        raise HTTPException(404, "no briefing generated yet")
    return latest


def _latest_brief() -> dict[str, Any] | None:
    with db.session() as conn:
        row = conn.execute("SELECT payload FROM briefings ORDER BY created_at DESC LIMIT 1").fetchone()
    return json.loads(row["payload"]) if row else None


# ===========================================================================
# n8n webhook — the scheduled-trigger entry point
# ===========================================================================
@app.post("/webhooks/n8n/daily-intelligence")
async def n8n_daily_intelligence(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        body = {}
    brief = briefing.generate_daily_brief(persist=True)
    return JSONResponse({"received_sources": list(body.keys()), "brief_id": brief.get("id"),
                         "slack_message": _slack_blocks(brief), "brief": brief})


def _slack_blocks(brief: dict[str, Any]) -> str:
    lines = [f"*{brief['title']} — {brief['org']} — {brief['for_date']}*",
             f"_{brief['event_focus']}_", "", "*What changed since yesterday*"]
    for c in brief["what_changed_since_yesterday"]:
        lines.append(f"• {c['summary']}")
    lines += ["", f"*Event readiness:* {brief['event_readiness']['headline']}",
              f"*Invitations:* {brief['invitation_status']['headline']}",
              f"*New risks:* {len(brief['new_risks'])}  |  *Decisions:* {len(brief['decisions_needed'])}  |  *Approvals waiting:* {len(brief['items_requiring_approval'])}"]
    if brief["recommended_actions"]:
        lines.append("\n*Recommended actions*")
        for a in brief["recommended_actions"]:
            lines.append(f"• {a['action']} — _{a['owner']}_ (due {a['due']})")
    return "\n".join(lines)


# ===========================================================================
# Agents — individually invokable services (n8n can call any of these)
# ===========================================================================
@app.post("/agents/{agent_key}/run")
def run_agent(agent_key: str) -> dict[str, Any]:
    """Run a single agent. The full pipeline runs so upstream findings exist;
    the requested agent's result is returned. agent_key e.g. 'network-gap'."""
    key = agent_key.replace("-", "_")
    if key not in AGENT_KEYS:
        raise HTTPException(404, f"unknown agent '{agent_key}'. Options: {sorted(AGENT_KEYS)}")
    _, domain = briefing.run_pipeline()
    return domain[key]


@app.post("/agents/decision-facilitator/brief")
def decision_brief() -> dict[str, Any]:
    _, domain = briefing.run_pipeline()
    return domain["decision_facilitator"]


# ===========================================================================
# Approvals — the human judgment layer
# ===========================================================================
@app.get("/approvals")
def list_approvals(status: str | None = None) -> dict[str, Any]:
    q, params = "SELECT * FROM approvals", ()
    if status:
        q += " WHERE status = ?"; params = (status,)
    q += " ORDER BY created_at DESC"
    with db.session() as conn:
        rows = conn.execute(q, params).fetchall()
    return {"approvals": [dict(r) for r in rows]}


@app.post("/approvals")
def create_approval(payload: dict[str, Any]) -> dict[str, Any]:
    import uuid

    aid = payload.get("id") or f"appr:{uuid.uuid4().hex[:8]}"
    with db.session() as conn:
        conn.execute(
            """INSERT INTO approvals (id, created_at, requested_by, owner_role, title, detail, related_node)
               VALUES (?, datetime('now'), ?, ?, ?, ?, ?)""",
            (aid, payload.get("requested_by", "api"), payload.get("owner_role", "President"),
             payload.get("title", "Approval requested"), payload.get("detail", ""), payload.get("related_node")))
    return {"id": aid, "status": "pending"}


@app.post("/approvals/{approval_id}/resolve")
def resolve_approval(approval_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision", "approved")
    if decision not in ("approved", "rejected"):
        raise HTTPException(400, "decision must be 'approved' or 'rejected'")
    with db.session() as conn:
        cur = conn.execute(
            """UPDATE approvals SET status=?, resolved_at=datetime('now'), resolved_by=?, note=?
               WHERE id=? AND status='pending'""",
            (decision, payload.get("resolved_by", "President"), payload.get("note", ""), approval_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "approval not found or already resolved")
        row = conn.execute("SELECT related_node FROM approvals WHERE id=?", (approval_id,)).fetchone()
    if row and row["related_node"]:
        node = wg.get_node(row["related_node"])
        if node:
            wg.upsert_node(node["id"], node["type"], node["title"],
                           "decided" if decision == "approved" else "rejected", node["data"])
    wg.log_event(f"human:{payload.get('resolved_by','leader')}", "approval",
                 f"Approval {approval_id} {decision}", node_id=row["related_node"] if row else None)
    return {"id": approval_id, "status": decision}


# ===========================================================================
# Mock systems-of-record sources (what n8n would fetch)
# ===========================================================================
@app.get("/mock/sources/{system}")
def mock_source(system: str) -> dict[str, Any]:
    fname = {"attio": "people.json", "people": "people.json", "orgs": "communities.json",
             "communities": "communities.json", "events": "events.json", "sheets": "events.json",
             "ecosystem": "ecosystem.json", "news": "ecosystem.json", "goals": "goals.json",
             "context": "context.json", "docs": "context.json", "changes": "changes.json"}.get(system)
    if not fname:
        raise HTTPException(404, f"unknown mock system '{system}'")
    return json.loads((config.SEED_DIR / fname).read_text())


# ===========================================================================
# Dashboard (Jinja)
# ===========================================================================
def _brief() -> dict[str, Any]:
    return _latest_brief() or briefing.generate_daily_brief(persist=True)


# -- Level 1–4 operating-model views --------------------------------------
@app.get("/", response_class=HTMLResponse)
def operating_model(request: Request) -> HTMLResponse:
    """The four-level operating model — the home view."""
    inbox.ensure()
    roles = wg.nodes_by_type("role")
    counts = inbox.counts_by_role()
    return templates.TemplateResponse(request, "model.html", {
        "roles": roles, "counts": counts,
        "services": registry.SERVICE_AGENTS, "workflows": registry.WORKFLOWS, "systems": registry.SYSTEMS,
        "provider": config.LLM_PROVIDER})


@app.get("/executive", response_class=HTMLResponse)
def executive_overview(request: Request) -> HTMLResponse:
    brief = _brief()
    return templates.TemplateResponse(request, "dashboard.html", {
        "brief": brief, "roll": executive.build(brief),
        "summary": wg.graph_summary(), "provider": config.LLM_PROVIDER})


# ===== Level 1 — Human Roles (CRUD) ======================================
@app.get("/roles", response_class=HTMLResponse)
def roles_page(request: Request) -> HTMLResponse:
    goals = {g["id"]: g["title"] for g in wg.nodes_by_type("goal")}
    return templates.TemplateResponse(request, "roles.html", {
        "roles": wg.nodes_by_type("role"), "goal_titles": goals, "counts": inbox.counts_by_role()})


@app.get("/roles/{role_id:path}", response_class=HTMLResponse)
def role_detail(request: Request, role_id: str) -> HTMLResponse:
    """A single role (L1) with its partner agent's live inbox (L2) embedded."""
    role = wg.get_node(role_id)
    if not role or role["type"] != "role":
        raise HTTPException(404, f"role not found: {role_id}")
    inbox.ensure()
    goals = {g["id"]: g["title"] for g in wg.nodes_by_type("goal")}
    return templates.TemplateResponse(request, "role_detail.html", {
        "role": role, "goal_titles": goals, "counts": inbox.counts_by_role().get(role_id, {"open": 0, "total": 0}),
        "events": inbox.for_role(role_id)})


@app.get("/api/roles")
def api_roles() -> dict[str, Any]:
    return {"roles": wg.nodes_by_type("role")}


@app.post("/roles")
def upsert_role(payload: dict[str, Any]) -> dict[str, Any]:
    import re

    rid = payload.get("id") or "role:" + re.sub(r"[^a-z0-9]+", "-", payload.get("title", "role").lower()).strip("-")[:40]
    existing = wg.get_node(rid)
    data = {**(existing["data"] if existing else {}), **payload.get("data", {})}
    for k in ("person_name", "partner_agent", "partner_blurb", "responsibilities", "owns", "decision_authority"):
        if k in payload:
            data[k] = payload[k]
    # Every role gets a partner agent — auto-provisioned on creation if not named.
    if not data.get("partner_agent"):
        data["partner_agent"] = f"{payload['title']} Partner"
    if not data.get("partner_blurb"):
        data["partner_blurb"] = (f"Partner agent for the {payload['title']} role — surfaces events "
                                 "from the org and recommends responses for sign-off.")
    wg.upsert_node(rid, "role", payload["title"], payload.get("status", "active"), data)
    wg.log_event(payload.get("source", "api"), "log",
                 f"Upserted role: {payload['title']} (+ partner: {data['partner_agent']})", node_id=rid)
    return {"id": rid, "partner_agent": data["partner_agent"]}


@app.post("/roles/{role_id:path}/delete")
def delete_role(role_id: str) -> dict[str, Any]:
    with db.session() as conn:
        conn.execute("DELETE FROM edges WHERE src = ? OR dst = ?", (role_id, role_id))
        conn.execute("DELETE FROM nodes WHERE id = ?", (role_id,))
    wg.log_event("api", "log", f"Deleted role {role_id}", node_id=role_id)
    return {"id": role_id, "deleted": True}


@app.post("/roles-ui/save")
def roles_ui_save(title: str = Form(...), id: str = Form(""), person_name: str = Form(""),
                  partner_agent: str = Form(""), partner_blurb: str = Form(""),
                  responsibilities: str = Form(""), decision_authority: str = Form("")) -> RedirectResponse:
    payload = {"title": title, "person_name": person_name, "partner_agent": partner_agent,
               "responsibilities": [s.strip() for s in responsibilities.splitlines() if s.strip()],
               "decision_authority": [s.strip() for s in decision_authority.splitlines() if s.strip()],
               "source": "roles-page"}
    if id:
        payload["id"] = id
    if partner_blurb:
        payload["partner_blurb"] = partner_blurb
    upsert_role(payload)
    return RedirectResponse("/roles", status_code=303)


@app.post("/roles-ui/{role_id:path}/delete")
def roles_ui_delete(role_id: str) -> RedirectResponse:
    delete_role(role_id)
    return RedirectResponse("/roles", status_code=303)


# ===== Level 2 — Partner-agent inboxes ===================================
@app.get("/partners", response_class=HTMLResponse)
def partners_page(request: Request) -> HTMLResponse:
    """L2 roster — one partner agent per role; click through to the role's inbox."""
    inbox.ensure()
    return templates.TemplateResponse(request, "partner_roster.html", {
        "roles": wg.nodes_by_type("role"), "counts": inbox.counts_by_role()})


@app.get("/api/inbox/{role_id:path}")
def api_inbox(role_id: str) -> dict[str, Any]:
    return {"role": role_id, "events": inbox.for_role(role_id)}


@app.post("/inbox/rebuild")
def inbox_rebuild() -> dict[str, Any]:
    return {"created": inbox.rebuild()}


@app.post("/inbox/{event_id:path}/respond")
def inbox_respond(event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return inbox.respond(event_id, payload.get("action", "ignore"),
                         payload.get("rec_index"), payload.get("response", ""))


@app.post("/partners/rebuild")
def partners_rebuild(role: str = Form(""), back: str = Form("")) -> RedirectResponse:
    inbox.rebuild()
    return RedirectResponse(back or (f"/roles/{role}" if role else "/partners"), status_code=303)


@app.post("/partners/{event_id:path}/respond")
def partners_respond(event_id: str, action: str = Form(...), role: str = Form(""),
                     rec_index: str = Form(""), response: str = Form(""), back: str = Form("")) -> RedirectResponse:
    inbox.respond(event_id, action, int(rec_index) if rec_index.isdigit() else None, response)
    return RedirectResponse(back or (f"/roles/{role}" if role else "/partners"), status_code=303)


# ===== Level 3 — service agents · Level 4 — automations ==================
@app.get("/services", response_class=HTMLResponse)
def services_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "services.html", {"services": registry.SERVICE_AGENTS})


@app.get("/api/services")
def api_services() -> dict[str, Any]:
    return {"services": registry.SERVICE_AGENTS}


@app.get("/automations", response_class=HTMLResponse)
def automations_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "automations.html", {
        "workflows": registry.WORKFLOWS, "systems": registry.SYSTEMS})


@app.get("/api/automations")
def api_automations() -> dict[str, Any]:
    return {"workflows": registry.WORKFLOWS, "systems": registry.SYSTEMS}


@app.get("/briefing", response_class=HTMLResponse)
def briefing_page(request: Request, refresh: bool = False) -> HTMLResponse:
    brief = briefing.generate_daily_brief(persist=True) if refresh else _brief()
    return templates.TemplateResponse(request, "briefing.html", {"brief": brief})


@app.get("/decisions", response_class=HTMLResponse)
def decisions_page(request: Request) -> HTMLResponse:
    brief = _brief()
    return templates.TemplateResponse(request, "decisions.html", {
        "brief": brief, "risk_nodes": wg.nodes_by_type("risk")})


# -- generic entity browser ------------------------------------------------
def _people_index() -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in wg.nodes_by_type("person")}


def _entity_rows(types: list[str]) -> list[dict[str, Any]]:
    rows = []
    for t in types:
        rows.extend(wg.nodes_by_type(t))
    return rows


@app.get("/events", response_class=HTMLResponse)
def events_page(request: Request) -> HTMLResponse:
    rows = [{"Title": e["title"], "Kind": e["data"].get("kind"), "Date": e["data"].get("date"),
             "Location": e["data"].get("location"),
             "Confirmed / Target": f"{e['data'].get('accepted','—')} / {e['data'].get('target_attendance','—')}",
             "Status": e["status"]} for e in wg.nodes_by_type("event")]
    return _entities(request, "Events", "Convenings tracked by the OS.", rows)


@app.get("/invitations", response_class=HTMLResponse)
def invitations_page(request: Request) -> HTMLResponse:
    people = _people_index()
    rows = []
    for inv in wg.nodes_by_type("invitation"):
        to = next((e["dst"] for e in wg.all_edges() if e["src"] == inv["id"] and e["rel"] == "sent_to"), None)
        rows.append({"Invitee": people.get(to, {}).get("title", to), "Status": inv["status"],
                     "Owner": people.get(inv["data"].get("owner"), {}).get("title", inv["data"].get("owner", "—")),
                     "VIP": "★" if inv["data"].get("vip") else "", "Sent": inv["data"].get("sent")})
    rows.sort(key=lambda r: (r["Status"] != "no_response", r["Status"]))
    return _entities(request, "Invitations", "Invitation & RSVP pipeline for The Curve 2027.", rows)


@app.get("/attendees", response_class=HTMLResponse)
def attendees_page(request: Request) -> HTMLResponse:
    rows = []
    for p in wg.nodes_by_type("person"):
        if p["data"].get("team"):
            continue
        org = next((e["dst"] for e in wg.all_edges() if e["src"] == p["id"] and e["rel"] == "belongs_to"), None)
        org_node = wg.get_node(org) if org else None
        rows.append({"Name": p["title"], "Role": p["data"].get("role"),
                     "Org": org_node["title"] if org_node else "—",
                     "Seniority": p["data"].get("seniority", "—"), "Geo": p["data"].get("geo", "—"),
                     "Influence": p["data"].get("influence", "—"),
                     "Emerging": "▲" if p["data"].get("emerging") else ""})
    rows.sort(key=lambda r: (r["Influence"] if isinstance(r["Influence"], (int, float)) else 0), reverse=True)
    return _entities(request, "Attendees", "People in the AI-ecosystem network.", rows)


@app.get("/topics", response_class=HTMLResponse)
def topics_page(request: Request) -> HTMLResponse:
    rows = [{"Topic": t["title"], "Heat": t["data"].get("heat", "—"), "Status": t["status"],
             "Note": t["data"].get("note", "")} for t in wg.nodes_by_type("topic")]
    return _entities(request, "Topics", "Discussion topics & themes (Topic Development Agent proposes new ones).", rows)


@app.get("/speakers", response_class=HTMLResponse)
def speakers_page(request: Request) -> HTMLResponse:
    people = _people_index()
    rows = []
    for sp in cb.speakers_for(cb.build(), "event:curve-2027"):
        p = people.get(sp["person"], {})
        rows.append({"Speaker": p.get("title", sp["person"]), "Status": sp["status"],
                     "Role": p.get("data", {}).get("role"), "Org/Lab": p.get("data", {}).get("org", "—")})
    return _entities(request, "Speakers", "Speaker roster for The Curve 2027.", rows)


@app.get("/followups", response_class=HTMLResponse)
def followups_page(request: Request) -> HTMLResponse:
    people = _people_index()
    rows = [{"Follow-up": f["title"], "Status": f["status"], "Due": f["data"].get("due"),
             "Owner": people.get(f["data"].get("owner"), {}).get("title", f["data"].get("owner", "—")),
             "From": f["data"].get("from_event", "—")} for f in wg.nodes_by_type("follow_up")]
    rows.sort(key=lambda r: r["Status"] != "overdue")
    return _entities(request, "Follow-Ups", "Open and overdue follow-ups (Post-Event Knowledge Agent).", rows)


@app.get("/community", response_class=HTMLResponse)
def community_page(request: Request) -> HTMLResponse:
    ctx = cb.build()
    counts = {}
    for p in ctx["people"]:
        if p["data"].get("team"):
            continue
        c = cb.community_of_person(ctx, p["id"])
        if c:
            counts[c] = counts.get(c, 0) + 1
    communities = []
    for c in ctx["communities"]:
        communities.append({"community": c, "count": counts.get(c["id"], 0),
                            "target": c["data"].get("target_share", 0)})
    return templates.TemplateResponse(request, "community.html", {
        "communities": communities, "labs": ctx["ai_labs"], "orgs": ctx["organizations"]})


@app.get("/graph", response_class=HTMLResponse)
def relationship_graph_page(request: Request) -> HTMLResponse:
    ctx = cb.build()
    people = _people_index()
    knows = [{"a": people.get(e["src"], {}).get("title", e["src"]),
              "b": people.get(e["dst"], {}).get("title", e["dst"])}
             for e in ctx["edges"] if e["rel"] == "knows"]
    intros = [{"title": i["title"], "status": i["status"], "reason": i["data"].get("reason", "")}
              for i in wg.nodes_by_type("introduction")]
    return templates.TemplateResponse(request, "relationship_graph.html", {
        "knows": knows, "intros": intros, "people": ctx["people"]})


@app.get("/workgraph-ui", response_class=HTMLResponse)
def workgraph_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "workgraph.html", {
        "summary": wg.graph_summary(), "nodes": wg.all_nodes(), "edges": wg.all_edges()})


@app.get("/context-ui", response_class=HTMLResponse)
def context_page(request: Request) -> HTMLResponse:
    context = {t: wg.nodes_by_type(t) for t in CONTEXT_TYPES}
    histories = {n["id"]: wg.node_history(n["id"]) for items in context.values() for n in items}
    return templates.TemplateResponse(request, "context.html", {
        "context": context, "types": CONTEXT_TYPES, "histories": histories})


@app.post("/context-ui/add")
def context_ui_add(type: str = Form(...), title: str = Form(...),
                   detail: str = Form(""), key: str = Form("")) -> RedirectResponse:
    data = {key: detail} if key and detail else ({"note": detail} if detail else {})
    upsert_context({"type": type, "title": title, "data": data, "source": "in-os-context-page"})
    return RedirectResponse("/context-ui", status_code=303)


@app.get("/goals-ui", response_class=HTMLResponse)
def goals_page(request: Request) -> HTMLResponse:
    people = {p["id"]: p["title"] for p in wg.nodes_by_type("person")}
    return templates.TemplateResponse(request, "goals.html", {"goal_tree": wg.goal_tree(), "people": people})


@app.post("/goals-ui/add")
def goals_ui_add(title: str = Form(...), scope: str = Form("company"),
                 owner_role: str = Form(""), parent: str = Form("")) -> RedirectResponse:
    upsert_goal({"title": title, "scope": scope, "owner_role": owner_role,
                 "parent": parent or None, "status": "active", "source": "in-os-goals-page"})
    return RedirectResponse("/goals-ui", status_code=303)


@app.post("/goals-ui/{goal_id:path}/review")
def goals_ui_review(goal_id: str, decision: str = Form(...), title: str = Form("")) -> RedirectResponse:
    payload = {"decision": decision, "reviewed_by": "Role Lead"}
    if decision == "edit" and title:
        payload["title"] = title
    review_goal(goal_id, payload)
    return RedirectResponse("/goals-ui", status_code=303)


@app.post("/goals-ui/{goal_id:path}/cascade")
def goals_ui_cascade(goal_id: str) -> RedirectResponse:
    cascade_goal(goal_id)
    return RedirectResponse("/goals-ui", status_code=303)


@app.get("/approvals-ui", response_class=HTMLResponse)
def approvals_page(request: Request) -> HTMLResponse:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall()
    return templates.TemplateResponse(request, "approvals.html", {"approvals": [dict(r) for r in rows]})


@app.post("/approvals-ui/{approval_id}/resolve")
def approvals_ui_resolve(approval_id: str, decision: str = Form(...), note: str = Form("")) -> RedirectResponse:
    resolve_approval(approval_id, {"decision": decision, "note": note, "resolved_by": "Steve Newman"})
    return RedirectResponse("/approvals-ui", status_code=303)


def _entities(request: Request, title: str, intro: str, rows: list[dict[str, Any]]) -> HTMLResponse:
    columns = list(rows[0].keys()) if rows else []
    return templates.TemplateResponse(request, "entities.html",
                                      {"title": title, "intro": intro, "columns": columns, "rows": rows})
