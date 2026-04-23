"""Tests for projectos/core/dependency.py."""
import pytest
from projectos.core.dependency import DependencyManager, CycleError
from projectos.core.registry import ProjectRegistry
from projectos.core.models import Project


@pytest.fixture
def tmp_deps(tmp_path):
    db = tmp_path / "projects.json"
    reg = ProjectRegistry(str(db))
    return DependencyManager(reg), reg


class TestDependencyManager:
    def test_add_dependency(self, tmp_deps):
        dm, reg = tmp_deps
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path=""))
        dm.add_dependency("b", "a", {"endpoint": "/api"})
        assert "a" in dm.get_dependencies("b")

    def test_get_dependents(self, tmp_deps):
        dm, reg = tmp_deps
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path=""))
        dm.add_dependency("b", "a", {})
        assert "b" in dm.get_dependents("a")

    def test_build_order_linear(self, tmp_deps):
        dm, reg = tmp_deps
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path=""))
        reg.create(Project(id="c", name="C", repo_url="", local_path=""))
        dm.add_dependency("b", "a", {})
        dm.add_dependency("c", "b", {})
        order = dm.build_order()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_build_order_cycle_raises(self, tmp_deps):
        dm, reg = tmp_deps
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path=""))
        dm.add_dependency("b", "a", {})
        dm.add_dependency("a", "b", {})  # cycle!
        with pytest.raises(CycleError):
            dm.build_order()

    def test_is_ready(self, tmp_deps):
        dm, reg = tmp_deps
        reg.create(Project(id="a", name="A", repo_url="", local_path=""))
        reg.create(Project(id="b", name="B", repo_url="", local_path="", status="active"))
        dm.add_dependency("a", "b", {})
        assert dm.is_ready("a") is True

        reg.update("b", status="paused")
        assert dm.is_ready("a") is False
