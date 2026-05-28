"""ProjectOS Core — Multi-project orchestration engine."""
from .models import Project, Task, AgentInstance, CrossProjectTask, ProjectTask
from .registry import ProjectRegistry
from .state import StateManager
from .scheduler import AgentScheduler
from .dependency import DependencyManager, CycleError
from .dashboard import Dashboard
from .solo_adapter import SoloProjectAdapter, SoloCommandError
from .cross_task import CrossTaskStore
from .orchestrator import CrossProjectOrchestrator

__all__ = [
    "Project",
    "Task",
    "AgentInstance",
    "CrossProjectTask",
    "ProjectTask",
    "ProjectRegistry",
    "StateManager",
    "AgentScheduler",
    "DependencyManager",
    "CycleError",
    "Dashboard",
    "SoloProjectAdapter",
    "SoloCommandError",
    "CrossTaskStore",
    "CrossProjectOrchestrator",
]
