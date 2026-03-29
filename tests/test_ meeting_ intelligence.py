"""tests/test_meeting_intelligence.py — Unit tests for meeting intelligence pipeline"""
import asyncio
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from meeting_intelligence.transcript_parser import TranscriptParser
from meeting_intelligence.task_generator import TaskGenerator
from meeting_intelligence.owner_assigner import OwnerAssigner
from meeting_intelligence.progress_tracker import ProgressTracker


SAMPLE_TRANSCRIPT = """Alice: Good morning everyone. Let's get started.
Bob: Sure. I wanted to discuss the deployment pipeline first.
Alice: Agreed. We decided to move to Docker-based deployments.
Bob: I will set up the staging environment by this Friday.
Charlie: I can update the CI/CD documentation by next Monday.
Alice: Good. We need to review the new access policies too.
Bob: I'll schedule a security review meeting this week.
Alice: One more thing — the client demo is next Wednesday. Diana, can you prepare the slides?
Diana: Yes, I'll have the presentation ready by Tuesday EOD.
Alice: Perfect. Any blockers?
Bob: The staging credentials are blocked — waiting on IT.
Alice: Let's wrap up then. Good meeting everyone."""


class TestTranscriptParser(unittest.TestCase):

    def setUp(self):
        self.parser = TranscriptParser()

    def test_parse_returns_dict(self):
        result = self.parser.parse(SAMPLE_TRANSCRIPT)
        self.assertIsInstance(result, dict)

    def test_extracts_speakers(self):
        result = self.parser.parse(SAMPLE_TRANSCRIPT)
        speakers = result["speakers"]
        self.assertIn("Alice", speakers)
        self.assertIn("Bob", speakers)
        self.assertIn("Charlie", speakers)
        self.assertIn("Diana", speakers)

    def test_creates_segments(self):
        result = self.parser.parse(SAMPLE_TRANSCRIPT)
        self.assertGreater(len(result["segments"]), 0)

    def test_empty_transcript(self):
        result = self.parser.parse("")
        self.assertEqual(result["segments"], [])

    def test_word_count(self):
        result = self.parser.parse(SAMPLE_TRANSCRIPT)
        self.assertGreater(result["word_count"], 50)


class TestTaskGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = TaskGenerator()

    def test_generates_tasks_from_action_items(self):
        extracted = {
            "action_items": [
                {"id": "ai_1", "description": "Bob will set up staging by Friday",
                 "owner_hint": "Bob", "deadline_hint": "Friday", "priority": "high"},
                {"id": "ai_2", "description": "Charlie updates docs by next Monday",
                 "owner_hint": "Charlie", "deadline_hint": "next Monday"},
            ]
        }
        tasks = self.generator.generate(extracted)
        self.assertEqual(len(tasks), 2)

    def test_task_has_required_fields(self):
        extracted = {
            "action_items": [
                {"id": "ai_1", "description": "Alice will do X", "owner_hint": "Alice", "deadline_hint": "tomorrow"}
            ]
        }
        tasks = self.generator.generate(extracted)
        task = tasks[0]
        self.assertIn("id", task)
        self.assertIn("title", task)
        self.assertIn("deadline", task)
        self.assertIn("priority", task)
        self.assertIn("status", task)
        self.assertEqual(task["status"], "pending")

    def test_priority_detection(self):
        extracted = {
            "action_items": [
                {"id": "ai_1", "description": "URGENT fix needed ASAP", "owner_hint": "Bob", "deadline_hint": "today"},
                {"id": "ai_2", "description": "eventually update docs", "owner_hint": "Alice", "deadline_hint": "eventually"},
            ]
        }
        tasks = self.generator.generate(extracted)
        self.assertEqual(tasks[0]["priority"], "high")
        self.assertEqual(tasks[1]["priority"], "low")

    def test_empty_action_items(self):
        tasks = self.generator.generate({"action_items": []})
        self.assertEqual(tasks, [])


class TestOwnerAssigner(unittest.TestCase):

    def setUp(self):
        self.assigner = OwnerAssigner()

    def test_assigns_known_owner(self):
        tasks = [{"id": "t1", "title": "Task", "owner_hint": "alice", "description": ""}]
        result = self.assigner.assign(tasks)
        self.assertEqual(result[0]["owner"], "Alice Johnson")
        self.assertEqual(result[0]["owner_email"], "alice@company.com")

    def test_assigns_partial_match(self):
        tasks = [{"id": "t1", "title": "Task", "owner_hint": "Bob Smith", "description": ""}]
        result = self.assigner.assign(tasks)
        self.assertEqual(result[0]["owner_email"], "bob@company.com")

    def test_fallback_to_manager(self):
        tasks = [{"id": "t1", "title": "Task", "owner_hint": "unknown_person_xyz", "description": ""}]
        result = self.assigner.assign(tasks)
        self.assertEqual(result[0]["owner_email"], "manager@company.com")
        self.assertIn("assignment_note", result[0])

    def test_assigns_multiple_tasks(self):
        tasks = [
            {"id": "t1", "title": "Task 1", "owner_hint": "alice", "description": ""},
            {"id": "t2", "title": "Task 2", "owner_hint": "bob", "description": ""},
        ]
        result = self.assigner.assign(tasks)
        self.assertEqual(result[0]["owner"], "Alice Johnson")
        self.assertEqual(result[1]["owner"], "Bob Smith")


class TestProgressTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = ProgressTracker()

    def test_register_and_retrieve_tasks(self):
        tasks = [
            {"id": "t1", "title": "Task 1", "status": "pending", "deadline": "2030-01-01T00:00:00+00:00"},
        ]
        self.tracker.register_tasks("wf_test", tasks)
        retrieved = self.tracker.get_all_tasks("wf_test")
        self.assertEqual(len(retrieved), 1)

    def test_update_task_status(self):
        tasks = [{"id": "t1", "title": "Task", "status": "pending", "deadline": "2030-01-01T00:00:00+00:00"}]
        self.tracker.register_tasks("wf_test2", tasks)
        self.tracker.update_task_status("wf_test2", "t1", "done")
        retrieved = self.tracker.get_all_tasks("wf_test2")
        self.assertEqual(retrieved[0]["status"], "done")

    def test_stall_detection(self):
        # Past deadline = stalled
        tasks = [{"id": "t1", "title": "Overdue Task", "status": "pending",
                  "deadline": "2020-01-01T00:00:00+00:00"}]
        self.tracker.register_tasks("wf_stall", tasks)
        stalled = self.tracker.get_stalled("wf_stall")
        self.assertEqual(len(stalled), 1)

    def test_done_task_not_stalled(self):
        tasks = [{"id": "t1", "title": "Done Task", "status": "done",
                  "deadline": "2020-01-01T00:00:00+00:00"}]
        self.tracker.register_tasks("wf_done", tasks)
        stalled = self.tracker.get_stalled("wf_done")
        self.assertEqual(len(stalled), 0)

    def test_completion_stats(self):
        tasks = [
            {"id": "t1", "status": "done", "deadline": "2030-01-01T00:00:00+00:00"},
            {"id": "t2", "status": "pending", "deadline": "2030-01-01T00:00:00+00:00"},
            {"id": "t3", "status": "pending", "deadline": "2020-01-01T00:00:00+00:00"},
        ]
        self.tracker.register_tasks("wf_stats", tasks)
        stats = self.tracker.get_completion_stats("wf_stats")
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["done"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)