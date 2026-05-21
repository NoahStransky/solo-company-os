"""Tests for .solo project integration."""
import json
import sys
from pathlib import Path

from projectos.core.dashboard import Dashboard
from projectos.core.registry import ProjectRegistry
from projectos.core.scheduler import AgentScheduler
from projectos.core.solo_adapter import SoloProjectAdapter


def test_solo_adapter_reads_metadata_without_cli(tmp_path):
    project = _make_solo_project(tmp_path)

    metadata = SoloProjectAdapter(project).metadata()

    assert metadata["name"] == "Linked Solo"
    assert metadata["repo"] == "https://example.com/linked.git"
    assert metadata["protocol_version"] == 1


def test_registry_can_add_initialized_solo_project(tmp_path):
    project = _make_solo_project(tmp_path)
    registry = ProjectRegistry(str(tmp_path / "projects.json"))

    pid = registry.add_solo_project(str(project))

    registered = registry.get(pid)
    assert pid == "linked-solo"
    assert registered is not None
    assert registered.kind == "solo"
    assert registered.local_path == str(project.resolve())
    assert registered.protocol_version == 1
    assert registered.metadata["solo_dir"].endswith(".solo")


def test_dashboard_status_reads_solo_status_json(tmp_path, monkeypatch):
    project = _make_solo_project(tmp_path)
    fake_solo = _make_fake_solo_cli(tmp_path)
    monkeypatch.setenv("SOLO_OS_SOLO_COMMAND", f"{sys.executable} {fake_solo}")
    registry = ProjectRegistry(str(tmp_path / "projects.json"))
    pid = registry.add_solo_project(str(project))
    dashboard = Dashboard(registry, AgentScheduler(registry))

    payload = dashboard.project_status_payload(pid)
    text = dashboard.project_status(pid)

    assert payload["ok"] is True
    assert payload["health"] == "healthy"
    assert payload["solo_status"]["summary"]["active_tasks"] == 1
    assert "Tasks: 2 total, 1 active, 0 failed" in text


def _make_solo_project(tmp_path: Path) -> Path:
    project = tmp_path / "linked"
    solo = project / ".solo"
    solo.mkdir(parents=True)
    (solo / "config.yaml").write_text(
        "\n".join([
            "solo_protocol_version: 1",
            "project:",
            "  name: Linked Solo",
            "  description: A linked solo project",
            "  repo: https://example.com/linked.git",
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
import sys

command = sys.argv[1:]
if command[:2] == ["status", "--json"]:
    print(json.dumps({
        "project": {"name": "Linked Solo"},
        "protocol": {"compatible": True},
        "summary": {
            "total_tasks": 2,
            "active_tasks": 1,
            "failed_tasks": 0,
            "completed_tasks": 1,
            "last_updated": "2026-05-20T00:00:00+00:00"
        },
        "dashboard": {"tasks": []},
        "tasks": []
    }))
elif command[:2] == ["validate", "--json"]:
    print(json.dumps({"ok": True, "errors": [], "warnings": []}))
elif command[:2] == ["inspect", "--json"]:
    print(json.dumps({"project": {"name": "Linked Solo"}, "task": {}, "dashboard": {}}))
else:
    print(json.dumps({"ok": True, "command": command}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script
