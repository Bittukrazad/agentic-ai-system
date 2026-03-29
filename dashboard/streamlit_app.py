"""dashboard/streamlit_app.py — Live Streamlit dashboard"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

st.set_page_config(
    page_title="Agentic AI — Workflow Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .badge-green {background:#e1f5ee;color:#085041;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500}
    .badge-red   {background:#fcebeb;color:#791f1f;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500}
    .badge-amber {background:#faeeda;color:#633806;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500}
    .badge-blue  {background:#e6f1fb;color:#0c447c;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:500}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SESSION STATE
# =============================================================================
if "task_overrides" not in st.session_state:
    st.session_state.task_overrides = {}


def apply_override(task_id, new_status, updated_by="employee"):
    now = datetime.now(timezone.utc).isoformat()
    st.session_state.task_overrides[task_id] = {
        "status": new_status, "updated_by": updated_by, "updated_at": now,
    }
    # Try RAM
    try:
        from memory.short_term_memory import ShortTermMemory, _store
        for key, value in list(_store.items()):
            if key.startswith("tracker:") and key.endswith(":tasks"):
                for task in value:
                    if task.get("id") == task_id:
                        task["status"]     = new_status
                        task["updated_at"] = now
                ShortTermMemory.set(key, value)
    except Exception:
        pass
    # Try DB
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "..", "agentic_ai.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("UPDATE task_records SET status=?, updated_at=? WHERE task_id=?",
                         (new_status, now, task_id))
            conn.commit()
            conn.close()
    except Exception:
        pass


def merge_overrides(tasks):
    for task in tasks:
        tid = task.get("id", "")
        if tid in st.session_state.task_overrides:
            o = st.session_state.task_overrides[tid]
            task["status"]     = o["status"]
            task["updated_by"] = o.get("updated_by", "")
            task["updated_at"] = o.get("updated_at", "")
    return tasks


def fmt_deadline(deadline_str):
    """Format deadline nicely. Returns '—' if empty."""
    if not deadline_str:
        return "—"
    try:
        dl = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
        return dl.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return str(deadline_str)[:16] if deadline_str else "—"


def is_overdue(deadline_str):
    """Check if deadline has passed"""
    if not deadline_str:
        return False
    try:
        dl  = datetime.fromisoformat(str(deadline_str).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return now > dl
    except Exception:
        return False


# =============================================================================
# DATA LOADERS
# =============================================================================

@st.cache_data(ttl=3)
def load_audit_log():
    path = os.path.join(os.path.dirname(__file__), "..", "audit", "decision_logs.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


@st.cache_data(ttl=3)
def load_long_term_memory():
    path = os.path.join(os.path.dirname(__file__), "..", "memory", "workflow_state_store.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def load_active_workflows():
    try:
        from memory.short_term_memory import ShortTermMemory
        ids = ShortTermMemory.all_workflow_ids()
        return [s for wid in ids if (s := ShortTermMemory.get_state(wid))]
    except Exception:
        return []


def load_all_workflows_from_audit():
    """Reconstruct workflow history from audit log."""
    audit_entries = load_audit_log()
    workflows     = {}
    for entry in audit_entries:
        wid    = entry.get("workflow_id", "")
        action = entry.get("action", "")
        if not wid:
            continue
        if wid not in workflows:
            workflows[wid] = {
                "workflow_id":   wid,
                "workflow_type": "unknown",
                "status":        "running",
                "started_at":    entry.get("timestamp", ""),
                "completed_at":  "",
                "steps":         [],
                "total_retries": 0,
                "sla_breached":  False,
                "tasks_count":   0,
                "confidence_avg":[],
            }
        wf  = workflows[wid]
        inp = entry.get("input_summary", "")
        if "type=" in inp:
            for t in ["meeting", "onboarding", "procurement", "contract"]:
                if t in inp:
                    wf["workflow_type"] = t
                    break
        if action == "WORKFLOW_STARTED":
            wf["started_at"] = entry.get("timestamp", "")
            for t in ["meeting", "onboarding", "procurement", "contract"]:
                if t in inp:
                    wf["workflow_type"] = t
                    break
        if action == "STEP_COMPLETE":
            step = entry.get("step_name", "")
            if step and step not in wf["steps"]:
                wf["steps"].append(step)
        if action == "WORKFLOW_COMPLETED":
            wf["status"]       = "completed"
            wf["completed_at"] = entry.get("timestamp", "")
            out = entry.get("output_summary", "")
            if "tasks=" in out:
                try:
                    wf["tasks_count"] = int(out.split("tasks=")[1].split()[0])
                except Exception:
                    pass
        if action == "SLA_BREACHED":
            wf["sla_breached"] = True
        conf = entry.get("confidence", 1.0)
        if conf:
            wf["confidence_avg"].append(float(conf))
        wf["total_retries"] += entry.get("retry_count", 0)

    result = []
    for wf in workflows.values():
        confs = wf.pop("confidence_avg", [])
        wf["avg_confidence"] = round(sum(confs) / len(confs) * 100, 1) if confs else 100.0
        wf["steps_count"]    = len(wf["steps"])
        result.append(wf)
    result.sort(key=lambda x: x.get("started_at", ""), reverse=True)
    return result


def load_all_tasks():
    """
    Load tasks with STRICT deduplication.

    Priority order (highest to lowest):
      1. RAM tracker store  — most complete, has deadlines
      2. RAM workflow state — also complete
      3. SQLite DB          — persistent
      4. Audit log          — last resort, no deadlines

    Key rule: once a task_id is seen, NEVER add it again from lower sources.
    Also deduplicate by (title + owner) to prevent same task from audit + RAM.
    """
    seen_ids    = set()   # by task_id
    seen_titles = set()   # by "title|owner" — prevents audit duplicates
    all_tasks   = []

    # ── Source 1: RAM tracker store (best — has full data + deadlines) ────────
    try:
        from memory.short_term_memory import ShortTermMemory, _store
        for key, value in _store.items():
            if key.startswith("tracker:") and key.endswith(":tasks"):
                wid = key.split(":")[1]
                if not isinstance(value, list):
                    continue
                for task in value:
                    t   = dict(task)
                    t["workflow_id"] = wid
                    t["source"]      = "ram"
                    tid  = t.get("id", "")
                    tkey = f"{t.get('title','')}|{t.get('owner','')}"
                    if tid and tid not in seen_ids:
                        seen_ids.add(tid)
                        seen_titles.add(tkey)
                        all_tasks.append(t)
    except Exception:
        pass

    # ── Source 2: RAM workflow state ──────────────────────────────────────────
    try:
        from memory.short_term_memory import ShortTermMemory
        for wid in ShortTermMemory.all_workflow_ids():
            state = ShortTermMemory.get_state(wid) or {}
            for task in state.get("tasks", []):
                t    = dict(task)
                t["workflow_id"] = wid
                t["source"]      = "ram"
                tid  = t.get("id", "")
                tkey = f"{t.get('title','')}|{t.get('owner','')}"
                if tid and tid not in seen_ids and tkey not in seen_titles:
                    seen_ids.add(tid)
                    seen_titles.add(tkey)
                    all_tasks.append(t)
    except Exception:
        pass

    # ── Source 3: SQLite DB ───────────────────────────────────────────────────
    try:
        import sqlite3
        db_path = os.path.join(os.path.dirname(__file__), "..", "agentic_ai.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur  = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_records'")
            if cur.fetchone():
                cur.execute("""
                    SELECT task_id, workflow_id, title, description,
                           owner, owner_email, priority, status,
                           deadline, escalation_count, created_at, updated_at
                    FROM task_records ORDER BY created_at DESC
                """)
                for row in cur.fetchall():
                    tid  = row["task_id"]
                    tkey = f"{row['title']}|{row['owner']}"
                    if tid and tid not in seen_ids and tkey not in seen_titles:
                        seen_ids.add(tid)
                        seen_titles.add(tkey)
                        all_tasks.append({
                            "id":               tid,
                            "workflow_id":      row["workflow_id"] or "",
                            "title":            row["title"] or "",
                            "description":      row["description"] or "",
                            "owner":            row["owner"] or "Unassigned",
                            "owner_email":      row["owner_email"] or "",
                            "priority":         row["priority"] or "medium",
                            "status":           row["status"] or "pending",
                            "deadline":         row["deadline"] or "",
                            "escalation_count": row["escalation_count"] or 0,
                            "source":           "database",
                        })
            conn.close()
    except Exception:
        pass

    # ── Source 4: Audit log (LAST RESORT — no deadline info) ──────────────────
    # Only use if RAM and DB are completely empty
    if not all_tasks:
        try:
            audit_entries = load_audit_log()
            # Get the LATEST workflow's tasks only — avoid old duplicates
            latest_wf_id  = None
            for entry in reversed(audit_entries):
                if entry.get("action") == "TASKS_REGISTERED":
                    latest_wf_id = entry.get("workflow_id")
                    break

            for entry in audit_entries:
                if entry.get("action") != "TASK_OWNER_NOTIFIED":
                    continue
                # Only load tasks from the latest workflow
                if latest_wf_id and entry.get("workflow_id") != latest_wf_id:
                    continue
                summary    = entry.get("input_summary", "")
                wf_id      = entry.get("workflow_id", "")
                task_part  = ""
                owner_part = "Unknown"
                if "task=" in summary and "owner=" in summary:
                    parts      = summary.split(" owner=")
                    task_part  = parts[0].replace("task=", "").strip()
                    owner_part = parts[1].strip() if len(parts) > 1 else "Unknown"
                if task_part:
                    tkey = f"{task_part}|{owner_part}"
                    if tkey not in seen_titles:
                        fake_id = f"audit_{entry.get('id', len(all_tasks))}"
                        seen_ids.add(fake_id)
                        seen_titles.add(tkey)
                        all_tasks.append({
                            "id":          fake_id,
                            "workflow_id": wf_id,
                            "title":       task_part,
                            "owner":       owner_part,
                            "owner_email": "",
                            "priority":    "medium",
                            "status":      "pending",
                            "deadline":    "",   # audit log has no deadline
                            "source":      "audit_log",
                        })
        except Exception:
            pass

    return merge_overrides(all_tasks)


def get_stats(tasks):
    total       = len(tasks)
    done        = sum(1 for t in tasks if t.get("status") == "done")
    in_progress = sum(1 for t in tasks if t.get("status") == "in_progress")
    stalled     = sum(1 for t in tasks if t.get("status") == "stalled")
    needs_help  = sum(1 for t in tasks if t.get("status") == "needs_help")
    pending     = max(total - done - in_progress - stalled - needs_help, 0)
    pct         = round((done / total * 100) if total else 0, 1)
    return dict(total=total, done=done, in_progress=in_progress,
                pending=pending, stalled=stalled, needs_help=needs_help,
                completion_pct=pct)


def check_api(api_url):
    try:
        import requests
        r = requests.get(f"{api_url}/health", timeout=2)
        return r.ok
    except Exception:
        return False


# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.markdown("## Agentic AI System")
    st.markdown("*Autonomous Enterprise Workflows*")
    st.divider()
    page = st.radio(
        "Navigate",
        ["Live Dashboard", "All Workflows", "Workflow Tasks",
         "Manager View", "Audit Trail", "Health Monitor", "Trigger Workflow"],
    )
    st.divider()
    st.markdown("**API Base URL**")
    api_url      = st.text_input("", value="http://localhost:8000/api/v1", label_visibility="collapsed")
    api_ok = check_api(api_url)
    if api_ok:
        st.markdown('<span class="badge-green">API Online</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-red">API Offline — run ./run.sh api</span>', unsafe_allow_html=True)
    st.divider()
    auto_refresh = st.toggle("Auto-refresh (5s)", value=False)
    if auto_refresh:
        time.sleep(5)
        st.rerun()


# =============================================================================
# PAGE: Live Dashboard
# =============================================================================

if page == "Live Dashboard":
    st.title("Live Workflow Dashboard")
    audit_entries = load_audit_log()
    all_wfs       = load_all_workflows_from_audit()
    all_tasks     = load_all_tasks()
    active_wfs    = load_active_workflows()

    c1, c2, c3, c4, c5 = st.columns(5)
    completed  = sum(1 for w in all_wfs if w["status"] == "completed")
    done_tasks = sum(1 for t in all_tasks if t.get("status") == "done")
    avg_conf   = (sum(e.get("confidence", 0) for e in audit_entries) / len(audit_entries)) if audit_entries else 0

    c1.metric("Total workflows",  len(all_wfs))
    c2.metric("Completed",        completed)
    c3.metric("Active now",       len(active_wfs))
    c4.metric("Tasks done",       f"{done_tasks}/{len(all_tasks)}")
    c5.metric("Avg confidence",    f"{avg_conf:.0%}")

    if all_tasks:
        st.divider()
        s = get_stats(all_tasks)
        st.subheader("Overall task completion")
        st.progress(s["completion_pct"] / 100,
                    text=f"{s['done']} of {s['total']} tasks done ({s['completion_pct']}%)")
        ca, cb, cc, cd = st.columns(4)
        ca.metric("Pending",     s["pending"])
        cb.metric("In progress", s["in_progress"])
        cc.metric("Done",        s["done"])
        cd.metric("Stalled",     s["stalled"])

    st.divider()
    st.subheader("Recent workflow runs")
    type_emoji = {"meeting": "🎙️", "onboarding": "👤", "procurement": "🛒", "contract": "📄"}
    if not all_wfs:
        st.info("No workflows yet. Trigger one from the sidebar.")
    else:
        for wf in all_wfs[:8]:
            emoji   = type_emoji.get(wf["workflow_type"], "⚙️")
            started = wf.get("started_at", "")[:16].replace("T", " ")
            c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 1])
            c1.markdown(f"{emoji} **{wf['workflow_type'].upper()}** `{wf['workflow_id'][:14]}...`")
            c2.markdown(
                '<span class="badge-green">done</span>' if wf["status"] == "completed"
                else '<span class="badge-amber">running</span>',
                unsafe_allow_html=True,
            )
            c3.markdown(f"Steps: `{wf['steps_count']}`")
            c4.markdown(f"Conf: `{wf['avg_confidence']}%`")
            c5.markdown(f"`{started}`")

    if active_wfs:
        st.divider()
        st.subheader("Currently running")
        for wf in active_wfs:
            with st.expander(f"{wf.get('workflow_type','').upper()} — {wf.get('workflow_id','')[:14]}...", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Status:** `{wf.get('status','—')}`")
                c2.markdown(f"**Step:** `{wf.get('current_step','—')}`")
                c3.markdown(f"**Retries:** {wf.get('retry_count', 0)}")
                completed_steps = wf.get("completed_steps", [])
                if completed_steps:
                    st.progress(min(len(completed_steps) / max(len(completed_steps) + 2, 1), 1.0),
                                text=f"Steps: {len(completed_steps)}")

    st.divider()
    st.subheader("Recent agent actions")
    recent = audit_entries[-20:][::-1]
    if recent:
        import pandas as pd
        df = pd.DataFrame(recent)
        wanted   = ["timestamp", "agent_id", "action", "step_name", "confidence", "workflow_id"]
        existing = [c for c in wanted if c in df.columns]
        df = df[existing].copy()
        if "confidence"  in df.columns: df["confidence"]  = df["confidence"].apply(lambda x: f"{float(x):.0%}")
        if "workflow_id" in df.columns: df["workflow_id"] = df["workflow_id"].apply(lambda x: str(x)[:12] + "...")
        st.dataframe(df, use_container_width=True, height=350)
    else:
        st.info("No audit entries yet.")


# =============================================================================
# PAGE: All Workflows
# =============================================================================

elif page == "All Workflows":
    st.title("All Workflow Runs")
    st.markdown("*Complete history — meeting, onboarding, procurement, contract*")

    all_wfs = load_all_workflows_from_audit()
    if not all_wfs:
        st.info("No workflows run yet.")
    else:
        types    = ["All", "meeting", "onboarding", "procurement", "contract"]
        sel_type = st.selectbox("Filter by type", types)
        filtered = all_wfs if sel_type == "All" else [w for w in all_wfs if w["workflow_type"] == sel_type]
        st.markdown(f"Showing **{len(filtered)}** workflow runs")
        st.divider()
        type_emoji = {"meeting": "🎙️", "onboarding": "👤", "procurement": "🛒", "contract": "📄"}

        for wf in filtered:
            emoji    = type_emoji.get(wf["workflow_type"], "⚙️")
            wid      = wf["workflow_id"]
            started  = wf.get("started_at",  "")[:19].replace("T", " ")
            finished = wf.get("completed_at","")[:19].replace("T", " ")

            with st.expander(
                f"{emoji} {wf['workflow_type'].upper()} — {wid[:16]}... — "
                f"{'Completed' if wf['status'] == 'completed' else 'Running'}",
                expanded=False,
            ):
                c1, c2, c3, c4 = st.columns(4)
                c1.markdown(f"**Type:** {wf['workflow_type'].capitalize()}")
                c2.markdown(
                    f'**Status:** <span class="badge-green">completed</span>'
                    if wf["status"] == "completed"
                    else f'**Status:** <span class="badge-amber">running</span>',
                    unsafe_allow_html=True,
                )
                c3.markdown(f"**Confidence:** {wf['avg_confidence']}%")
                c4.markdown(f"**Retries:** {wf['total_retries']}")

                c5, c6 = st.columns(2)
                c5.markdown(f"**Started:** `{started}`")
                if finished:
                    c6.markdown(f"**Finished:** `{finished}`")

                if wf.get("tasks_count", 0) > 0:
                    st.markdown(f"**Tasks created:** {wf['tasks_count']}")
                if wf.get("steps"):
                    st.markdown(f"**Steps:** " + " → ".join(wf["steps"]))

                st.caption(f"Workflow ID: `{wid}`")

                if st.button("View audit trail", key=f"aud_{wid}"):
                    entries = [e for e in load_audit_log() if e.get("workflow_id") == wid]
                    if entries:
                        import pandas as pd
                        df = pd.DataFrame(entries)
                        cols = ["timestamp", "agent_id", "action", "step_name", "output_summary", "confidence"]
                        existing = [c for c in cols if c in df.columns]
                        st.dataframe(df[existing], use_container_width=True)


# =============================================================================
# PAGE: Workflow Tasks — with deadlines shown properly
# =============================================================================

elif page == "Workflow Tasks":
    st.title("Meeting Intelligence — Task Board")
    st.markdown("*Find your task and update its status*")

    all_tasks = load_all_tasks()

    if not all_tasks:
        st.warning("No tasks found. Upload a meeting transcript to generate tasks.")
        st.markdown("Go to **Trigger Workflow → Meeting transcript**")
    else:
        s = get_stats(all_tasks)

        # Show warning if tasks have no deadlines (came from audit log)
        no_deadline = sum(1 for t in all_tasks if not t.get("deadline"))
        if no_deadline > 0:
            st.warning(
                f"{no_deadline} task(s) have no deadline — these came from the audit log fallback "
                f"(server was restarted). Upload the transcript again to restore full task details."
            )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pending",     s["pending"])
        c2.metric("In progress", s["in_progress"])
        c3.metric("Done",        s["done"])
        c4.metric("Stalled",     s["stalled"])
        st.progress(s["completion_pct"] / 100,
                    text=f"Completion: {s['completion_pct']}%  ({s['done']}/{s['total']} done)")
        st.divider()

        owners    = ["All"] + sorted(set(t.get("owner", "Unassigned") for t in all_tasks))
        sel_owner = st.selectbox("Filter by employee", owners)
        ftasks    = all_tasks if sel_owner == "All" else [
            t for t in all_tasks if t.get("owner") == sel_owner
        ]
        st.divider()

        for status_key, label, emoji in [
            ("pending",     "Pending",     "🟡"),
            ("in_progress", "In progress", "🔵"),
            ("needs_help",  "Needs help",  "⚠️"),
            ("done",        "Done",        "🟢"),
            ("stalled",     "Stalled",     "🔴"),
        ]:
            bucket = [t for t in ftasks if t.get("status") == status_key]
            if not bucket:
                continue
            st.subheader(f"{emoji} {label} ({len(bucket)})")

            for idx, task in enumerate(bucket):
                tid         = task.get("id",          f"{status_key}_{idx}")
                title       = task.get("title",        "Untitled")
                owner       = task.get("owner",        "Unassigned")
                owner_email = task.get("owner_email",  "")
                owner_slack = task.get("owner_slack",  "")
                priority    = task.get("priority",     "medium")
                deadline    = task.get("deadline",     "")
                deadline_fmt = fmt_deadline(deadline)
                overdue     = is_overdue(deadline) and status_key not in ("done", "cancelled")
                wf_id       = task.get("workflow_id",  "")
                esc         = task.get("escalation_count", 0)
                updated_by  = task.get("updated_by",  "")
                source      = task.get("source",      "")

                with st.expander(
                    f"{title}  —  {owner}" + (" 🔴 OVERDUE" if overdue else ""),
                    expanded=(status_key == "pending"),
                ):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"**Owner:** {owner}")

                    # Deadline with overdue highlight
                    if overdue:
                        c2.markdown(
                            f'**Deadline:** <span class="badge-red">{deadline_fmt} — OVERDUE</span>',
                            unsafe_allow_html=True,
                        )
                    elif deadline_fmt == "—":
                        c2.markdown(f"**Deadline:** `Not set`")
                    else:
                        c2.markdown(f"**Deadline:** `{deadline_fmt}`")

                    c3.markdown(f"**Priority:** `{priority}`")

                    if owner_email:
                        c4, c5 = st.columns(2)
                        c4.markdown(f"**Email:** {owner_email}")
                        if owner_slack:
                            c5.markdown(f"**Slack:** {owner_slack}")

                    if esc > 0:
                        st.markdown(f'<span class="badge-red">Escalated {esc}×</span>', unsafe_allow_html=True)
                    if updated_by:
                        st.caption(f"Last updated by: {updated_by}")

                    st.divider()
                    b1, b2, b3 = st.columns(3)

                    if status_key != "done":
                        if b1.button("Mark Done", key=f"done_{tid}_{idx}", type="primary", use_container_width=True):
                            apply_override(tid, "done", "employee")
                            st.success("Marked as Done!")
                            st.rerun()

                    if status_key == "pending":
                        if b2.button("In Progress", key=f"prog_{tid}_{idx}", use_container_width=True):
                            apply_override(tid, "in_progress", "employee")
                            st.info("Marked In Progress")
                            st.rerun()

                    if status_key in ("pending", "in_progress"):
                        if b3.button("Need Help", key=f"help_{tid}_{idx}", use_container_width=True):
                            apply_override(tid, "needs_help", "employee")
                            st.warning("Manager notified")
                            st.rerun()

                    st.caption(f"ID: `{tid}` | Workflow: `{wf_id[:14]}...` | Source: `{source}`")


# =============================================================================
# PAGE: Manager View
# =============================================================================

elif page == "Manager View":
    st.title("Manager Overview")

    all_tasks = load_all_tasks()
    all_wfs   = load_all_workflows_from_audit()

    # Workflow type summary
    st.subheader("Workflow summary")
    type_emoji = {"meeting": "🎙️", "onboarding": "👤", "procurement": "🛒", "contract": "📄"}
    cols = st.columns(4)
    for i, wtype in enumerate(["meeting", "onboarding", "procurement", "contract"]):
        count = sum(1 for w in all_wfs if w["workflow_type"] == wtype)
        cols[i].metric(f"{type_emoji[wtype]} {wtype.capitalize()}", count)
    st.divider()

    if not all_tasks:
        st.info("No tasks yet. Upload a meeting transcript to generate tasks.")
    else:
        s = get_stats(all_tasks)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total tasks",   s["total"])
        c2.metric("Done",          s["done"])
        c3.metric("In progress",   s["in_progress"])
        c4.metric("Pending",       s["pending"])
        c5.metric("Stalled",       s["stalled"])
        st.progress(s["completion_pct"] / 100, text=f"Team completion: {s['completion_pct']}%")
        st.divider()

        # Per-employee breakdown
        st.subheader("Per-employee breakdown")
        import pandas as pd
        employees = sorted(set(t.get("owner", "Unassigned") for t in all_tasks))
        rows = []
        for emp in employees:
            emp_tasks = [t for t in all_tasks if t.get("owner") == emp]
            emp_done  = sum(1 for t in emp_tasks if t.get("status") == "done")
            emp_pend  = sum(1 for t in emp_tasks if t.get("status") == "pending")
            emp_stall = sum(1 for t in emp_tasks if t.get("status") == "stalled")
            emp_pct   = round((emp_done / len(emp_tasks) * 100) if emp_tasks else 0, 1)
            rows.append({
                "Employee":    emp,
                "Total tasks": len(emp_tasks),
                "Done":        emp_done,
                "Pending":     emp_pend,
                "Stalled":     emp_stall,
                "Completion":  f"{emp_pct}%",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.divider()

        # Action required
        action_tasks = [t for t in all_tasks if t.get("status") in ("stalled", "needs_help")]
        if action_tasks:
            st.subheader(f"Action required — {len(action_tasks)} task(s)")
            for task in action_tasks:
                tid      = task.get("id", "?")
                title    = task.get("title", "Untitled")
                owner    = task.get("owner", "?")
                deadline = fmt_deadline(task.get("deadline", ""))
                wf_id    = task.get("workflow_id", "")
                status   = task.get("status", "")
                with st.expander(f"{title}  —  {owner}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.markdown(f"**Owner:** {owner}")
                    c2.markdown(f"**Deadline:** `{deadline}`")
                    c3.markdown(
                        f'**Status:** <span class="badge-red">{status}</span>',
                        unsafe_allow_html=True,
                    )
                    if st.button("Mark Done (manager)", key=f"mgr_{tid}", type="primary", use_container_width=True):
                        apply_override(tid, "done", "manager")
                        st.success("Done by manager")
                        st.rerun()
        else:
            st.success("No stalled tasks — all tasks are being handled!")

        st.divider()

        # Full task table with proper deadline formatting
        st.subheader("All tasks")
        rows = []
        for t in all_tasks:
            dl      = t.get("deadline", "")
            dl_fmt  = fmt_deadline(dl)
            overdue = is_overdue(dl) and t.get("status") not in ("done", "cancelled")
            rows.append({
                "Title":    t.get("title", "")[:55],
                "Owner":    t.get("owner", "—"),
                "Deadline": f"⚠️ {dl_fmt}" if overdue else dl_fmt,
                "Status":   t.get("status", "—"),
                "Priority": t.get("priority", "—"),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.download_button("Download task report (JSON)",
                               data=json.dumps(all_tasks, indent=2, default=str),
                               file_name="task_report.json", mime="application/json")


# =============================================================================
# PAGE: Audit Trail
# =============================================================================

elif page == "Audit Trail":
    st.title("Full Audit Trail")
    audit_entries = load_audit_log()
    st.markdown(f"**Total entries:** {len(audit_entries)}  |  Append-only.")
    st.divider()

    c1, c2, c3 = st.columns(3)
    wf_ids       = ["All"] + list(set(e.get("workflow_id", "") for e in audit_entries))
    agent_ids    = ["All"] + sorted(set(e.get("agent_id",   "") for e in audit_entries))
    action_types = ["All"] + sorted(set(e.get("action",     "") for e in audit_entries))
    sel_wf  = c1.selectbox("Workflow ID",  wf_ids)
    sel_ag  = c2.selectbox("Agent",        agent_ids)
    sel_act = c3.selectbox("Action type",  action_types)

    filtered = audit_entries
    if sel_wf  != "All": filtered = [e for e in filtered if e.get("workflow_id") == sel_wf]
    if sel_ag  != "All": filtered = [e for e in filtered if e.get("agent_id")    == sel_ag]
    if sel_act != "All": filtered = [e for e in filtered if e.get("action")      == sel_act]

    st.markdown(f"*Showing {len(filtered)} of {len(audit_entries)} entries*")
    if filtered:
        import pandas as pd
        df = pd.DataFrame(filtered[::-1])
        cols = ["timestamp", "workflow_id", "agent_id", "action",
                "step_name", "input_summary", "output_summary", "confidence"]
        existing = [c for c in cols if c in df.columns]
        st.dataframe(df[existing], use_container_width=True, height=500)
        st.download_button("Download (JSON)", data=json.dumps(filtered, indent=2, default=str),
                           file_name="audit.json", mime="application/json")
    else:
        st.info("No entries match the filters.")


# =============================================================================
# PAGE: Health Monitor
# =============================================================================

elif page == "Health Monitor":
    st.title("Workflow Health Monitor")
    audit_entries = load_audit_log()
    all_wfs       = load_all_workflows_from_audit()
    active_wfs    = load_active_workflows()

    if not check_api(api_url):
        st.error("API server is offline! Start it: `./run.sh api`")

    st.subheader("Active workflow SLA status")
    if not active_wfs:
        st.info("No active workflows right now — all completed.")
    else:
        for wf in active_wfs:
            wid     = wf.get("workflow_id", "")
            wtype   = wf.get("workflow_type", "?")
            sla_rem = wf.get("sla_remaining_minutes")
            step    = wf.get("current_step", "—")
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**{wtype.upper()}** `{wid[:12]}...`")
            c2.markdown(f"Status: `{wf.get('status','—')}`")
            c3.markdown(f"Step: `{step}`")
            if sla_rem is not None:
                if sla_rem < 10:
                    c4.markdown(f'<span class="badge-red">⚠ {sla_rem:.0f} min left</span>', unsafe_allow_html=True)
                elif sla_rem < 30:
                    c4.markdown(f'<span class="badge-amber">⏱ {sla_rem:.0f} min left</span>', unsafe_allow_html=True)
                else:
                    c4.markdown(f'<span class="badge-green">✓ {sla_rem:.0f} min left</span>', unsafe_allow_html=True)

    st.divider()
    st.subheader("Overall system statistics")
    total_wfs = len(all_wfs)
    completed = sum(1 for w in all_wfs if w["status"] == "completed")
    breached  = sum(1 for w in all_wfs if w.get("sla_breached"))
    avg_conf  = (sum(e.get("confidence", 0) for e in audit_entries) / len(audit_entries) * 100) if audit_entries else 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total workflows", total_wfs)
    c2.metric("Completed",       completed)
    c3.metric("SLA breaches",    breached)
    c4.metric("Avg confidence",  f"{avg_conf:.1f}%")

    st.divider()
    st.subheader("SLA & drift events")
    HEALTH_KW = {"DRIFT", "BREACH", "ANOMALY", "REROUTE", "RETRY", "TIMEOUT", "ESCALAT"}
    health_events = [
        e for e in audit_entries
        if any(kw in e.get("action", "").upper() for kw in HEALTH_KW)
    ]
    if not health_events:
        st.success("No SLA or drift events. All workflows ran within baseline.")
    else:
        import pandas as pd
        h1, h2, h3 = st.columns(3)
        h1.metric("Total events", len(health_events))
        h2.metric("Escalations",  sum(1 for e in health_events if "ESCALAT" in e.get("action", "")))
        h3.metric("Retries",      sum(1 for e in health_events if "RETRY"   in e.get("action", "")))
        df = pd.DataFrame(health_events[::-1])
        cols = ["timestamp", "workflow_id", "agent_id", "action", "output_summary"]
        existing = [c for c in cols if c in df.columns]
        st.dataframe(df[existing], use_container_width=True)

    st.divider()
    st.subheader("Workflow type breakdown")
    if all_wfs:
        import pandas as pd
        type_rows = []
        for wtype in ["meeting", "onboarding", "procurement", "contract"]:
            wfs = [w for w in all_wfs if w["workflow_type"] == wtype]
            if not wfs:
                continue
            avg_c = round(sum(w.get("avg_confidence", 100) for w in wfs) / len(wfs), 1)
            type_rows.append({
                "Workflow type":  wtype.capitalize(),
                "Total runs":    len(wfs),
                "Completed":     sum(1 for w in wfs if w["status"] == "completed"),
                "SLA breaches":  sum(1 for w in wfs if w.get("sla_breached")),
                "Avg confidence":f"{avg_c}%",
            })
        if type_rows:
            st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No historical data yet.")


# =============================================================================
# PAGE: Trigger Workflow
# =============================================================================

elif page == "Trigger Workflow":
    st.title("Trigger a Workflow")

    if not check_api(api_url):
        st.error("API server is offline! Open Git Bash Terminal 1 and run: `./run.sh api`")
        st.stop()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Meeting transcript", "Employee onboarding", "Procurement", "Contract"]
    )

    with tab1:
        st.subheader("Upload meeting transcript")
        uploaded_file = st.file_uploader("Choose a .txt transcript file", type=["txt"])
        if uploaded_file:
            content = uploaded_file.read().decode("utf-8", errors="ignore")
            st.text_area("Preview", value=content[:500] + "..." if len(content) > 500 else content, height=150)
            if st.button("Process transcript"):
                try:
                    import requests
                    resp = requests.post(
                        f"{api_url}/meeting/upload",
                        files={"file": (uploaded_file.name, content.encode(), "text/plain")},
                    )
                    if resp.ok:
                        wf_id = resp.json().get("workflow_id")
                        st.success(f"Workflow started! ID: `{wf_id}`")
                        st.info("Go to **Workflow Tasks** to see tasks with deadlines.")
                    else:
                        st.error(f"API error: {resp.status_code}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")

    with tab2:
        st.subheader("New employee onboarding")
        with st.form("onboarding_form"):
            emp_name    = st.text_input("Employee name",  value="Jane Doe")
            emp_dept    = st.selectbox("Department", ["Engineering", "Marketing", "HR", "Finance", "Legal", "QA", "Product"])
            emp_role    = st.text_input("Role",           value="Software Engineer")
            emp_manager = st.text_input("Manager email",  value="manager@company.com")
            if st.form_submit_button("Start onboarding workflow"):
                try:
                    import requests
                    resp = requests.post(f"{api_url}/workflow/trigger", json={
                        "workflow_type": "onboarding",
                        "payload": {"name": emp_name, "department": emp_dept,
                                    "role": emp_role, "manager": emp_manager},
                    })
                    if resp.ok:
                        st.success(f"Onboarding started! ID: `{resp.json().get('workflow_id')}`")
                        st.info("Go to **All Workflows** to see the result.")
                    else:
                        st.error(f"API error: {resp.status_code}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")

    with tab3:
        st.subheader("Procurement to payment")
        with st.form("procurement_form"):
            vendor = st.text_input("Vendor name", value="ACME Corp")
            amount = st.number_input("PO amount (Rs.)", min_value=0, value=150000, step=10000)
            if st.form_submit_button("Start procurement workflow"):
                try:
                    import requests
                    resp = requests.post(f"{api_url}/workflow/trigger", json={
                        "workflow_type": "procurement",
                        "payload": {"vendor_name": vendor, "amount": amount},
                    })
                    if resp.ok:
                        st.success(f"Procurement started! ID: `{resp.json().get('workflow_id')}`")
                        st.info("Go to **All Workflows** to see the result.")
                    else:
                        st.error(f"API error: {resp.status_code}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")

    with tab4:
        st.subheader("Contract lifecycle")
        with st.form("contract_form"):
            contract_id = st.text_input("Contract ID",           value="C-2026-001")
            value       = st.number_input("Contract value (Rs.)", min_value=0, value=800000, step=50000)
            if st.form_submit_button("Start contract workflow"):
                try:
                    import requests
                    resp = requests.post(f"{api_url}/workflow/trigger", json={
                        "workflow_type": "contract",
                        "payload": {"contract_id": contract_id, "value": value},
                    })
                    if resp.ok:
                        st.success(f"Contract workflow started! ID: `{resp.json().get('workflow_id')}`")
                        st.info("Go to **All Workflows** to see the result.")
                    else:
                        st.error(f"API error: {resp.status_code}")
                except Exception as e:
                    st.error(f"Could not reach API: {e}")