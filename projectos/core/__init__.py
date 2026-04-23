"""ProjectOS Core — Multi-project orchestration engine."""
from .models import Project, Task, AgentInstance
from .registry import ProjectRegistry
from .state import StateManager
from .scheduler import AgentScheduler
from .dependency import DependencyManager, CycleError
from .dashboard import Dashboard

__all__ = [
    "Project",
    "Task",
    "AgentInstance",
    "ProjectRegistry",
    "StateManager",
    "AgentScheduler",
    "DependencyManager",
    "CycleError",
    "Dashboard",
]
