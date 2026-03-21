from datetime import datetime, timedelta
import uuid

class CalendarTool:
    def __init__(self):
        self.tasks = []

    def schedule_task(self, task_name, minutes_from_now=30, priority="medium"):
        scheduled_time = datetime.now() + timedelta(minutes=minutes_from_now)

        task = {
            "id": str(uuid.uuid4()),
            "task": task_name,
            "scheduled_at": scheduled_time.isoformat(),
            "priority": priority,
            "status": "scheduled",
            "created_at": datetime.now().isoformat()
        }

        self.tasks.append(task)

        return task

    def is_overdue(self, scheduled_time):
        try:
            return datetime.now() > datetime.fromisoformat(scheduled_time)
        except:
            return False

    def get_overdue_tasks(self):
        return [
            task for task in self.tasks
            if self.is_overdue(task["scheduled_at"]) and task["status"] != "completed"
        ]

    def mark_completed(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "completed"
                return task
        return None

    def get_all_tasks(self):
        return self.tasks

    def get_task_stats(self):
        total = len(self.tasks)
        overdue = len(self.get_overdue_tasks())

        return {
            "total_tasks": total,
            "overdue_tasks": overdue,
            "efficiency": (total - overdue) / max(1, total)
        }