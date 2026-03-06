import os
import threading
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from .executor import execute_plan
from .planner import generate_demo_plan, generate_demo_instructions

# Hardcoded defaults (same as CLI demo mode)
NUM_FILES = 5
FILE_FORMAT = "html"


def _load_env() -> None:
    """Load environment variables from .env and the ingestion agent's credentials."""
    load_dotenv()
    ingestion_creds = Path.home() / "data-ingestion-agent" / ".credentials" / "dev.env"
    if ingestion_creds.exists():
        load_dotenv(ingestion_creds, override=False)


def _run_pipeline(solution_script: str, context: str, say, thread_ts: str) -> None:
    """Run the full solutions agent pipeline and post results to the Slack thread."""
    try:
        say(text="Generating demo plan...", thread_ts=thread_ts)
        plan = generate_demo_plan(
            solution_script, NUM_FILES, context=context, file_format=FILE_FORMAT
        )

        say(
            text=(
                f"*Plan ready:* {plan.naming.project_name}\n"
                f"_{plan.summary}_\n"
                f"Executing..."
            ),
            thread_ts=thread_ts,
        )

        result = execute_plan(plan)

        say(text="Generating demo instructions...", thread_ts=thread_ts)
        instructions = generate_demo_instructions(plan, solution_script, context)

        # Save instructions locally
        company = plan.naming.project_name.split(" - ")[0].strip().lower().replace(" ", "-")
        instructions_dir = Path("demo-instructions")
        instructions_dir.mkdir(exist_ok=True)
        instructions_path = instructions_dir / f"{company}-{date.today().isoformat()}.txt"
        instructions_path.write_text(instructions, encoding="utf-8")

        say(
            text=(
                f"*Demo project created!*\n"
                f"*Project URL:* {result.project_url}\n"
                f"Files uploaded: {result.files_uploaded}\n"
                f"Format: {FILE_FORMAT}\n\n"
                f"*Demo instructions:*\n```\n{instructions}\n```"
            ),
            thread_ts=thread_ts,
        )

    except Exception as e:
        say(text=f"Error: {e}", thread_ts=thread_ts)


def _strip_mention(text: str, bot_user_id: str) -> str:
    """Remove the @mention of the bot from the message text."""
    import re
    return re.sub(rf"<@{bot_user_id}>\s*", "", text).strip()


def main() -> None:
    _load_env()

    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    # Resolve the bot's own user ID once at startup
    auth = app.client.auth_test()
    bot_user_id = auth["user_id"]
    print(f"Bot user ID: {bot_user_id}")

    def _handle_trigger(event, say, client):
        """Handle a message that mentions the bot (works for both app_mention and message events)."""
        print(f"[DEBUG] Triggered by: {event.get('text', '')[:100]}")

        # Must be a thread reply (not a top-level message)
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            say(
                text="Mention me in a thread reply — I'll use the previous message as the script and your reply as context.",
                thread_ts=event["ts"],
            )
            return

        # Fetch thread history
        resp = client.conversations_replies(
            channel=event["channel"],
            ts=thread_ts,
        )
        messages = resp["messages"]

        # Human messages only (exclude bot replies)
        human_messages = [m for m in messages if not m.get("bot_id")]

        if len(human_messages) < 2:
            say(
                text="I need at least one previous message in this thread to use as the solution script.",
                thread_ts=thread_ts,
            )
            return

        # Previous human message = script, current message (minus @mention) = context
        solution_script = human_messages[-2].get("text", "")
        context = _strip_mention(human_messages[-1].get("text", ""), bot_user_id)

        if not solution_script.strip():
            say(text="The previous message is empty — can't use it as a script.", thread_ts=thread_ts)
            return

        # Run pipeline in background so we don't block the Slack event handler
        threading.Thread(
            target=_run_pipeline,
            args=(solution_script, context, say, thread_ts),
            daemon=True,
        ).start()

    @app.event("app_mention")
    def handle_mention(event, say, client):
        _handle_trigger(event, say, client)

    @app.event("message")
    def handle_message(event, say, client):
        # Only trigger on messages that @mention the bot
        text = event.get("text", "")
        if f"<@{bot_user_id}>" not in text:
            return
        # Skip bot messages to avoid loops
        if event.get("bot_id"):
            return
        _handle_trigger(event, say, client)

    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    print("Solutions Agent Slack bot is running...")
    handler.start()


if __name__ == "__main__":
    main()
