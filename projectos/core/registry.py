"""Project registry — CRUD and persistence."""
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from .models import Project


class ProjectRegistry:
    """Manage project registration with atomic JSON persistence."""

    def __init__(self, db_path: str = "projectos/projects.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._projects: Dict[str, Project] = {}
        self._load()

    def create(self, project: Project) -> str:
        """Register a new project. Returns project_id."""
        if project.id in self._projects:
            raise ValueError(f"Project '{project.id}' already exists")
        self._projects[project.id] = project
        self._save()
        return project.id

    def get(self, project_id: str) -> Optional[Project]:
        return self._projects.get(project_id)

    def list(self, status: Optional[str] = None) -> List[Project]:
        projects = list(self._projects.values())
        if status:
            projects = [p for p in projects if p.status == status]
        return projects

    def update(self, project_id: str, **kwargs) -> None:
        project = self._projects.get(project_id)
        if not project:
            raise KeyError(f"Project '{project_id}' not found")
        for key, value in kwargs.items():
            if hasattr(project, key):
                setattr(project, key, value)
            else:
                raise AttributeError(f"Project has no attribute '{key}'")
        self._save()

    def delete(self, project_id: str) -> None:
        if project_id not in self._projects:
            raise KeyError(f"Project '{project_id}' not found")
        del self._projects[project_id]
        self._save()

    def exists(self, project_id: str) -> bool:
        return project_id in self._projects

    def _load(self) -> None:
        if not self.db_path.exists():
            return
        raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        for pid, pdata in raw.items():
            self._projects[pid] = Project.from_dict(pdata)

    def _save(self) -> None:
        """Atomic write: temp file + rename."""
        data = {pid: p.to_dict() for pid, p in self._projects.items()}
        temp_path = self.db_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        shutil.move(str(temp_path), str(self.db_path))
