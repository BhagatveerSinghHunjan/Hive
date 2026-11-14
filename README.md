# HIVE — The Operating Environment for Autonomous AI Workforces

**A desktop-first AI environment where intelligent agents collaborate, execute real-world tasks, and operate as a coordinated workforce.**

HIVE is an AI-native execution environment designed to move beyond traditional AI assistants. Instead of relying on one model to handle every task, HIVE coordinates specialized agents that plan, delegate, collaborate, challenge decisions, and execute work through connected tools.

From software development and research to browser automation, presentations, file operations, and business workflows, HIVE aims to provide a unified environment for getting work done with AI.

---

## The Vision

Today's AI tools are fragmented.

You use one tool to write code, another to conduct research, another to automate browsers, and another to manage business workflows. Even when AI agents are available, they often operate independently, with limited coordination, visibility, and control.

HIVE brings these capabilities together.

It provides a unified environment in which AI agents can:
- Understand objectives and break them into actionable tasks.
- Form teams of specialized agents dynamically.
- Delegate work and coordinate execution.
- Access tools, files, and external services.
- Evaluate results and challenge assumptions.
- Request human approval for sensitive actions.
- Maintain execution context and report progress.

**The goal is not another AI chatbot. It is an environment where AI can actually get work done.**

---

## Core Architecture

HIVE combines a desktop application with a persistent agent execution runtime.

| Layer | Responsibility |
|---|---|
| Desktop Environment | User interface, mission control, monitoring and approvals |
| Agent Runtime | Agent lifecycle, orchestration and task execution |
| HIVE Leader | Understands objectives and coordinates the workforce |
| Specialist Agents | Perform domain-specific tasks |
| Creator | Creates specialized agents when required |
| Cleanup Crew | Handles agent retirement and execution cleanup |
| Tool Layer | Connects agents to browsers, files, integrations and other capabilities |
| Persistence | Stores execution state, agent information and application data |

The desktop application communicates with the Python runtime through a JSON-lines interface.

### Agent Society

HIVE uses a hierarchical multi-agent architecture.

- **Leader:** Coordinates missions, delegates work and monitors execution.
- **Creator:** Designs and initializes task-specific agents.
- **Specialists:** Execute assigned tasks using their respective capabilities.
- **Cleanup Crew:** Manages agent retirement and cleanup.
- **Debate and Judge:** Challenge proposed decisions and evaluate whether actions should proceed.

Agents can communicate, share findings, challenge assumptions and request assistance rather than operating as isolated AI instances.

---

## Key Capabilities

### 1. Multi-Agent Orchestration
Coordinate multiple specialized agents around a common objective, with delegated responsibilities and centralized execution oversight.

### 2. Dynamic Agent Creation
Create specialized agents based on the requirements of a mission rather than depending entirely on a fixed set of predefined agents.

### 3. Structured Debate and Evaluation
Use multi-round discussions between agents to challenge proposals, identify weaknesses and evaluate important decisions before execution.

### 4. Real-World Task Execution
Connect agent intelligence to practical capabilities, including:
- Browser automation using Playwright.
- File operations and document generation.
- PowerPoint presentation generation.
- Coding and development workflows.
- External integrations and APIs.
- Google Workspace integrations.

### 5. Human-in-the-Loop Control
Keep humans involved in important decisions through approval workflows, execution visibility and controlled external actions.

### 6. Execution Monitoring
Monitor missions, agent activity, task progress and execution status through the desktop interface.

### 7. Agent Economy and Reputation
Use resource allocation, credits, confidence and agent performance tracking to encourage efficient delegation and more accountable execution.

---

## Desktop Experience

HIVE is designed as a desktop application rather than a browser-based SaaS dashboard.

The desktop environment provides a central workspace for interacting with and supervising the agent workforce.

Core interface areas include:

| Interface | Purpose |
|---|---|
| Dashboard | Overview of the HIVE environment |
| Chat | Communicate objectives to HIVE |
| Mission Control | Manage active missions |
| Execution Monitor | Observe agent activity and progress |
| Approvals | Review actions requiring human authorization |
| Inbox | Manage communication and incoming items |
| Calendar | View scheduled activities |
| Tasks | Track assigned and pending work |
| Workflows | Coordinate multi-step operations |

---

## Technology Stack

| Component | Technology |
|---|---|
| Desktop Application | Electron |
| Frontend | React |
| Backend Runtime | Python |
| Agent Communication | JSON Lines IPC |
| Database | SQLite |
| LLM Integration | Qwen / Alibaba Cloud DashScope |
| Browser Automation | Playwright |
| Agent Tool Integration | Model Context Protocol (MCP) |
| External Integrations | Google APIs |
| Desktop UI | React-based interface |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git
- An Alibaba Cloud DashScope API key for the configured Qwen provider

### 1. Clone the Repository

```bash
git clone https://github.com/BhagatveerSinghHunjan/Hive.git
cd Hive
```

### 2. Set Up the Python Runtime

```bash
python -m venv .venv
```

Activate the environment:

**macOS / Linux**
```bash
source .venv/bin/activate
```

**Windows**
```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -e ".[browser]"
```

Install the Playwright browser:

```bash
playwright install chromium
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Add the required API configuration to `.env`:

```env
DASHSCOPE_API_KEY=your_api_key_here
```

Keep API keys private. Never commit `.env` or other secret files.

### 4. Start the Desktop Application

```bash
cd desktop
npm install
npm run build
npm start
```

### 5. Run the Agent Runtime Separately

From the project root, activate the Python environment and run:

```bash
python -m hive
```

For the JSON-lines runtime interface:

```bash
python -m hive.cli --server
```

---

## Project Structure

```text
HIVE/
│
├── desktop/                  # Electron + React desktop application
│
├── hive/                     # Python agent runtime
│   ├── agents/               # Leader, Creator and specialist agents
│   ├── core/                 # Orchestration and agent coordination
│   ├── integrations/         # External service integrations
│   ├── workflows/            # Workflow execution
│   ├── browser/              # Browser automation
│   ├── llm.py                # LLM provider integration
│   ├── missions.py           # Mission definitions
│   └── state_api.py          # Runtime state interface
│
├── hive-frontend/            # Terminal interface
│
├── docs/                     # Architecture and documentation
│
├── scripts/                  # Setup and deployment utilities
│
├── tests/                    # Automated tests
│
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## Current Development Status

HIVE is an actively evolving project.

The existing codebase includes:
- Python-based multi-agent orchestration.
- Leader and specialist agent architecture.
- Dynamic agent creation and cleanup mechanisms.
- Structured agent debate and evaluation.
- Credit and reputation mechanisms.
- Electron and React desktop interface.
- JSON-lines communication with the Python runtime.
- Browser automation and external integrations.
- Mission management and execution monitoring.
- Human approval workflows.

Further development is focused on improving runtime reliability, expanding agent capabilities, strengthening execution controls, and bringing the desktop experience closer to a unified AI operating environment.

HIVE is currently an alpha-stage project. Not every planned capability is production-ready.

---

## Design Philosophy

HIVE is built around five principles:

1. **Collective Intelligence:** Complex work should be distributed across specialized agents.
2. **Autonomy with Oversight:** Agents should execute independently within clearly defined boundaries.
3. **Transparency:** Users should understand what agents are doing and why.
4. **Adaptability:** The workforce should adapt to the requirements of each mission.
5. **Practical Execution:** Intelligence should translate into completed work, not just generated responses.

---

## Roadmap

- [ ] More reliable persistent agent runtime.
- [ ] Advanced mission planning and delegation.
- [ ] Expanded coding and development capabilities.
- [ ] Deeper browser and desktop automation.
- [ ] Improved file and document workflows.
- [ ] Stronger permission and approval infrastructure.
- [ ] Agent memory and cross-mission continuity.
- [ ] Enterprise workspace and identity management.
- [ ] Advanced execution observability and recovery.

---

## Contributing

HIVE is being developed as an evolving AI execution environment.

Contributions, technical feedback, architectural discussions and ideas are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Make your changes.
4. Test your implementation.
5. Submit a pull request.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**HIVE — From individual AI assistants to coordinated autonomous workforces.**
