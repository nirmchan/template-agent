"""CLI name and shared strings (single place to rename the CLI)."""

import os

CLI_NAME = os.environ.get("CLI_NAME", "ask")
CONFIG_DIR_NAME = CLI_NAME
APP_DESCRIPTION = f"{CLI_NAME} — CLI chat client for Deep Agent"

CLI_INSTALL_HINT = "CLI dependencies not installed. Run: pip install -e '.[cli]'"

MISSING_URL_MSG = (
    f"No agent URL configured. Set AGENT_URL, run "
    f"`{CLI_NAME} config set url <url>`, or pass --url."
)

LOGIN_REQUIRED_MSG = f"Authentication required. Run `{CLI_NAME} login`."

CLI_FEATURE_FLAG = "ENABLE_CLI"
CLI_DISABLED_MSG = f"CLI is disabled. Set {CLI_FEATURE_FLAG}=true to enable."


def is_cli_enabled() -> bool:
    """Return True when the CLI feature flag is on (env ``ENABLE_CLI``)."""
    return os.environ.get(CLI_FEATURE_FLAG, "false").lower() == "true"
