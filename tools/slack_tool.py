from datetime import datetime
import time

class SlackTool:
    def __init__(self):
        self.default_channels = {
            "alert": "#alerts",
            "update": "#updates",
            "critical": "#critical"
        }

    def send_message(self, channel, message, retries=2):
        for attempt in range(retries + 1):
            try:
                timestamp = datetime.now().isoformat()

                print("\n[SLACK MESSAGE]")
                print(f"Time: {timestamp}")
                print(f"Channel: {channel}")
                print(f"Message: {message}")

                return {
                    "status": "sent",
                    "channel": channel,
                    "time": timestamp
                }

            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                else:
                    return {"status": "failed", "error": str(e)}

    def notify_delay(self, task):
        priority = task.get("priority", "medium")

        channel = (
            self.default_channels["critical"]
            if priority == "high"
            else self.default_channels["alert"]
        )

        return self.send_message(
            channel,
            f"Task '{task.get('task')}' is delayed!\nPriority: {priority}"
        )

    def notify_success(self, task):
        return self.send_message(
            self.default_channels["update"],
            f"Task '{task.get('task')}' completed successfully!"
        )

    def notify_escalation(self, task):
        return self.send_message(
            self.default_channels["critical"],
            (
                f"ESCALATION: Task '{task.get('task')}' is critically delayed!\n"
                f"Assigned To: {task.get('assigned_to', 'N/A')}"
            )
        )

    def send_summary(self, stats):
        return self.send_message(
            self.default_channels["update"],
            (
                f"Workflow Summary\n"
                f"Total: {stats.get('total_tasks')}\n"
                f"Completed: {stats.get('completed_tasks')}\n"
                f"Delayed: {stats.get('delayed_tasks')}\n"
                f"Efficiency: {stats.get('efficiency'):.2f}"
            )
        )