"""Data models for ProjectOS."""
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict
from datetime import datetime, timezone


@dataclass
class Project:
    id: str
    name: str
    repo_url: str
    local_path: str
    status: str = "active"  # active | paused | archived
    kind: str = "legacy"  # solo | legacy
    protocol_version: int = 0
    health: str = "unknown"  # unknown | healthy | unhealthy | missing
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    team: Dict[str, bool] = field(default_factory=lambda: {
        "secretary": True,
        "cpo": True,
        "cto": True,
        "dev": True,
        "qa": True,
        "growth": False,
        "analyst": False,
    })
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Project":
        return cls(**data)


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    description: str = ""
    phase: str = "dev"  # cto | dev | qa | review | merge | done
    status: str = "pending"  # pending | in_progress | blocked | completed | failed
    priority: int = 3  # 1 (highest) to 5 (lowest)
    branch: Optional[str] = None
    assignee: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    parent_task: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        return cls(**data)


@dataclass
class AgentInstance:
    id: str
    role: str  # secretary | cto | dev | qa | growth
    status: str = "idle"  # idle | busy | error
    current_project: Optional[str] = None
    current_task: Optional[str] = None
    history: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentInstance":
        return cls(**data)


@dataclass
class ProjectTask:
    project_id: str
    title: str
    prompt: str
    solo_task_id: str = ""
    status: str = "pending"  # pending | blocked | in_progress | completed | failed
    depends_on: List[str] = field(default_factory=list)
    failed_reason: str = ""
    last_summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ProjectTask":
        return cls(**data)


@dataclass
class CrossProjectTask:
    id: str
    title: str
    description: str = ""
    status: str = "pending"  # pending | in_progress | blocked | completed | failed
    project_tasks: List[ProjectTask] = field(default_factory=list)
    final_report: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["project_tasks"] = [task.to_dict() for task in self.project_tasks]
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "CrossProjectTask":
        payload = dict(data)
        payload["project_tasks"] = [
            ProjectTask.from_dict(item)
            for item in payload.get("project_tasks", [])
        ]
        return cls(**payload)

    def get_project_task(self, project_id: str) -> Optional[ProjectTask]:
        for task in self.project_tasks:
            if task.project_id == project_id:
                return task
        return None
