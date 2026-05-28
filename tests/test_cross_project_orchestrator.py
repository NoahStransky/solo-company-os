"""Tests for cross-project orchestration."""
import json
import os
import subprocess
import sys
from pathlib import Path

from projectos.core.cross_task import CrossTaskStore
from projectos.core.orchestrator import CrossProjectOrchestrator
from projectos.core.registry import ProjectRegistry


def test_cross_project_orchestrator_dispatches_and_runs_dependencies(tmp_path, monkeypatch):
    backend = _make_solo_project(tmp_path, "backend", "Backend")
    frontend = _make_solo_project(tmp_path, "frontend", "Frontend")
    fake_solo = _make_fake_solo_cli(tmp_path)
    monkeypatch.setenv("SOLO_OS_SOLO_COMMAND", f"{sys.executable} {fake_solo}")
    registry = ProjectRegistry(str(tmp_path / "projects.json"))
    registry.add_solo_project(str(backend), project_id="backend")
    registry.add_solo_project(str(frontend), project_id="frontend")
    store = CrossTaskStore(str(tmp_path / "state"))
    orchestrator = CrossProjectOrchestrator(registry, store)

    created = orchestrator.dispatch(
        "Build billing feature",
        project_ids=["backend", "frontend"],
        dependencies={"frontend": ["backend"]},
    )

    assert created.status in {"in_progress", "blocked"}
    assert created.get_project_task("backend").solo_task_id == "TASK-backend"
    assert created.get_project_task("frontend").solo_task_id == ""
    assert created.get_project_task("frontend").status == "blocked"

    completed = orchestrator.run(created.id)

    assert completed.status == "completed"
    assert completed.get_project_task("backend").status == "completed"
    assert completed.get_project_task("frontend").status == "completed"
    assert completed.get_project_task("frontend").solo_task_id == "TASK-frontend"
    frontend_state = json.loads((frontend / ".fake_solo_state.json").read_text())
    assert "## Dependency Context" in frontend_state["title"]
    assert "TASK-backend" in frontend_state["title"]
    assert "api-contract.json" in frontend_state["title"]
    assert "backend" in completed.final_report
    assert (tmp_path / "state" / "cross_tasks.json").exists()


def test_cli_minimal_cross_project_loop(tmp_path):
    backend = _make_solo_project(tmp_path, "backend", "Backend")
    frontend = _make_solo_project(tmp_path, "frontend", "Frontend")
    fake_solo = _make_fake_solo_cli(tmp_path)
    env = dict(os.environ)
    env["SOLO_OS_SOLO_COMMAND"] = f"{sys.executable} {fake_solo}"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])

    _run_cli(tmp_path, env, "project", "add", str(backend), "--id", "backend")
    _run_cli(tmp_path, env, "project", "add", str(frontend), "--id", "frontend")
    dispatched = _run_cli(
        tmp_path,
        env,
        "dispatch",
        "Build billing feature",
        "--project",
        "backend",
        "--project",
        "frontend",
        "--depends",
        "frontend:backend",
        "--json",
    )
    payload = json.loads(dispatched.stdout)
    task_id = payload["cross_task"]["id"]

    completed = _run_cli(tmp_path, env, "run", "--task", task_id, "--until", "done", "--json")
    status = _run_cli(tmp_path, env, "status", "--json")

    completed_payload = json.loads(completed.stdout)
    status_payload = json.loads(status.stdout)
    assert completed_payload["cross_task"]["status"] == "completed"
    assert status_payload["cross_tasks"]["summary"]["completed_cross_tasks"] == 1


def test_cross_project_retry_and_reopen_bridge_to_child_solo(tmp_path, monkeypatch):
    backend = _make_solo_project(tmp_path, "backend", "Backend")
    fake_solo = _make_fake_solo_cli(tmp_path)
    monkeypatch.setenv("SOLO_OS_SOLO_COMMAND", f"{sys.executable} {fake_solo}")
    registry = ProjectRegistry(str(tmp_path / "projects.json"))
    registry.add_solo_project(str(backend), project_id="backend")
    store = CrossTaskStore(str(tmp_path / "state"))
    orchestrator = CrossProjectOrchestrator(registry, store)
    task = orchestrator.dispatch("Build risky backend", project_ids=["backend"])
    state_path = backend / ".fake_solo_state.json"
    state = json.loads(state_path.read_text())
    state["fail_next_run"] = True
    state_path.write_text(json.dumps(state))

    failed = orchestrator.run(task.id)

    assert failed.status == "failed"
    assert failed.get_project_task("backend").status == "failed"

    retried = orchestrator.retry("backend", task_id=task.id, phase="dev_pool")

    retry_state = json.loads(state_path.read_text())
    assert retried.status == "in_progress"
    assert retried.get_project_task("backend").status == "in_progress"
    assert retry_state["last_command"][:2] == ["retry", "--json"]
    assert "--phase" in retry_state["last_command"]
    assert "dev_pool" in retry_state["last_command"]

    reopened = orchestrator.reopen("backend", phase="qa", task_id=task.id)

    reopen_state = json.loads(state_path.read_text())
    assert reopened.status == "in_progress"
    assert reopened.get_project_task("backend").last_summary == "reopened phase qa"
    assert reopen_state["last_command"][:3] == ["reopen", "--phase", "qa"]


def _run_cli(tmp_path: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "projectos", *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def _make_solo_project(tmp_path: Path, project_id: str, name: str) -> Path:
    project = tmp_path / project_id
    solo = project / ".solo"
    solo.mkdir(parents=True)
    (solo / "config.yaml").write_text(
        "\n".join([
            "solo_protocol_version: 1",
            "project:",
            f"  name: {name}",
            f"  repo: https://example.com/{project_id}.git",
            "",
        ]),
        encoding="utf-8",
    )
    return project


def _make_fake_solo_cli(tmp_path: Path) -> Path:
    script = tmp_path / "fake_solo.py"
    script.write_text(
        """
import json
import pathlib
import sys

cwd = pathlib.Path.cwd()
state_path = cwd / ".fake_solo_state.json"
if state_path.exists():
    state = json.loads(state_path.read_text())
else:
    state = {}

command = sys.argv[1:]
project_id = cwd.name
task_id = state.get("task_id") or f"TASK-{project_id}"

if command and command[0] == "dispatch":
    state = {"task_id": task_id, "status": "in_progress", "title": command[-1]}
    state_path.write_text(json.dumps(state))
    print(json.dumps({"task": {"id": task_id, "status": "in_progress", "title": command[-1]}}))
elif command and command[0] == "run":
    if state.get("fail_next_run"):
        state["fail_next_run"] = False
        state["status"] = "failed"
        state_path.write_text(json.dumps(state))
        print(json.dumps({"stopped_reason": "failed", "failed_phase": "dev_pool", "task": {"id": task_id, "status": "failed"}}))
        sys.exit(0)
    state["task_id"] = task_id
    state["status"] = "completed"
    state_path.write_text(json.dumps(state))
    print(json.dumps({"stopped_reason": "done", "task": {"id": task_id, "status": "completed"}}))
elif command and command[0] == "retry":
    state["last_command"] = command
    state["status"] = "in_progress"
    state_path.write_text(json.dumps(state))
    print(json.dumps({"task": {"id": task_id, "status": "in_progress"}, "command": command}))
elif command and command[0] == "reopen":
    state["last_command"] = command
    state["status"] = "in_progress"
    state_path.write_text(json.dumps(state))
    print(json.dumps({"task": {"id": task_id, "status": "in_progress"}, "command": command}))
elif command[:2] == ["status", "--json"]:
    status = state.get("status", "pending")
    print(json.dumps({
        "protocol": {"compatible": True},
        "summary": {
            "total_tasks": 1 if state else 0,
            "active_tasks": 1 if status == "in_progress" else 0,
            "failed_tasks": 1 if status == "failed" else 0,
            "completed_tasks": 1 if status == "completed" else 0,
        },
        "tasks": [{"id": task_id, "status": status}] if state else [],
    }))
elif command[:2] == ["inspect", "--json"]:
    print(json.dumps({
        "task": {"id": task_id, "status": state.get("status", "pending"), "current_phase": ""},
        "dashboard": {"progress": {"completed_phases": 6, "total_phases": 6}},
        "artifacts": [
            {"kind": "agent_result", "relative_path": "final_report.md"},
            {"kind": "output", "relative_path": "api-contract.json"},
        ],
    }))
elif command[:2] == ["validate", "--json"]:
    print(json.dumps({"ok": True, "errors": [], "warnings": []}))
else:
    print(json.dumps({"ok": True, "command": command}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script
