"""Timer tool — set, list, and cancel timers. Fire-and-forget via system `at` command."""
import json
import os
import subprocess
from datetime import datetime, timedelta


def register(mcp):
    data_dir = os.environ.get("CHILL_DATA_DIR", "data")
    timer_file = os.path.join(data_dir, "timers.json")

    def _load_timers() -> list[dict]:
        if os.path.exists(timer_file):
            with open(timer_file) as f:
                return json.load(f)
        return []

    def _save_timers(timers: list[dict]) -> None:
        os.makedirs(data_dir, exist_ok=True)
        with open(timer_file, "w") as f:
            json.dump(timers, f, indent=2)

    def _next_id(timers: list[dict]) -> str:
        existing = [int(t["id"].split("_")[1]) for t in timers if t["id"].startswith("timer_")]
        n = max(existing, default=0) + 1
        return f"timer_{n}"

    @mcp.tool()
    def set_timer(duration_seconds: int, label: str = "Timer") -> str:
        """Set a countdown timer.

        Args:
            duration_seconds: How many seconds until the timer fires.
            label: A short description for the timer.
        """
        timers = _load_timers()
        timer_id = _next_id(timers)
        fire_at = datetime.now() + timedelta(seconds=duration_seconds)

        entry = {
            "id": timer_id,
            "label": label,
            "duration_seconds": duration_seconds,
            "created_at": datetime.now().isoformat(),
            "fire_at": fire_at.isoformat(),
            "status": "active",
        }
        timers.append(entry)
        _save_timers(timers)

        # Fire-and-forget: try system `at` command, fall back to logged-only
        try:
            # Use `at` to schedule a notification
            at_time = fire_at.strftime("%H:%M %Y-%m-%d")
            notify_cmd = f'echo "TIMER FIRED: {label}" >> {os.path.join(data_dir, "timer_notifications.log")}'
            proc = subprocess.run(
                ["at", at_time],
                input=notify_cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                entry["scheduler"] = "at"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            entry["scheduler"] = "none"
            _save_timers(timers)

        if duration_seconds >= 60:
            mins = duration_seconds // 60
            secs = duration_seconds % 60
            dur_str = f"{mins}m {secs}s" if secs else f"{mins}m"
        else:
            dur_str = f"{duration_seconds}s"

        return f"Timer '{label}' set for {dur_str} (fires at {fire_at.strftime('%H:%M:%S')}). ID: {timer_id}"

    @mcp.tool()
    def list_timers() -> str:
        """List all timers (active, fired, and cancelled)."""
        timers = _load_timers()
        if not timers:
            return "No timers."
        lines = []
        for t in timers:
            fire_str = t["fire_at"][:19].replace("T", " ")
            lines.append(f"[{t['status']}] {t['label']} — fires at {fire_str} (id: {t['id']})")
        return "\n".join(lines)

    @mcp.tool()
    def cancel_timer(timer_id: str) -> str:
        """Cancel an active timer.

        Args:
            timer_id: The timer ID to cancel (e.g. "timer_1").
        """
        timers = _load_timers()
        for t in timers:
            if t["id"] == timer_id:
                if t["status"] != "active":
                    return f"Timer '{t['label']}' is already {t['status']}."
                t["status"] = "cancelled"
                _save_timers(timers)
                return f"Timer '{t['label']}' cancelled."
        return f"Timer '{timer_id}' not found."
