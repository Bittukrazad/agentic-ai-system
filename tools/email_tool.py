from datetime import datetime
import time

class EmailTool:
    def __init__(self, default_recipient="team@company.com"):
        self.default_recipient = default_recipient

    def send_email(self, to, subject, message, retries=2):
        for attempt in range(retries + 1):
            try:
                timestamp = datetime.now().isoformat()

                print("\n[EMAIL SENT]")
                print(f"Time: {timestamp}")
                print(f"To: {to}")
                print(f"Subject: {subject}")
                print(f"Message: {message}")

                return {
                    "status": "sent",
                    "to": to,
                    "time": timestamp
                }

            except Exception as e:
                if attempt < retries:
                    time.sleep(1)
                else:
                    return {"status": "failed", "error": str(e)}

    def send_delay_alert(self, task):
        return self.send_email(
            to=task.get("assigned_to", self.default_recipient),
            subject="Task Delay Alert",
            message=(
                f"Task '{task.get('task')}' is delayed.\n"
                f"Priority: {task.get('priority', 'N/A')}\n"
                f"Please take action immediately."
            )
        )

    def send_completion_alert(self, task):
        return self.send_email(
            to=task.get("assigned_to", self.default_recipient),
            subject="Task Completed",
            message=(
                f"Task '{task.get('task')}' has been completed successfully.\n"
                f"Completed At: {datetime.now().isoformat()}"
            )
        )

    def send_summary(self, stats):
        return self.send_email(
            to=self.default_recipient,
            subject="Workflow Summary",
            message=(
                f"Total Tasks: {stats.get('total_tasks')}\n"
                f"Completed: {stats.get('completed_tasks')}\n"
                f"Delayed: {stats.get('delayed_tasks')}\n"
                f"Efficiency: {stats.get('efficiency'):.2f}"
            )
        )