# Google Integration Setup (Gmail + Calendar)

HIVE uses a **Desktop OAuth client** owned by you. No credentials are bundled
with the app, and tokens are never sent to the LLM or the desktop renderer.

## 1. Create the Google Cloud project

1. Open https://console.cloud.google.com/
2. Create a project, for example `hive-club-ops`.
3. Go to **APIs & Services → Library**.
4. Enable **Gmail API**.
5. Enable **Google Calendar API**.

## 2. Configure the OAuth consent screen

1. Go to **APIs & Services → OAuth consent screen**.
2. Choose **External** unless you have a Workspace organization.
3. Fill the app name and support email.
4. Add scopes:
   - `.../auth/gmail.modify`
   - `.../auth/gmail.send`
   - `.../auth/calendar`
   - `openid`, `email`, `profile`
5. Add the dedicated demo Google account under **Test users**.
6. Save.

The app can stay in **Testing** mode. Only the test users you add can authorize
it, which is exactly what the demo needs.

## 3. Create the OAuth client

1. Go to **APIs & Services → Credentials**.
2. Click **Create credentials → OAuth client ID**.
3. Application type: **Desktop app**.
4. Download the JSON file.
5. Save it here:

```text
C:\Users\<you>\.hive\google_oauth_client.json
```

Alternatively, set `GOOGLE_OAUTH_CLIENT_FILE` to the downloaded file, or put
`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`.

## 4. Connect the demo account

From the HIVE repository:

```powershell
py -3.13 -m hive.cli --connect-google
```

A browser window opens. Sign in with the **dedicated demo account**, review the
scopes, and approve. The token is written to:

```text
C:\Users\<you>\.hive\google_token.json
```

## 5. Verify

```powershell
py -3.13 -m hive.cli --check-integrations
```

Expected healthy output:

```json
{
  "google": {
    "libraries_installed": true,
    "client_configured": true,
    "token_present": true,
    "connected": true,
    "email": "demo-account@example.com"
  }
}
```

Then start HIVE normally. The desktop shell receives an `integration_status`
event at startup.

For a live read test, run:

```powershell
py -3.13 -m hive.cli --gmail-smoke "is:unread newer_than:2d"
```

This returns real message metadata (IDs, senders, subjects, snippets) without
modifying the mailbox.

## Scopes requested

| Scope | Why |
|---|---|
| `gmail.modify` | Read threads, labels, and draft management |
| `gmail.send` | Send approved replies |
| `calendar` | Read events, check conflicts, create/update events |
| `openid email profile` | Identify the connected account |

Phase 1 only uses read tools. Write tools are added behind approval gates in a
later phase.

## Security notes

- `google_token.json` and `google_oauth_client.json` live outside the repository.
- `read_file` treats `*token*` and `*oauth*client*` filenames as credential
  files and refuses to read them.
- Tool results contain mailbox data only — never access tokens, refresh tokens,
  or client secrets.
- Do not commit `.env`, the OAuth client JSON, or the token file.

## Troubleshooting

| Problem | Fix |
|---|---|
| `Google OAuth is not configured` | Save the client JSON to `~/.hive/google_oauth_client.json` or set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` |
| `Access blocked: app has not completed verification` | Add the account under **Test users** |
| `Gmail API has not been used in project...` | Enable Gmail API in the same project as the OAuth client |
| `invalid_grant` | Run `py -3.13 -m hive.cli --disconnect-google` and reconnect |
| Browser opens but callback fails | Check that localhost is allowed; set `GOOGLE_OAUTH_PORT=8765` if needed |
| `Google libraries are not installed` | `py -3.13 -m pip install -r requirements.txt` |

## Slack

Slack tools arrive in a later phase. When implemented, the bot token will be
read from `SLACK_BOT_TOKEN` in `.env` and will never be returned by a tool.
