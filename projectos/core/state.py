"""State management — snapshots, transitions, crash recovery."""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .models import Task


VALID_TRANSITIONS = {
    "created": ["cto"],
    "cto": ["dev", "retry"],
    "dev": ["qa", "retry"],
    "qa": ["review", "retry"],
    "review": ["merge", "reject"],
    "merge": ["done"],
    "reject": ["dev"],
    "retry": ["dev", "qa", "review"],
}


class StateManager:
    """Manage task state transitions and project snapshots."""

    def __init__(self, base_dir: str = "projectos/state"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Task] = {}
        self._tasks_file = self.base_dir / "tasks.json"
        self._load_tasks()

    def snapshot(self, project_id: str) -> Dict:
        """Create a snapshot of all tasks for a project."""
        tasks = [t.to_dict() for t in self._tasks.values() if t.project_id == project_id]
        snapshot = {
            "project_id": project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tasks": tasks,
        }
        snap_path = self.base_dir / f"{project_id}_snapshot.json"
        snap_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
        return snapshot

    def restore(self, project_id: str) -> Dict:
        """Restore tasks from the latest snapshot."""
        snap_path = self.base_dir / f"{project_id}_snapshot.json"
        if not snap_path.exists():
            raise FileNotFoundError(f"No snapshot found for project '{project_id}'")
        data = json.loads(snap_path.read_text(encoding="utf-8"))
        for tdata in data.get("tasks", []):
            task = Task.from_dict(tdata)
            self._tasks[task.id] = task
        self._save_tasks()
        return data

    def transition(self, task_id: str, from_phase: str, to_phase: str) -> None:
        """Transition a task from one phase to another."""
        task = self._tasks.get(task_id)
        if not task:
            raise KeyError(f"Task '{task_id}' not found")
        if task.phase != from_phase:
            raise ValueError(
                f"Task '{task_id}' is in phase '{task.phase}', expected '{from_phase}'"
            )
        valid = VALID_TRANSITIONS.get(from_phase, [])
        if to_phase not in valid:
            raise ValueError(
                f"Invalid transition: '{from_phase}' -> '{to_phase}'. Valid: {valid}"
            )
        task.phase = to_phase
        task.updated_at = datetime.now(timezone.utc).isoformat()
        if to_phase == "done":
            task.status = "completed"
            task.completed_at = task.updated_at
        self._save_tasks()

    def add_task(self, task: Task) -> None:
        self._tasks[task.id] = task
        self._save_tasks()

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self, project_id: Optional[str] = None, phase: Optional[str] = None) -> List[Task]:
        tasks = list(self._tasks.values())
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]
        if phase:
            tasks = [t for t in tasks if t.phase == phase]
        return tasks

    def _load_tasks(self) -> None:
        if not self._tasks_file.exists():
            return
        raw = json.loads(self._tasks_file.read_text(encoding="utf-8"))
        for tid, tdata in raw.items():
            self._tasks[tid] = Task.from_dict(tdata)

    def _save_tasks(self) -> None:
        data = {tid: t.to_dict() for tid, t in self._tasks.items()}
        temp = self._tasks_file.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp), str(self._tasks_file))
