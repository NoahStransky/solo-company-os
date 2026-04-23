"""Agent scheduler — resource allocation and queue management."""
from typing import Dict, List, Optional
from datetime import datetime, timezone

from .models import Task, AgentInstance
from .registry import ProjectRegistry


class AgentScheduler:
    """Schedule agents across projects with concurrency limits."""

    # Global limits per role
    ROLE_LIMITS = {
        "dev": 3,
        "cto": 2,
        "qa": 2,
        "secretary": 1,
        "growth": 1,
        "analyst": 1,
    }

    # Per-project limit per role
    PROJECT_ROLE_LIMIT = 1

    def __init__(self, registry: ProjectRegistry):
        self.registry = registry
        self.agents: Dict[str, AgentInstance] = {}
        self._queue: List[Task] = []
        self._agent_counter = 0

    def assign(self, task: Task, role: str) -> Optional[str]:
        """Assign an agent to a task. Returns agent_id or None if queued."""
        if not self.can_start(task.project_id, role):
            pos = self.queue(task)
            return None

        agent_id = self._find_or_create_agent(role)
        agent = self.agents[agent_id]
        agent.status = "busy"
        agent.current_project = task.project_id
        agent.current_task = task.id
        agent.history.append({
            "project": task.project_id,
            "task": task.id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        task.assignee = agent_id
        task.status = "in_progress"
        return agent_id

    def release(self, agent_id: str) -> None:
        """Release an agent after task completion."""
        agent = self.agents.get(agent_id)
        if not agent:
            return
        agent.status = "idle"
        agent.current_project = None
        agent.current_task = None
        # Try to assign next queued task
        self._process_queue()

    def queue(self, task: Task) -> int:
        """Add task to queue. Returns queue position (0-indexed)."""
        # Insert by priority (lower number = higher priority)
        inserted = False
        for i, queued in enumerate(self._queue):
            if task.priority < queued.priority:
                self._queue.insert(i, task)
                inserted = True
                break
        if not inserted:
            self._queue.append(task)
        task.status = "pending"
        return self._queue.index(task)

    def get_queue(self, project_id: Optional[str] = None) -> List[Task]:
        """Get queued tasks, optionally filtered by project."""
        tasks = self._queue
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]
        return tasks

    def can_start(self, project_id: str, role: str) -> bool:
        """Check if a new task can start for the given project and role."""
        # Check per-project limit
        project_busy = sum(
            1 for a in self.agents.values()
            if a.role == role and a.status == "busy" and a.current_project == project_id
        )
        if project_busy >= self.PROJECT_ROLE_LIMIT:
            return False

        # Check global role limit
        global_busy = sum(
            1 for a in self.agents.values()
            if a.role == role and a.status == "busy"
        )
        if global_busy >= self.ROLE_LIMITS.get(role, 1):
            return False

        return True

    def get_busy_agents(self, role: Optional[str] = None) -> List[AgentInstance]:
        agents = [a for a in self.agents.values() if a.status == "busy"]
        if role:
            agents = [a for a in agents if a.role == role]
        return agents

    def get_idle_agents(self, role: Optional[str] = None) -> List[AgentInstance]:
        agents = [a for a in self.agents.values() if a.status == "idle"]
        if role:
            agents = [a for a in agents if a.role == role]
        return agents

    def _find_or_create_agent(self, role: str) -> str:
        """Find an idle agent or create a new one."""
        for aid, agent in self.agents.items():
            if agent.role == role and agent.status == "idle":
                return aid
        self._agent_counter += 1
        agent_id = f"{role}-{self._agent_counter:03d}"
        self.agents[agent_id] = AgentInstance(id=agent_id, role=role)
        return agent_id

    def _process_queue(self) -> None:
        """Try to assign queued tasks to available agents."""
        to_remove = []
        for task in self._queue:
            if self.can_start(task.project_id, task.phase):
                agent_id = self.assign(task, task.phase)
                if agent_id:
                    to_remove.append(task)
        for task in to_remove:
            if task in self._queue:
                self._queue.remove(task)
