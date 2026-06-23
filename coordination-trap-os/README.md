# Golden Gate Institute for AI — AI-Native Relationship & Events Operating System (Prototype)

A runnable prototype of the operating model from *The Coordination Trap*, specialized
for the **Golden Gate Institute for AI** — a nonprofit that convenes influential leaders
across the AI ecosystem through dinners, salons, workshops, and **The Curve** conference.

> **Traditional organizations** make humans *pull* information from systems — checking
> Attio, spreadsheets, email, Slack, and the news by hand.
>
> **AI-native organizations** *push* the right people, perspectives, conversations,
> risks, and decisions to humans at the right moment.
>
> Golden Gate's leaders decide **which conversations need to happen.**
> The AI Operating System figures out **how to make them happen.**

The Institute's primary asset is **the network of relationships among influential people
in the AI ecosystem.** This OS exists to grow, maintain, and activate that network — and
to free Steve, Taren, and Jon to spend their time on judgment, not coordination.

> This is the same platform as the original Product OS prototype, **converted** to the
> relationship/events domain. The architecture is unchanged — FastAPI, SQLite, the Work
> Graph (nodes + edges), the agent framework, events, approvals, the daily-briefing
> orchestrator, the context/goals/risk layers, node versioning, and n8n integration.

---

## The demo scenario — The Curve 2027

**Topic:** Future of Frontier AI Governance · **Location:** San Francisco · **Target:** 250 attendees · **~4 weeks out.**

The system assembles one **Daily Executive Briefing** for the leadership team instead of
making them check six systems. In the seeded scenario: confirmed RSVPs are **behind**
target, **no keynote is locked**, the **policy bloc exceeds the 35% viewpoint-balance
limit**, **civil-society and open-weights voices are missing**, three **VIP invitations**
(Demis, the EU AI Office, Fei) are unanswered, an emerging founder's profile is **stale**
in Attio (Mira left OpenAI), and the **open-weights** topic just went hot. The agents
detect all of it, synthesize the risks, recommend introductions, and prepare decision
briefs for human sign-off.

---

## Architecture (the book's three layers)

```
Layer 1 — Systems of Record    Attio CRM · Google Sheets/Docs · Email · Slack ·
   (mocked here)               public web · AI news feeds · research & policy trackers
        │   (n8n fetches / webhooks)
        ▼
Layer 2 — AI Operating System  Work Graph · Agents · Memory · Rules · Goals ·
                               Workflows · n8n orchestration
        │   (push: people, perspectives, intros, risks, decisions, approvals)
        ▼
Layer 3 — Human Judgment       Steve Newman (President) · Taren Stinebrickner-Kauffman (CEO) ·
                               Jon Finley (COO)
```

### The agents (organizational services, not chatbots)

| Agent | What it does |
|-------|--------------|
| **Relationship Intelligence** | Detects job/org changes, emerging influence, missing profile data; proposes enrichments |
| **Community Intelligence** | Tracks communities & influence networks; identifies emerging leaders and ecosystem shifts |
| **Topic Development** | Monitors AI news / research / policy; proposes topics, themes, and speakers |
| **Network Gap** | Analyzes coverage vs community targets and the viewpoint-balance principle; finds missing voices |
| **Event Matching** | Scores and ranks candidate attendees on seniority, expertise, attendance, relationships, diversity |
| **Invitation** | Tracks the invitation/RSVP pipeline; flags VIP RSVP risk and recommends follow-ups |
| **Event Operations** | Tracks readiness, capacity, and speaker confirmation; raises logistics warnings |
| **Relationship Facilitator** | Recommends high-value, cross-community introductions |
| **Post-Event Knowledge** | Captures outcomes, records introductions, surfaces open/overdue follow-ups |
| **Risk Watcher** | Synthesizes cross-functional risk: attendance, program, perspective, relationship, data-quality, follow-up, decision, strategic, governance |
| **Decision Facilitator** | Turns decision-risk into human-ready briefs (keynote selection, viewpoint rebalance) |
| **Documentation Steward** | Writes risks, decisions, and recommended introductions back to the Work Graph; raises approvals |
| **Strategy** | Maintains the company→department→role goal cascade; drafts goals for human ratification |

The **Executive Briefing** is produced by the orchestrator that runs this pipeline each
morning (see `app/briefing.py`). Agents analyze the Work Graph **deterministically**
(reproducible, like real monitoring agents) and use the pluggable LLM layer only to turn
findings into narrative — see [`app/llm.py`](app/llm.py).

---

## The Work Graph

A property graph (`nodes` + `edges`) holding the relationship/event entities — **person,
organization, community, ai_lab, event, theme, topic, invitation, rsvp, attendance,
follow_up, introduction, publication, policy_initiative, goal, risk, decision** — and
relationships such as *person belongs_to organization*, *organization part_of community*,
*person knows person*, *event discusses topic*, *event includes speaker*, *invitation
sent_to person*, *person introduced_to person*, *follow_up assigned_to person*, *decision
affects event*, *goal cascades_to goal*. Schema: [`app/schema.sql`](app/schema.sql).

Risks, decision briefs, and recommended introductions are **not** seeded — the agents
generate them at brief time and the Documentation Steward writes them back, demonstrating
the push model. Node edits are **versioned** (`node_versions`) so memory evolves with a trail.

---

## Goals & Context (Memory + Rules)

**Goal cascade** (company → department → role), authored in-OS or synced from an OKR tool:

```
Build stronger connections across frontier AI labs        → Steve (President)
  Make The Curve 2027 the definitive frontier-governance convening
    Confirm 6 frontier-lab principals · Hold viewpoint balance · 20% international [draft]
Increase policy & governance participation                → Taren (CEO)
Improve diversity of viewpoints across convenings         → Steve (President)
Flawless invitation → RSVP → execution pipeline           → Jon (COO)
```

**Organizational Context** (`/context-ui`) is the standing knowledge the agents reason
with: who we are, our positioning (*the trusted convener of frontier-AI governance
dialogue*), curation **principles** (Chatham House Rule, viewpoint balance, every invite
flows through a relationship), and **rules** (VIP sign-off, balance gate, privacy). These
flow into the agents — e.g. the Network Gap Agent enforces the 35% balance limit and the
Decision Facilitator cites the balance principle.

---

## Quick start

```bash
cd coordination-trap-os
./run.sh                       # → http://localhost:8000   (no API keys needed; mock LLM)
```

Manual equivalent:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.seed             # seed the Work Graph
uvicorn app.main:app --reload  # http://localhost:8000
```

### Front end — a four-level operating model

The home view (`/`) is the **Operating Model**, four navigable levels:

| Level | URL | What it is |
|-------|-----|-----------|
| **L1 · Human Roles** | `/roles` | CRUD list of roles; each carries a job description (responsibilities, owned goals, decision authority). |
| **L2 · Partner Agents** | `/partners` | One partner agent per role — the human's inbox. Push events arrive with recommended responses; the human **ignores, accepts a recommendation, or writes their own** (persisted, and preserved across re-scans). |
| **L3 · Service Agents** | `/services` | The shared coordination roster (Status Checker, Dependency Checker, Risk Watcher, Decision Agent, Planner, Documentation Agent, Escalation Agent, Meeting Agent) **plus** the Golden Gate domain agents. |
| **L4 · Automations** | `/automations` | The n8n workflows and the company systems (Attio, Sheets, Slack, email, news…) they wire to. |

The partner-agent inbox is generated by re-bucketing the live agent pipeline's findings to the **owning role** (decisions → President, strategic/governance → CEO, attendance/relationship/follow-ups → COO, etc.), each with recommended actions. Responses are stored as `push_event` nodes in the Work Graph and logged as `guidance` events.

### Detail views

| Tab | URL | Shows |
|-----|-----|-------|
| Executive Overview | `/executive` | Readiness, KPIs, what changed, company-goal exposure, agent trace |
| Community Overview | `/community` | Communities & network coverage vs target share |
| Events | `/events` | Convenings tracked by the OS |
| Invitations | `/invitations` | Invitation & RSVP pipeline |
| Attendees | `/attendees` | People in the network (seniority, geo, influence, emerging) |
| Topics | `/topics` | Topics & themes (Topic Development proposes new ones) |
| Speakers | `/speakers` | Speaker roster for The Curve 2027 |
| Relationship Graph | `/graph` | Known relationships + recommended introductions |
| Daily Brief | `/briefing` | The full 13-section executive briefing |
| Decisions | `/decisions` | Decision briefs + the risks behind them |
| Follow-Ups | `/followups` | Open & overdue follow-ups |
| Goals | `/goals-ui` | Goal cascade; author + review agent-drafted goals |
| Context | `/context-ui` | Memory + Rules (positioning, principles, guardrails) |
| Work Graph | `/workgraph-ui` | Every node and relationship |
| Approvals | `/approvals-ui` | Human approval flow |

---

## API endpoints (what n8n calls)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + config |
| GET | `/workgraph` · `/workgraph/node/{id}` | Full graph · node + neighbors + history |
| GET | `/goals` · POST `/goals` · `/goals/{id}/cascade` · `/goals/{id}/review` | Goal cascade |
| GET | `/context` · POST `/context` | Organizational context (memory + rules) |
| GET | `/briefings/daily` · `/briefings/latest` | Generate / fetch the executive briefing |
| POST | `/webhooks/n8n/daily-intelligence` | **n8n entry point** — runs the pipeline, returns brief + Slack message |
| POST | `/agents/{name}/run` | Run a single agent (e.g. `network-gap`, `event-matching`, `invitation`, `relationship-intelligence`, `topic-development`, `relationship-facilitator`, `post-event-knowledge`, `community-intelligence`, `event-operations`, `risk-watcher`, `strategy`) |
| POST | `/agents/decision-facilitator/brief` | Prepare decision briefs |
| GET/POST | `/approvals` · POST `/approvals/{id}/resolve` | Human approvals (approving updates the decision node) |
| GET | `/api/roles` · `/api/inbox/{role}` · `/api/services` · `/api/automations` | JSON for the four-level UI (roles, a partner inbox, the L3 roster, the L4 workflow/system map) |
| GET | `/mock/sources/{system}` | Mocked source data n8n would fetch: `attio`, `people`, `communities`, `events`/`sheets`, `news`/`ecosystem`, `goals`, `context`/`docs`, `changes` |

**CORS:** browser front ends (e.g. a v0 / Vercel app) may call the API directly.
Origins default to `*`; restrict with `CTOS_CORS_ORIGINS=https://your-app.vercel.app` (comma-separated).

Try it:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/webhooks/n8n/daily-intelligence | python -m json.tool
curl -s -X POST localhost:8000/agents/network-gap/run | python -m json.tool
```

---

## n8n workflows

Importable JSON in [`n8n/`](n8n/) — one per primary activity:

- `executive-brief-generation` — scheduled: fetch Attio/news/sheets → run pipeline → post to Slack
- `attio-sync` — periodic Attio pull → Relationship Intelligence → data-quality alerts
- `relationship-enrichment` — Attio-change webhook → Relationship Intelligence → enrichment suggestions
- `event-matching` — webhook → Event Matching → ranked attendee list
- `topic-development` — weekly news/research pull → Topic Development → topic & speaker ideas
- `invitation-follow-up` — daily → Invitation Agent → alert relationship owners on VIP RSVP risk
- `post-event-knowledge-capture` — event-closed webhook → Post-Event Knowledge → follow-up summary
- `relationship-graph-update` — daily → Relationship Facilitator → suggested introductions (written back to the graph)

**Import:** n8n → *Workflows* → *Import from File*. HTTP nodes call
`http://host.docker.internal:8000` (use `http://localhost:8000` if n8n runs natively).
Slack nodes need credentials — disable them to run end-to-end; output is still on the
dashboard and at `/briefings/latest`.

### Plugging in real systems later

Each `/mock/sources/{system}` endpoint is the seam. Replace those n8n HTTP nodes with real
Attio / Google Sheets / RSS / arXiv / policy-tracker nodes that emit the same shape, and
the rest of the pipeline is unchanged. To ingest live data into the graph, POST normalized
records to the upsert endpoints (mirror `app/seed.py`).

---

## Switching on a real LLM

Defaults to `mock` (deterministic, no key). To use Claude:

```bash
# .env
CTOS_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic
```

Test one narration without regenerating a brief:
`curl -X POST 'localhost:8000/admin/llm-test?provider=anthropic'`. Model defaults to
`claude-opus-4-8`; falls back to mock if the SDK/key is missing. No agent code changes —
only [`app/llm.py`](app/llm.py) switches providers.

---

## Project layout

```
app/
  main.py            FastAPI routes (API + n8n webhooks) + Jinja dashboard
  schema.sql         Work Graph schema (nodes, edges, node_versions, events, approvals, briefings)
  db.py · workgraph.py   SQLite + graph query/mutation helpers (incl. goal cascade, versioning)
  context_builder.py Assembles the context package (Layer 2)
  llm.py             Pluggable LLM layer (mock | anthropic | openai)
  briefing.py        Executive-brief orchestrator (runs the agent pipeline)
  executive.py       Goal-level rollup for leadership
  agents/            relationship_intelligence, community_intelligence, topic_development,
                     network_gap, event_matching, invitation, event_operations,
                     relationship_facilitator, post_event_knowledge, risk_watcher,
                     decision_facilitator, documentation_steward, strategy
  templates/ static/ dashboard UI
data/seed/*.json     Mocked systems of record (Attio people/orgs/communities, events, ecosystem, goals, context)
n8n/*.json           Importable workflows
```

## Reset the demo

```bash
curl -X POST localhost:8000/admin/reseed     # or: rm workgraph.db && ./run.sh
```

A prototype: SQLite, no auth, deterministic mock data. It exists to make the book's thesis
visible and runnable for Golden Gate, and to be a skeleton you extend.
