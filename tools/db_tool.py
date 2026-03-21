from datetime import datetime
import uuid

class DBTool:
    def __init__(self):
        self.storage = []

    def save(self, record):
        record["id"] = str(uuid.uuid4())
        record["created_at"] = datetime.now().isoformat()
        self.storage.append(record)

        return {"status": "saved", "data": record}

    def fetch_all(self):
        return self.storage

    def find_by_id(self, record_id):
        for r in self.storage:
            if r["id"] == record_id:
                return r
        return None

    def update_status(self, record_id, status):
        record = self.find_by_id(record_id)
        if record:
            record["status"] = status
            record["updated_at"] = datetime.now().isoformat()
            return {"status": "updated", "data": record}
        return {"status": "not_found"}

    def delete(self, record_id):
        self.storage = [r for r in self.storage if r["id"] != record_id]
        return {"status": "deleted"}

    def find_delayed_tasks(self):
        return [r for r in self.storage if r.get("status") == "delayed"]

    def find_by_status(self, status):
        return [r for r in self.storage if r.get("status") == status]

    def get_stats(self):
        total = len(self.storage)
        delayed = len(self.find_delayed_tasks())
        completed = len(self.find_by_status("completed"))

        return {
            "total_tasks": total,
            "delayed_tasks": delayed,
            "completed_tasks": completed,
            "efficiency": (completed / max(1, total))
        }