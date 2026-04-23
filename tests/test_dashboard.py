"""Tests for projectos/core/dashboard.py."""
import pytest
from projectos.core.dashboard import Dashboard
from projectos.core.registry import ProjectRegistry
from projectos.core.scheduler import AgentScheduler
from projectos.core.models import Project


@pytest.fixture
def tmp_dashboard(tmp_path):
    db = tmp_path / "projects.json"
    reg = ProjectRegistry(str(db))
    sched = AgentScheduler(reg)
    return Dashboard(reg, sched)


class TestDashboard:
    def test_list_projects_empty(self, tmp_dashboard):
        out = tmp_dashboard.list_projects()
        assert "No projects" in out

    def test_list_projects_with_data(self, tmp_dashboard):
        reg = tmp_dashboard.registry
        reg.create(Project(id="p1", name="Project One", repo_url="", local_path=""))
        out = tmp_dashboard.list_projects()
        assert "p1" in out
        assert "Project One" in out

    def test_project_status_found(self, tmp_dashboard):
        reg = tmp_dashboard.registry
        reg.create(Project(id="p1", name="P1", repo_url="https://github.com/test", local_path="/tmp/p1"))
        out = tmp_dashboard.project_status("p1")
        assert "P1" in out
        assert "https://github.com/test" in out

    def test_project_status_not_found(self, tmp_dashboard):
        out = tmp_dashboard.project_status("xxx")
        assert "not found" in out

    def test_system_overview(self, tmp_dashboard):
        out = tmp_dashboard.system_overview()
        assert "ProjectOS Dashboard" in out

    def test_dependency_graph(self, tmp_dashboard):
        reg = tmp_dashboard.registry
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path="", dependencies=["a"]))
        out = tmp_dashboard.dependency_graph()
        assert "a" in out
        assert "b" in out
