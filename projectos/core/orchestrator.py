"""Cross-project orchestration over registered solo projects."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .cross_task import CrossTaskStore
from .models import CrossProjectTask, ProjectTask
from .registry import ProjectRegistry
from .solo_adapter import SoloCommandError, SoloProjectAdapter


class CrossProjectOrchestrator:
    """Create and run project-level task graphs through child solo CLIs."""

    def __init__(
        self,
        registry: ProjectRegistry,
        store: Optional[CrossTaskStore] = None,
    ):
        self.registry = registry
        self.store = store or CrossTaskStore()

    def dispatch(
        self,
        title: str,
        project_ids: Optional[List[str]] = None,
        dependencies: Optional[Dict[str, List[str]]] = None,
        workflow: str = "",
    ) -> CrossProjectTask:
        selected = project_ids or [
            project.id
            for project in self.registry.list(status="active")
            if project.kind == "solo"
        ]
        if not selected:
            raise ValueError("No active solo projects selected.")
        for project_id in selected:
            project = self.registry.get(project_id)
            if project is None:
                raise KeyError(f"Project '{project_id}' not found")
            if project.kind != "solo":
                raise ValueError(f"Project '{project_id}' is not a solo project")

        task = self.store.create(title, selected, dependencies=dependencies)
        self._dispatch_ready(task, workflow=workflow)
        self._refresh_status(task)
        self.store.save(task)
        return task

    def run(self, task_id: str = "", until: str = "done", workflow: str = "") -> CrossProjectTask:
        task = self._resolve_task(task_id)
        max_steps = max(1, len(task.project_tasks) * 3)
        for _ in range(max_steps):
            changed = self._dispatch_ready(task, workflow=workflow)
            changed = self._run_ready(task, until=until) or changed
            self._refresh_status(task)
            self.store.save(task)
            if task.status in {"completed", "failed"}:
                break
            if not changed:
                break
        return task

    def retry(self, project_id: str, task_id: str = "", phase: str = "", agent: str = "") -> CrossProjectTask:
        if bool(phase) == bool(agent):
            raise ValueError("Use exactly one of phase or agent.")
        task = self._resolve_task(task_id)
        node = _require_project_node(task, project_id)
        if not node.solo_task_id:
            raise ValueError(f"Project node '{project_id}' has not been dispatched yet.")
        project = self.registry.get(project_id)
        if project is None:
            raise KeyError(f"Project '{project_id}' not found")
        try:
            SoloProjectAdapter(project.local_path).retry(task_id=node.solo_task_id, phase=phase, agent=agent)
        except SoloCommandError as exc:
            node.status = "failed"
            node.failed_reason = exc.stderr or exc.stdout or str(exc)
            self._refresh_status(task)
            self.store.save(task)
            raise
        node.status = "in_progress"
        node.failed_reason = ""
        node.completed_at = None
        node.last_summary = f"retried {'agent ' + agent if agent else 'phase ' + phase}"
        node.updated_at = _now()
        self._refresh_status(task)
        self.store.save(task)
        self.store.append_event(task.id, "project_task.retried", {"project_id": project_id, "phase": phase, "agent": agent})
        return task

    def reopen(self, project_id: str, phase: str, task_id: str = "") -> CrossProjectTask:
        task = self._resolve_task(task_id)
        node = _require_project_node(task, project_id)
        if not node.solo_task_id:
            raise ValueError(f"Project node '{project_id}' has not been dispatched yet.")
        project = self.registry.get(project_id)
        if project is None:
            raise KeyError(f"Project '{project_id}' not found")
        try:
            SoloProjectAdapter(project.local_path).reopen(task_id=node.solo_task_id, phase=phase)
        except SoloCommandError as exc:
            node.status = "failed"
            node.failed_reason = exc.stderr or exc.stdout or str(exc)
            self._refresh_status(task)
            self.store.save(task)
            raise
        node.status = "in_progress"
        node.failed_reason = ""
        node.completed_at = None
        node.last_summary = f"reopened phase {phase}"
        node.updated_at = _now()
        self._refresh_status(task)
        self.store.save(task)
        self.store.append_event(task.id, "project_task.reopened", {"project_id": project_id, "phase": phase})
        return task

    def status_payload(self, task_id: str = "") -> Dict:
        tasks = [self._resolve_task(task_id)] if task_id else self.store.list()
        return {
            "summary": {
                "total_cross_tasks": len(tasks),
                "active_cross_tasks": len([task for task in tasks if task.status in {"pending", "in_progress", "blocked"}]),
                "failed_cross_tasks": len([task for task in tasks if task.status == "failed"]),
                "completed_cross_tasks": len([task for task in tasks if task.status == "completed"]),
            },
            "cross_tasks": [self._task_payload(task) for task in tasks],
        }

    def _dispatch_ready(self, task: CrossProjectTask, workflow: str = "") -> bool:
        changed = False
        completed = self._completed_projects(task)
        for node in task.project_tasks:
            if node.solo_task_id or node.status in {"completed", "failed"}:
                continue
            if not set(node.depends_on).issubset(completed):
                node.status = "blocked"
                continue
            project = self.registry.get(node.project_id)
            if project is None:
                node.status = "failed"
                node.failed_reason = f"Project '{node.project_id}' not found"
                changed = True
                continue
            try:
                prompt = self._build_dispatch_prompt(task, node)
                payload = SoloProjectAdapter(project.local_path).dispatch(prompt, workflow=workflow)
            except SoloCommandError as exc:
                node.status = "failed"
                node.failed_reason = exc.stderr or exc.stdout or str(exc)
                self.store.append_event(task.id, "project_task.dispatch_failed", {"project_id": node.project_id, "error": node.failed_reason})
                changed = True
                continue
            node.solo_task_id = _extract_solo_task_id(payload)
            node.status = "in_progress"
            node.updated_at = _now()
            self.store.append_event(task.id, "project_task.dispatched", {"project_id": node.project_id, "solo_task_id": node.solo_task_id})
            changed = True
        return changed

    def _run_ready(self, task: CrossProjectTask, until: str = "done") -> bool:
        changed = False
        completed = self._completed_projects(task)
        for node in task.project_tasks:
            if node.status != "in_progress" or not node.solo_task_id:
                continue
            if not set(node.depends_on).issubset(completed):
                node.status = "blocked"
                changed = True
                continue
            project = self.registry.get(node.project_id)
            if project is None:
                node.status = "failed"
                node.failed_reason = f"Project '{node.project_id}' not found"
                changed = True
                continue
            try:
                payload = SoloProjectAdapter(project.local_path).run(until=until, task_id=node.solo_task_id)
            except SoloCommandError as exc:
                node.status = "failed"
                node.failed_reason = exc.stderr or exc.stdout or str(exc)
                self.store.append_event(task.id, "project_task.run_failed", {"project_id": node.project_id, "error": node.failed_reason})
                changed = True
                continue
            self._apply_run_payload(node, payload)
            self.store.append_event(task.id, "project_task.ran", {"project_id": node.project_id, "status": node.status})
            changed = True
        return changed

    def _apply_run_payload(self, node: ProjectTask, payload: Dict) -> None:
        stopped = str(payload.get("stopped_reason", ""))
        failed_phase = str(payload.get("failed_phase", ""))
        task_payload = payload.get("task") if isinstance(payload.get("task"), dict) else {}
        task_status = str(task_payload.get("status", ""))
        if failed_phase or task_status == "failed":
            node.status = "failed"
            node.failed_reason = failed_phase or str(task_payload.get("failed_reason", "")) or "solo run failed"
        elif stopped == "done" or task_status == "completed":
            node.status = "completed"
            node.completed_at = _now()
            node.failed_reason = ""
        elif stopped == "blocked" or task_status == "blocked":
            node.status = "blocked"
        else:
            node.status = "in_progress"
        node.last_summary = _summary_from_run_payload(payload)
        node.updated_at = _now()

    def _refresh_status(self, task: CrossProjectTask) -> None:
        statuses = {node.status for node in task.project_tasks}
        if statuses and statuses <= {"completed"}:
            task.status = "completed"
            task.completed_at = task.completed_at or _now()
            task.final_report = self._final_report(task)
            self.store.append_event(task.id, "cross_task.completed", {"projects": [node.project_id for node in task.project_tasks]})
        elif "failed" in statuses:
            task.status = "failed"
        elif "in_progress" in statuses:
            task.status = "in_progress"
        elif "blocked" in statuses:
            task.status = "blocked"
        else:
            task.status = "pending"
        task.updated_at = _now()

    def _resolve_task(self, task_id: str) -> CrossProjectTask:
        task = self.store.get(task_id) if task_id else self.store.latest()
        if task is None:
            raise KeyError("No cross-project task found.")
        return task

    def _completed_projects(self, task: CrossProjectTask) -> set[str]:
        return {node.project_id for node in task.project_tasks if node.status == "completed"}

    def _build_dispatch_prompt(self, task: CrossProjectTask, node: ProjectTask) -> str:
        if not node.depends_on:
            return node.prompt
        lines = [node.prompt, "", "## Dependency Context"]
        for dependency_id in node.depends_on:
            dependency = task.get_project_task(dependency_id)
            if dependency is None or not dependency.solo_task_id:
                lines.append(f"- {dependency_id}: no completed solo task available yet.")
                continue
            project = self.registry.get(dependency_id)
            if project is None:
                lines.append(f"- {dependency_id}: project is no longer registered.")
                continue
            try:
                payload = SoloProjectAdapter(project.local_path).inspect(task_id=dependency.solo_task_id)
            except SoloCommandError as exc:
                error = exc.stderr or exc.stdout or str(exc)
                lines.append(f"- {dependency_id}: unable to inspect upstream task: {error}")
                continue
            lines.extend(_inspect_context_lines(dependency_id, dependency, payload))
        return "\n".join(lines)

    def _task_payload(self, task: CrossProjectTask) -> Dict:
        return task.to_dict()

    def _final_report(self, task: CrossProjectTask) -> str:
        lines = [f"# {task.title}", "", "Completed project nodes:"]
        for node in task.project_tasks:
            lines.append(f"- {node.project_id}: {node.solo_task_id or '-'}")
        return "\n".join(lines)


def parse_dependency_specs(specs: List[str]) -> Dict[str, List[str]]:
    dependencies: Dict[str, List[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise ValueError(f"Invalid dependency spec: {spec}. Expected project:dependency")
        project_id, depends_on = spec.split(":", 1)
        project_id = project_id.strip()
        depends_on = depends_on.strip()
        if not project_id or not depends_on:
            raise ValueError(f"Invalid dependency spec: {spec}. Expected project:dependency")
        dependencies.setdefault(project_id, [])
        for dep in depends_on.split(","):
            dep = dep.strip()
            if dep and dep not in dependencies[project_id]:
                dependencies[project_id].append(dep)
    return dependencies


def _extract_solo_task_id(payload: Dict) -> str:
    task = payload.get("task")
    if isinstance(task, dict):
        return str(task.get("id") or "")
    return str(payload.get("task_id") or "")


def _require_project_node(task: CrossProjectTask, project_id: str) -> ProjectTask:
    node = task.get_project_task(project_id)
    if node is None:
        raise KeyError(f"Project node '{project_id}' not found in cross task {task.id}.")
    return node


def _summary_from_run_payload(payload: Dict) -> str:
    if payload.get("stopped_reason"):
        return f"stopped: {payload['stopped_reason']}"
    task = payload.get("task")
    if isinstance(task, dict) and task.get("status"):
        return f"task status: {task['status']}"
    return ""


def _inspect_context_lines(project_id: str, node: ProjectTask, payload: Dict) -> List[str]:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    dashboard = payload.get("dashboard") if isinstance(payload.get("dashboard"), dict) else {}
    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    lines = [
        f"### {project_id}",
        f"- solo_task_id: {node.solo_task_id}",
        f"- status: {task.get('status', node.status)}",
    ]
    current_phase = task.get("current_phase")
    if current_phase:
        lines.append(f"- current_phase: {current_phase}")
    failed_reason = dashboard.get("failed_reason") or task.get("failed_reason")
    if failed_reason:
        lines.append(f"- failed_reason: {failed_reason}")
    progress = dashboard.get("progress") or dashboard.get("phase_progress")
    if progress:
        lines.append(f"- progress: {progress}")
    if node.last_summary:
        lines.append(f"- run_summary: {node.last_summary}")
    if artifacts:
        lines.append("- artifacts:")
        for artifact in artifacts[:12]:
            if not isinstance(artifact, dict):
                continue
            kind = artifact.get("kind", "artifact")
            rel = artifact.get("relative_path") or artifact.get("name") or artifact.get("path")
            lines.append(f"  - {kind}: {rel}")
        if len(artifacts) > 12:
            lines.append(f"  - ... {len(artifacts) - 12} more")
    return lines


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
