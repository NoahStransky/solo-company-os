"""Project dependency management with topological sorting."""
from typing import Dict, List, Set
from collections import deque

from .registry import ProjectRegistry


class CycleError(Exception):
    """Raised when a circular dependency is detected."""
    pass


class DependencyManager:
    """Manage inter-project dependencies and build order."""

    def __init__(self, registry: ProjectRegistry):
        self.registry = registry
        self._contracts: Dict[str, Dict] = {}

    def add_dependency(
        self, project_id: str, depends_on: str, contract: Dict
    ) -> None:
        """Register that project_id depends on depends_on."""
        if not self.registry.exists(project_id):
            raise KeyError(f"Project '{project_id}' not found")
        if not self.registry.exists(depends_on):
            raise KeyError(f"Dependency project '{depends_on}' not found")

        project = self.registry.get(project_id)
        if depends_on not in project.dependencies:
            project.dependencies.append(depends_on)
            self.registry.update(project_id, dependencies=project.dependencies)

        key = f"{project_id} -> {depends_on}"
        self._contracts[key] = contract

    def remove_dependency(self, project_id: str, depends_on: str) -> None:
        project = self.registry.get(project_id)
        if project and depends_on in project.dependencies:
            project.dependencies.remove(depends_on)
            self.registry.update(project_id, dependencies=project.dependencies)

    def get_dependencies(self, project_id: str) -> List[str]:
        project = self.registry.get(project_id)
        return project.dependencies if project else []

    def get_dependents(self, project_id: str) -> List[str]:
        dependents = []
        for project in self.registry.list():
            if project_id in project.dependencies:
                dependents.append(project.id)
        return dependents

    def get_contract(self, consumer: str, provider: str) -> Dict:
        key = f"{consumer} -> {provider}"
        return self._contracts.get(key, {})

    def validate_contract(self, provider: str, consumer: str) -> bool:
        """Check if provider meets consumer's contract requirements."""
        contract = self.get_contract(consumer, provider)
        if not contract:
            return True  # No contract means no requirements
        # In a real system, this would check OpenAPI schemas, versions, etc.
        provider_project = self.registry.get(provider)
        if not provider_project:
            return False
        return provider_project.status == "active"

    def build_order(self) -> List[str]:
        """Return projects in topological order (dependencies first)."""
        all_projects = {p.id for p in self.registry.list()}
        in_degree: Dict[str, int] = {pid: 0 for pid in all_projects}
        adj: Dict[str, List[str]] = {pid: [] for pid in all_projects}

        for project in self.registry.list():
            for dep in project.dependencies:
                if dep in all_projects:
                    adj[dep].append(project.id)
                    in_degree[project.id] += 1

        queue = deque([pid for pid, deg in in_degree.items() if deg == 0])
        order = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(all_projects):
            # Find cycle members
            remaining = [pid for pid in all_projects if pid not in order]
            raise CycleError(
                f"Circular dependency detected among: {remaining}"
            )

        return order

    def is_ready(self, project_id: str) -> bool:
        """Check if all dependencies of a project are satisfied."""
        for dep in self.get_dependencies(project_id):
            project = self.registry.get(dep)
            if not project or project.status != "active":
                return False
        return True
