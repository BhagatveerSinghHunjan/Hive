# HIVE Desktop — 60-minute demo shell

Electron + React desktop shell for the existing HIVE Python runtime. The backend is
unchanged: the Electron main process spawns `python -m hive.cli --server` and proxies
its JSON-lines protocol over IPC.

```
React renderer
  ↕ window.hive (preload)
Electron main  ──stdin/stdout JSON lines──  Python HiveServer
                                              └─ Leader → agents → tools
```

## Run

```powershell
cd C:\Users\lokes\OneDrive\Desktop\PEC\Hive\desktop
npm install
npm run dev
```

`npm run dev` starts Vite on port 5173, waits for it, then opens Electron.

For a debuggable dev session with Chrome DevTools Protocol on port 9333:

```powershell
npm run dev:debug
```

The window sizes itself from the primary display's work area, so the composer stays
visible at 125% Windows scaling and on smaller laptop screens.

Production-ish build:

```powershell
npm run build
npm start
```

## Interpreter selection

The bridge tries, in order:

1. `HIVE_PYTHON` environment variable
2. `<repo>/.venv/Scripts/python.exe`
3. the Python resolved by `py -3.13` (this machine has the core HIVE deps there)
4. `python`

Do not use the bare `python` on this machine: it is 3.12 and lacks `httpx`, `openai`, etc.

## Configuration

The Python backend loads `.env` from the repo root. Create it before the demo:

```
DASHSCOPE_API_KEY=sk-...
QWEN_MODEL=qwen3.7-plus
```

Without a key the runtime still starts and emits `ready`, but LLM calls fail and the
desktop app shows the real error. A rejected or invalid key also raises a banner with a
**Restart runtime** button; the Python process only reads `.env` at startup, so edit the
file first, then restart.

## Screens

- **Dashboard** — runtime state, current mission, credits, active agents, recent events, quick prompts.
- **Execution Monitor** — live stream, full event timeline, agent rail, tool-call arguments, runtime log.
- **Approvals** — permission requests (tool/target/tier) and human prompts (2FA, checkout, CAPTCHA).

`Agent Studio` and `Workspace` are intentionally disabled post-demo placeholders; they
are not fake screens.

## Protocol notes

Outbound from the desktop app:

```json
{"type":"user_message","content":"..."}
{"type":"permission_response","request_id":"...","decision":"approved"}
{"type":"interactive_response","request_id":"...","result":"..."}
{"type":"quit"}
```

`result` is a string for 2FA, a boolean for checkout/CAPTCHA, and `null` to cancel 2FA.

There is no backend cancel command. The sidebar's **Stop & restart runtime** sends
`quit`, kills the old process, and starts a fresh one. It is real, not a UI-only cancel.

## 60-minute demo script

1. Open the app; Dashboard shows runtime connected.
2. Ask: `Create a file called hive-demo.md with a 5-line summary of HIVE.`
3. Watch the Execution Monitor stream the run and show the tool call.
4. Approve the file write in Approvals.
5. Show the final response and credits spent.
6. Use **Stop & restart runtime** to prove clean recovery.

Avoid browser automation, MCP, PPT, and payment demos in this pass: those optional
dependencies are not installed in the Python 3.13 environment.

## Troubleshooting

If Electron reports `Electron failed to install correctly`, the npm postinstall did not
extract its cached zip on this machine. Fix it with:

```powershell
cd desktop
node node_modules/electron/install.js
```

If that still leaves `node_modules\electron\dist` incomplete, extract
`%LOCALAPPDATA%\electron\Cache\<hash>\electron-v<version>-win32-x64.zip` into
`node_modules\electron\dist` and create `node_modules\electron\path.txt` containing
`electron.exe`. This was required once on this machine; the app itself is unaffected.

## Known gaps (deliberate)

- No Agent Studio CRUD, file tree/editor, or embedded terminal yet.
- No installer, auto-update, signing, or packaged Python sidecar yet.
- No FastAPI/WebSocket local API — the existing JSON-lines bridge is reused.
- No Tauri shell yet; the machine lacks Rust/MSVC. Migration is post-demo.
