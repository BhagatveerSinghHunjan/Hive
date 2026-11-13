"""Native integrations for Gmail, Google Calendar, and Slack.

The coordinator profile talks to these services through HIVE tools. Credentials
are loaded from the local environment or ~/.hive and are never returned to the
LLM or the desktop renderer.
"""
