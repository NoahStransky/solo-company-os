"""Adapter for registered projects that expose the .solo protocol."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class SoloCommandError(RuntimeError):
    """Raised when a solo CLI command fails."""

    def __init__(self, command: List[str], cwd: Path, returncode: int, stdout: str, stderr: str):
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"solo command failed ({returncode}): {' '.join(command)}")


def default_solo_command() -> List[str]:
    """Return the command used to call the solo CLI."""
    configured = os.environ.get("SOLO_OS_SOLO_COMMAND", "").strip()
    if configured:
        return shlex.split(configured)
    if shutil.which("solo"):
        return ["solo"]
    return [sys.executable, "-m", "solo"]


class SoloProjectAdapter:
    """Read a single initialized solo project through files and public CLI JSON."""

    def __init__(self, path: str | Path, solo_command: Optional[List[str]] = None):
        self.path = Path(path).expanduser().resolve()
        self.solo_dir = self.path / ".solo"
        self.config_path = self.solo_dir / "config.yaml"
        self.solo_command = solo_command or default_solo_command()

    def is_initialized(self) -> bool:
        return self.config_path.exists()

    def metadata(self) -> Dict[str, Any]:
        """Return lightweight project metadata from .solo/config.yaml."""
        if not self.is_initialized():
            raise FileNotFoundError(f"No .solo project found at {self.path}")
        config = _load_minimal_yaml(self.config_path)
        project = config.get("project") if isinstance(config.get("project"), dict) else {}
        return {
            "name": str(project.get("name") or self.path.name),
            "description": str(project.get("description") or ""),
            "repo": str(project.get("repo") or ""),
            "protocol_version": int(config.get("solo_protocol_version") or 0),
        }

    def status(self, include_all: bool = True) -> Dict[str, Any]:
        args = ["status", "--json"]
        if include_all:
            args.append("--all")
        return self._run_json(args)

    def inspect(self, task_id: str = "") -> Dict[str, Any]:
        args = ["inspect", "--json"]
        if task_id:
            args.extend(["--task", task_id])
        return self._run_json(args)

    def validate(self) -> Dict[str, Any]:
        return self._run_json(["validate", "--json"], allow_failure=True)

    def migrate_check(self) -> Dict[str, Any]:
        return self._run_json(["migrate", "--check", "--json"], allow_failure=True)

    def dispatch(self, task: str, role: str = "", workflow: str = "") -> Dict[str, Any]:
        args = ["dispatch", "--json"]
        if role:
            args.extend(["--to", role])
        if workflow:
            args.extend(["--workflow", workflow])
        args.append(task)
        return self._run_json(args)

    def run(self, until: str = "done", task_id: str = "") -> Dict[str, Any]:
        args = ["run", "--until", until, "--json"]
        if task_id:
            args.extend(["--task", task_id])
        return self._run_json(args)

    def retry(self, task_id: str, phase: str = "", agent: str = "") -> Dict[str, Any]:
        args = ["retry", "--json"]
        if task_id:
            args.extend(["--task", task_id])
        if phase:
            args.extend(["--phase", phase])
        if agent:
            args.extend(["--agent", agent])
        return self._run_json(args)

    def reopen(self, task_id: str, phase: str) -> Dict[str, Any]:
        args = ["reopen", "--phase", phase, "--json"]
        if task_id:
            args.extend(["--task", task_id])
        return self._run_json(args)

    def _run_json(self, args: List[str], allow_failure: bool = False) -> Dict[str, Any]:
        command = [*self.solo_command, *args]
        completed = subprocess.run(
            command,
            cwd=self.path,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0 and not allow_failure:
            raise SoloCommandError(command, self.path, completed.returncode, completed.stdout, completed.stderr)
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise SoloCommandError(command, self.path, completed.returncode, completed.stdout, completed.stderr) from exc
        if completed.returncode != 0:
            payload.setdefault("ok", False)
            payload.setdefault("command_error", completed.stderr.strip() or completed.stdout.strip())
        return payload


def _load_minimal_yaml(path: Path) -> Dict[str, Any]:
    """Load simple YAML without making PyYAML a hard runtime dependency."""
    try:
        import yaml  # type: ignore
    except ImportError:
        return _load_project_config_fallback(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _load_project_config_fallback(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current_section = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, value = raw_line.split(":", 1)
            key = key.strip()
            value = value.strip().strip('"')
            if value:
                data[key] = _coerce_scalar(value)
                current_section = ""
            else:
                data[key] = {}
                current_section = key
            continue
        if current_section and raw_line.startswith("  ") and ":" in raw_line:
            key, value = raw_line.strip().split(":", 1)
            section = data.setdefault(current_section, {})
            if isinstance(section, dict):
                section[key.strip()] = value.strip().strip('"')
    return data


def _coerce_scalar(value: str) -> Any:
    try:
        return int(value)
    except ValueError:
        return value
