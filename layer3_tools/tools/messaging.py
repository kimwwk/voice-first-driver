"""Messaging tool — send and list messages."""
import json
import os
from datetime import datetime


def register(mcp):
    data_dir = os.environ.get("CHILL_DATA_DIR", "data")
    log_path = os.path.join(data_dir, "messages.jsonl")

    @mcp.tool()
    def send_message(recipient: str, content: str, platform: str = "log") -> str:
        """Send a message to a recipient.

        Args:
            recipient: Who to send the message to.
            content: The message content.
            platform: Delivery platform — "log" (default, local log) or "telegram".
        """
        os.makedirs(data_dir, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "recipient": recipient,
            "content": content,
            "platform": platform,
            "status": "pending",
        }

        if platform == "telegram":
            token = os.environ.get("TELEGRAM_BOT_TOKEN")
            chat_id = os.environ.get("TELEGRAM_CHAT_ID")
            if token and chat_id:
                try:
                    import urllib.request
                    payload = json.dumps({"chat_id": chat_id, "text": f"To {recipient}: {content}"})
                    req = urllib.request.Request(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        data=payload.encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        entry["status"] = "sent" if resp.status == 200 else "failed"
                except Exception as e:
                    entry["status"] = "failed"
                    entry["error"] = str(e)
            else:
                entry["status"] = "failed"
                entry["error"] = "Telegram not configured"
        else:
            entry["status"] = "logged"

        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return f"Message to {recipient} via {platform}: '{content}' — status: {entry['status']}"

    @mcp.tool()
    def list_messages(count: int = 10) -> str:
        """List recent messages.

        Args:
            count: Number of recent messages to show (default 10).
        """
        if not os.path.exists(log_path):
            return "No messages yet."
        with open(log_path) as f:
            lines = f.readlines()
        messages = [json.loads(line) for line in lines[-count:]]
        if not messages:
            return "No messages yet."
        parts = []
        for m in reversed(messages):
            ts = m["timestamp"][:16].replace("T", " ")
            parts.append(f"[{ts}] To {m['recipient']} ({m['platform']}): {m['content']} [{m['status']}]")
        return "\n".join(parts)
