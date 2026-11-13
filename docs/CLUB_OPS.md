# Club Ops Coordinator (PS 2)

HIVE in `coordinator` profile acts as a student-club chief of staff. It reads
Gmail and Google Calendar, keeps tasks, prepares meetings, drafts outbound
email, and proposes next actions — while every outbound action stays behind a
human approval gate.

See [GOOGLE_INTEGRATION_SETUP.md](GOOGLE_INTEGRATION_SETUP.md) for OAuth setup.

---

## Quick start

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# set DASHSCOPE_API_KEY, then:
python -m hive.cli --connect-google
python -m hive.cli --check-integrations

# 3. Run the coordinator
HIVE_AGENT_PROFILE=coordinator python -m hive

# 4. Or run the desktop app
cd desktop && npm install && npm run build && npm start
```

---

## What it can do

| Capability | Tools | Approval |
|---|---|---|
| Read unread mail and classify urgency | `gmail_search`, `gmail_read_thread` | safe, auto |
| Draft a reply (never sends) | `gmail_create_draft` | moderate |
| Send an approved draft / message | `gmail_send_draft`, `gmail_send_message` | **sensitive — always human** |
| Read agenda, find free slots, detect conflicts | `calendar_list_events`, `calendar_find_free_slots`, `calendar_detect_conflicts` | safe, auto |
| Create / update / delete events | `calendar_create_event`, `calendar_update_event`, `calendar_delete_event` | **sensitive/dangerous — always human** |
| Local tasks (+ optional Google Tasks sync) | `task_list`, `task_add`, `task_update`, `task_complete`, `task_delete`, `tasks_sync` | moderate |
| Run club-ops workflows and missions | `workflow_*`, `mission_list`, `mission_run` | safe/moderate, outbound returned as proposals |

Outbound rule: `should_auto_allow()` returns `False` for sensitive and
dangerous tiers. A trust level can never bypass an email send, calendar write,
signup, or checkout. Workflows do not execute outbound tools — they return
`next_actions` (`{tool, args, reason, requires_approval}`) for the leader and the
approval queue.

---

## CLI slash commands

```
/inbox                       Unread mail, prioritised
/calendar [days]             Agenda
/tasks                       Pending tasks
/brief                       Morning/daily brief
/missions                    List missions
/mission <name> [k=v ...]    Run a mission
/draft <thread_id> [to]      Create a reply draft (draft only)
/integrations                Connector status
/playbooks                   Recorded flows and trust scores
/trust <domain> [0-3]        Set or show domain trust
/persona [list|use|create]   Digital-twin personas
```

Desktop request actions (`/server` mode): `overview`, `inbox`, `agenda`,
`tasks`, `missions`, `mission_run`, `integrations`, `task_add`,
`task_complete`, `draft_reply`, `brief`, `triage`.

---

## Built-in missions

| Mission | Workflow | What it returns |
|---|---|---|
| `morning_brief` | `daily_brief` | Agenda, unread pressure, tasks due soon, nudge actions |
| `inbox_triage` | `triage_inbox` | Priority classification, draft/task next actions |
| `meeting_prep` | `prepare_meeting` | Briefing packet for the next or matching meeting |
| `post_meeting_followup` | `post_meeting_followup` | Follow-up tasks and draft thank-you notes |
| `sponsor_followups` | `sponsor_reminders` | Sponsors with outstanding deliverables + draft outreach |
| `volunteer_scheduling` | `volunteer_schedule` | Assignment plan + draft outreach |
| `venue_confirmation` | `venue_confirmation` | Venue confirmation draft |
| `weekly_review` | `daily_brief` (7 days) | Weekly rollup |

Custom missions live in `~/.hive/missions/*.json`:

```json
{
  "name": "recap_packet",
  "title": "Recap packet",
  "description": "Summarise the week for the core team.",
  "workflow": "daily_brief",
  "params": {"days": 7},
  "param_types": {"days": "int"},
  "required": []
}
```

Run one from the CLI: `/mission recap_packet days=14`.

---

## Workflows and approvals

`hive/workflows/club_ops.py` exposes seven workflows:

`triage_inbox`, `prepare_meeting`, `post_meeting_followup`,
`sponsor_reminders`, `volunteer_schedule`, `venue_confirmation`, `daily_brief`.

Each returns a `summary` string, structured data, `errors`, and `next_actions`.
The leader can execute safe actions directly; every outbound action is routed
through the same permission gate as a chat request:

1. Workflow proposes `next_actions`.
2. Leader calls the tool (e.g. `gmail_create_draft`).
3. Runtime emits `permission_request` with a rich target preview.
4. Desktop or CLI presents the approval card.
5. Only `approved` continues; denial is safe and recorded.

---

## Desktop screens

The Electron app adds four club-ops screens:

- **Inbox** — unread mail with priority, categories, snippet, and a one-click
  “Draft reply” (creates a Gmail draft only).
- **Calendar** — 1/7/14-day agenda, join/open links, and “Prep me” which sends a
  meeting-prep request to the leader.
- **Tasks** — pending/completed list, add form, complete action.
- **Missions** — one-click workflows with parameter inputs, summary output, and
  next-action cards that can be sent back to the leader for approval.

The dashboard shows unread count, pending tasks, events ahead, next meeting,
connector health, and the approval queue depth. The runtime pushes `state` at
startup, `tasks_updated` after task mutations, and `inbox_updated` after drafts.

---

## VISION extras

**Playbooks** (`hive/playbooks.py`, `hive/browser/recorder.py`,
`hive/browser/replay.py`)

- Record `goto`, `click`, `type`, `press`, `wait` steps with robust selectors.
- Replay with `${placeholder}` substitution for sensitive values.
- Schema v2 stores multiple named flows per site plus a trust score.

**Trust ladder** (`hive/trust.py`)

| Level | Meaning |
|---|---|
| 0 | Ask for everything on this domain |
| 1 | Still ask; HIVE has learned the flow |
| 2 | Autonomous navigation and read-only steps |
| 3 | Autonomous safe/moderate steps |

Outbound and dangerous tools are in `NEVER_AUTONOMOUS`. Unknown domains keep the
existing behavior unless `HIVE_TRUST_STRICT=true`.

**Personas** (`hive/personas.py`)

`/persona create work` creates an isolated vault and browser profile. Switching
personas changes vault path, Chrome profile, and optional spend caps. The default
persona keeps existing paths unchanged. Restart the runtime after switching.

**CAPTCHA handoff** (`hive/browser/captcha.py`)

Default provider is `human`: HIVE pauses, the browser window stays open, and the
user solves the challenge. Optional `2captcha` provider submits reCAPTCHA v2
tokens and falls back to human on failure.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `HIVE_AGENT_PROFILE` | `full` | Set to `coordinator` for club ops |
| `HIVE_TIMEZONE` | `Asia/Kolkata` | Calendar and brief timezone |
| `GOOGLE_CALENDAR_ID` | `primary` | Calendar to read/write |
| `HIVE_GOOGLE_TASKS_SYNC` | `false` | Mirror local tasks to Google Tasks |
| `GOOGLE_TASKS_LIST_ID` | `@default` | Google Tasks list |
| `HIVE_TASKS_FILE` | `~/.hive/tasks.json` | Local task store |
| `HIVE_TRUST_DEFAULT_LEVEL` | `0` | Fallback trust level |
| `HIVE_TRUST_STRICT` | unset | Unknown domains require approval |
| `HIVE_PERSONA` | unset | Active persona at startup |
| `HIVE_CAPTCHA_PROVIDER` | `human` | `human` or `2captcha` |
| `HIVE_CAPTCHA_API_KEY` | unset | 2captcha API key |
| `SLACK_BOT_TOKEN` | unset | Status-only Slack configuration |

Google credentials stay outside the repository in `~/.hive/`.

---

## Tests

```bash
python -m pytest tests/ -q
```

Coverage added for Gmail writes, Calendar, Tasks, workflows, state API,
playbook schema v2, trust, and personas. Browser replay tests inject a fake
page, so Playwright is not required for the unit suite.

---

## 3-minute demo script

1. Dashboard — “HIVE is connected to Gmail, Calendar, and Tasks.”
2. Inbox — triage unread mail, click **Draft reply**, show the draft is not sent.
3. Missions — run **Morning brief**, show agenda + unread + due tasks.
4. Calendar — **Prep me** on the next event; leader gathers related threads.
5. Approvals — show an outbound email/calendar write blocked for human approval.
6. Playbooks — replay a recorded flow and show the trust level for the domain.
7. Close — “One runtime, a society of agents, one approval gate.”
