# Agentic AI — Autonomous Enterprise Workflows

**ET AI Hackathon 2026 · Problem Statement 2**

A multi-agent system that takes full ownership of complex enterprise processes — meeting intelligence, employee onboarding, procurement-to-payment, contract lifecycle — with self-correction on failure and a complete audit trail of every decision.

---

## Quick Start

```bash
# 1. Clone and enter the project
cd agentic-ai-system

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (copy and edit .env)
cp .env.example .env
# Add your OPENAI_API_KEY or ANTHROPIC_API_KEY
# Without a key the system runs in mock LLM mode — great for demos

# 4. Start everything
./run.sh          # API on :8000  +  dashboard on :8501

# OR start individually
./run.sh api      # FastAPI server only
./run.sh dash     # Streamlit dashboard only
./run.sh test     # Run all unit tests

# OR with Docker
./run.sh docker   # docker-compose up --build
```

**API docs:** http://localhost:8000/docs  
**Dashboard:** http://localhost:8501

---

## Folder Structure

```
agentic-ai-system/
│
├── app/                        # FastAPI entry point
│   ├── main.py                 # App startup, lifespan, route registration
│   ├── routes.py               # All API endpoints
│   └── config.py               # Central config from .env
│
├── core/                       # Shared infrastructure (NEW)
│   ├── __init__.py             # Unified import surface
│   ├── state.py                # WorkflowStateDict TypedDict + helpers
│   ├── db.py                   # SQLAlchemy engine, session, ORM models
│   ├── llm_client.py           # LLM facade with retry/backoff
│   └── prompts.py              # Prompt management + validation
│
├── orchestrator/               # Brain — controls all workflow execution
│   ├── orchestrator.py         # Main controller: selects workflow, dispatches agents
│   ├── workflow_engine.py      # Loads and executes step definitions from JSON
│   ├── state_manager.py        # Persists WorkflowState to short-term memory
│   ├── exception_handler.py    # 3-level recovery: retry → human gate → skip
│   └── sla_manager.py          # SLA clock, breach probability, warnings
│
├── agents/                     # Specialist agents
│   ├── base_agent.py           # Abstract base: logging, audit, confidence scoring
│   ├── data_agent.py           # Fetches data from DB / APIs
│   ├── decision_agent.py       # Only agent that calls LLM; returns confidence score
│   ├── action_agent.py         # Executes actions: Slack, email, calendar, DB
│   ├── verification_agent.py   # Cross-checks outputs; flags low-confidence results
│   ├── monitoring_agent.py     # Activates health monitoring subsystem
│   └── communication_agent.py  # Coordinates inter-agent messaging via event bus
│
├── meeting_intelligence/       # Meeting transcript → tasks → tracking
│   ├── transcript_parser.py    # Cleans, segments, extracts speakers
│   ├── decision_extractor.py   # LLM extraction: decisions + action items → JSON
│   ├── task_generator.py       # Converts action items to Task objects with deadlines
│   ├── owner_assigner.py       # Maps speaker names → employee records + emails
│   ├── progress_tracker.py     # Polls task status; detects stalls
│   └── escalation_manager.py   # 3-level escalation: remind → reassign → alert
│
├── workflows/                  # Declarative workflow step definitions (JSON)
│   ├── meeting_workflow.json
│   ├── employee_onboarding.json
│   ├── procurement_to_payment.json
│   └── contract_lifecycle.json
│
├── health_monitoring/          # Parallel SLA watchdog
│   ├── drift_detector.py       # Step duration vs baseline; flags 1.5× overrun
│   ├── bottleneck_predictor.py # Predicts SLA breach; triggers reroute at 70%
│   ├── anomaly_detector.py     # Z-score outlier detection on retry/error rates
│   ├── reroute_engine.py       # Dynamically rewrites active step list
│   └── alert_manager.py        # Sends drift/breach/anomaly alerts via Slack+email
│
├── memory/                     # State storage
│   ├── short_term_memory.py    # In-process dict scoped to active workflow run
│   ├── long_term_memory.py     # JSON-backed persistent store: baselines, patterns
│   └── workflow_state_store.json
│
├── audit/                      # Append-only audit trail
│   ├── audit_logger.py         # Every agent action → one row in decision_logs
│   ├── decision_logs.json      # All decisions (append-only, never edited)
│   └── trace_logs.json         # One line per entry for grep/streaming
│
├── communication/              # Inter-agent messaging
│   ├── event_bus.py            # Async pub/sub; fire-and-forget event delivery
│   ├── message_queue.py        # Per-workflow FIFO queue (Redis-ready)
│   └── router.py               # Routes event types to the correct handler
│
├── tools/                      # External integrations
│   ├── slack_tool.py           # Slack API (mock mode without token)
│   ├── email_tool.py           # SMTP email (mock mode without credentials)
│   ├── calendar_tool.py        # Google Calendar (mock mode without credentials)
│   ├── db_tool.py              # SQLite / PostgreSQL (in-memory fallback)
│   └── api_clients.py          # Generic HTTP client for CRM/HRMS/ERP
│
├── llm/                        # LLM layer
│   ├── llm_client.py           # OpenAI / Anthropic / mock provider
│   ├── prompts.py              # All prompt templates in one place
│   └── chains.py               # LangChain / LangGraph chain definitions
│
├── dashboard/
│   └── streamlit_app.py        # Live dashboard: tasks, audit log, health, triggers
│
├── utils/
│   ├── logger.py               # Centralised logging config
│   └── helpers.py              # Shared utility functions
│
├── tests/
│   ├── test_meeting_intelligence.py
│   ├── test_orchestrator.py
│   ├── test_audit_logger.py
│   ├── test_health_monitoring.py
│   └── test_llm_and_core.py
│
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── run.sh
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/api/v1/health` | System health check |
| POST | `/api/v1/workflow/trigger` | Trigger any enterprise workflow |
| POST | `/api/v1/meeting/upload` | Upload a meeting transcript |
| GET  | `/api/v1/workflow/{id}/status` | Get real-time workflow status |
| GET  | `/api/v1/workflow/{id}/tasks` | Get tasks for a workflow |
| POST | `/api/v1/workflow/approve` | Human approves a gate |
| GET  | `/api/v1/audit/{workflow_id}` | Get full audit trail |
| GET  | `/api/v1/audit/all/recent` | Get recent audit entries |

### Example: Trigger onboarding

```bash
curl -X POST http://localhost:8000/api/v1/workflow/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_type": "onboarding",
    "payload": {
      "name": "Jane Doe",
      "department": "Engineering",
      "role": "Software Engineer",
      "manager": "manager@company.com"
    }
  }'
```

### Example: Upload meeting transcript

```bash
curl -X POST http://localhost:8000/api/v1/meeting/upload \
  -F "file=@your_meeting.txt"
```

---

## Architecture — How the Agents Talk

```
Trigger → app/routes.py
              ↓
        orchestrator.py          ← brain: selects workflow JSON
              ↓
        workflow_engine.py       ← loads step list, iterates
              ↓
    ┌─────────────────────────────┐
    │   Per step: dispatch agent   │
    │                              │
    │  data_agent    → fetches     │
    │  decision_agent→ LLM call    │
    │  verification  → quality     │
    │  action_agent  → executes    │
    │  comm_agent    → event bus   │
    └─────────────────────────────┘
              ↓
        audit_logger.py          ← every action logged
              ↓
      health_monitoring/         ← parallel SLA watchdog
              ↓
      dashboard/streamlit_app.py ← live view
```

---

## Error Recovery — Three Levels

| Level | Trigger | Action |
|-------|---------|--------|
| L1 | confidence < 0.7 or agent exception | Reprompt LLM with more context, retry up to 3× |
| L2 | 3 retries exhausted | Human gate via Slack/email; 30-min SLA window |
| L3 | Human gate timeout | Auto-skip step, log TIMEOUT, continue workflow |

All three levels write to `audit/decision_logs.json`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | `openai` / `anthropic` / `mock` |
| `OPENAI_API_KEY` | — | Required for OpenAI mode |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic mode |
| `LLM_MODEL` | `gpt-4o` | Model name |
| `DATABASE_URL` | `sqlite:///./agentic_ai.db` | Database connection string |
| `SLACK_BOT_TOKEN` | — | For real Slack messages |
| `SMTP_USER` / `SMTP_PASS` | — | For real email |
| `CONFIDENCE_THRESHOLD` | `0.7` | Below this → retry |
| `MAX_RETRIES` | `3` | Retries before human gate |
| `SLA_TIMEOUT_MINUTES` | `30` | Human gate window |
| `HEALTH_CHECK_INTERVAL_MINUTES` | `5` | Drift check frequency |

---

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific test file
python -m pytest tests/test_meeting_intelligence.py -v
python -m pytest tests/test_orchestrator.py -v
python -m pytest tests/test_audit_logger.py -v
python -m pytest tests/test_health_monitoring.py -v
python -m pytest tests/test_llm_and_core.py -v
```

Tests run entirely in mock mode — no API key or external services required.

---

## Business Impact

| Area | Before | After | Annual saving |
|------|--------|-------|---------------|
| Meeting follow-up | 45 min/meeting × 50/week | 5 min/meeting | ₹68.6 L |
| Employee onboarding | 6 hrs/hire | 90 min/hire | ₹28.8 L |
| SLA breach penalties | 36 breaches/yr | ~7 breaches/yr | ₹21.75 L |
| Decision rework | 15 errors/month | ~4 errors/month | ₹10.08 L |
| **Total** | | | **₹1.29 Cr/yr** |

*Assumptions: 500-person enterprise, ₹800/hr avg cost, ₹75K avg SLA penalty.*

---

## Tech Stack

- **FastAPI** — REST API
- **LangGraph / LangChain** — Agent orchestration
- **OpenAI GPT-4o / Claude claude-sonnet-4-6** — LLM backbone
- **SQLAlchemy + SQLite** — Database (PostgreSQL in production)
- **APScheduler** — Health monitor scheduling
- **Redis** — Message queue (optional, in-process fallback included)
- **Streamlit** — Live dashboard
- **Python 3.12**
