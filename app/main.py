from tools.db_tool import DBTool
from tools.email_tool import EmailTool
from tools.slack_tool import SlackTool
from tools.calendar_tool import CalendarTool


def main():
    db = DBTool()
    email = EmailTool()
    slack = SlackTool()
    calendar = CalendarTool()

    # Step 1: Create Task
    task = calendar.schedule_task("Submit Report", 1)
    task["status"] = "delayed"
    task["assigned_to"] = "neeraj"
    task["priority"] = "high"

    db.save(task)

    # Step 2: Delay Detection
    if task["status"] == "delayed":
        email.send_delay_alert(task)
        slack.notify_delay(task)

        if task["priority"] == "high":
            slack.notify_escalation(task)

    # Step 3: Completion
    task["status"] = "completed"
    db.update_status(task["id"], "completed")

    email.send_completion_alert(task)
    slack.notify_success(task)

    # Step 4: SUMMARY 
    stats = db.get_stats()
    email.send_summary(stats)
    slack.send_summary(stats)

    # Step 5: Print stats
    print("\n[STATS]")
    print(stats)


if __name__ == "__main__":
    main()