"""Cross-project task persistence."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .models import CrossProjectTask, ProjectTask


class CrossTaskStore:
    """Store cross-project task graphs as a ProjectOS-owned snapshot."""

    def __init__(self, base_dir: str = "projectos/state"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.base_dir / "cross_tasks.json"
        self.events_file = self.base_dir / "events.jsonl"
        self._tasks: Dict[str, CrossProjectTask] = {}
        self._load()

    def create(
        self,
        title: str,
        project_ids: List[str],
        dependencies: Optional[Dict[str, List[str]]] = None,
        description: str = "",
    ) -> CrossProjectTask:
        task_id = self.next_id()
        dependency_map = dependencies or {}
        project_tasks = [
            ProjectTask(
                project_id=project_id,
                title=title,
                prompt=_project_prompt(title, project_id, dependency_map.get(project_id, [])),
                status="blocked" if dependency_map.get(project_id) else "pending",
                depends_on=list(dependency_map.get(project_id, [])),
            )
            for project_id in project_ids
        ]
        task = CrossProjectTask(
            id=task_id,
            title=title,
            description=description,
            project_tasks=project_tasks,
        )
        self._tasks[task.id] = task
        self.save(task)
        self.append_event(task.id, "cross_task.created", {"projects": project_ids})
        return task

    def get(self, task_id: str) -> Optional[CrossProjectTask]:
        return self._tasks.get(task_id)

    def latest(self) -> Optional[CrossProjectTask]:
        if not self._tasks:
            return None
        return sorted(self._tasks.values(), key=lambda task: task.created_at)[-1]

    def list(self) -> List[CrossProjectTask]:
        return sorted(self._tasks.values(), key=lambda task: task.created_at)

    def save(self, task: CrossProjectTask) -> None:
        task.updated_at = _now()
        self._tasks[task.id] = task
        self._save()

    def append_event(self, task_id: str, event: str, details: Optional[Dict] = None) -> None:
        payload = {
            "ts": _now(),
            "cross_task_id": task_id,
            "event": event,
            "details": details or {},
        }
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def next_id(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        prefix = f"XPROJ-{today}-"
        existing = [
            int(task_id.replace(prefix, ""))
            for task_id in self._tasks
            if task_id.startswith(prefix) and task_id.replace(prefix, "").isdigit()
        ]
        return f"{prefix}{(max(existing) + 1 if existing else 1):03d}"

    def _load(self) -> None:
        if not self.tasks_file.exists():
            return
        raw = json.loads(self.tasks_file.read_text(encoding="utf-8") or "{}")
        for task_id, payload in raw.items():
            self._tasks[task_id] = CrossProjectTask.from_dict(payload)

    def _save(self) -> None:
        payload = {
            task_id: task.to_dict()
            for task_id, task in self._tasks.items()
        }
        temp = self.tasks_file.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp), str(self.tasks_file))


def _project_prompt(title: str, project_id: str, dependencies: List[str]) -> str:
    lines = [
        f"Cross-project task: {title}",
        f"Project node: {project_id}",
    ]
    if dependencies:
        lines.append(f"Depends on completed project nodes: {', '.join(dependencies)}")
    lines.extend([
        "",
        "Stay within this project's repository boundary.",
        "Report implementation, tests, blockers, and artifacts for solo-os aggregation.",
    ])
    return "\n".join(lines)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
