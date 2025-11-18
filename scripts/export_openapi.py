"""Export the FastAPI application's OpenAPI schema to docs/openapi.json."""

from __future__ import annotations

from importlib.machinery import ModuleSpec
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from fastapi import FastAPI


def _install_optional_dependency_stubs() -> None:
  """Register lightweight stubs for heavy optional dependencies.

  The FastAPI application imports the training services during start-up. Those
  services depend on heavyweight scientific libraries such as PyTorch and
  Stable-Baselines3 which are not required to build the OpenAPI schema. To
  avoid installing them in the documentation build environment, we provide
  minimal stub modules that satisfy the type checks performed at import time.
  """

  if "torch" not in sys.modules:  # pragma: no cover - documentation helper
    torch_stub = ModuleType("torch")
    torch_stub.__spec__ = ModuleSpec("torch", loader=None)
    sys.modules["torch"] = torch_stub

  if "gymnasium" not in sys.modules:  # pragma: no cover - documentation helper
    gym_stub = ModuleType("gymnasium")
    gym_stub.__spec__ = ModuleSpec("gymnasium", loader=None)

    class _Env:  # pylint: disable=too-few-public-methods
      """Minimal stand-in for ``gymnasium.Env``."""

    gym_stub.Env = _Env  # type: ignore[attr-defined]
    gym_stub.spaces = ModuleType("gymnasium.spaces")  # type: ignore[attr-defined]
    sys.modules["gymnasium"] = gym_stub
    sys.modules.setdefault("gym", gym_stub)

  if "stable_baselines3" not in sys.modules:  # pragma: no cover - documentation helper
    sb3_stub = ModuleType("stable_baselines3")
    sb3_stub.__spec__ = ModuleSpec("stable_baselines3", loader=None)

    class _PPO:  # pylint: disable=too-few-public-methods
      def __init__(self, *args, **kwargs) -> None:
        """Accept any arguments as a placeholder implementation."""

    sb3_stub.PPO = _PPO  # type: ignore[attr-defined]

    callbacks_module = ModuleType("stable_baselines3.common.callbacks")
    callbacks_module.__spec__ = ModuleSpec("stable_baselines3.common.callbacks", loader=None)

    class _BaseCallback:  # pylint: disable=too-few-public-methods
      pass

    class _CallbackList(list):
      pass

    callbacks_module.BaseCallback = _BaseCallback  # type: ignore[attr-defined]
    callbacks_module.CallbackList = _CallbackList  # type: ignore[attr-defined]

    vec_env_module = ModuleType("stable_baselines3.common.vec_env")
    vec_env_module.__spec__ = ModuleSpec("stable_baselines3.common.vec_env", loader=None)

    class _DummyVecEnv(list):
      pass

    vec_env_module.DummyVecEnv = _DummyVecEnv  # type: ignore[attr-defined]

    sys.modules["stable_baselines3"] = sb3_stub
    common_module = ModuleType("stable_baselines3.common")
    common_module.__spec__ = ModuleSpec("stable_baselines3.common", loader=None)
    sys.modules["stable_baselines3.common"] = common_module
    sys.modules["stable_baselines3.common.callbacks"] = callbacks_module
    sys.modules["stable_baselines3.common.vec_env"] = vec_env_module

  if "app.tasks.training_tasks" not in sys.modules:
    training_tasks_stub = ModuleType("app.tasks.training_tasks")
    training_tasks_stub.__spec__ = ModuleSpec("app.tasks.training_tasks", loader=None)

    class _StubAsyncResult(SimpleNamespace):
      def revoke(self, *args, **kwargs) -> None:
        """Perform no action when revoking tasks in documentation builds."""

    class _StubTask:
      def delay(self, *args, **kwargs) -> _StubAsyncResult:
        """Return a stub async result for documentation builds."""
        return _StubAsyncResult(id="stub-task")

    training_tasks_stub.run_ppo_training_task = _StubTask()  # type: ignore[attr-defined]
    training_tasks_stub.run_a3c_training_task = _StubTask()  # type: ignore[attr-defined]
    training_tasks_stub.stop_training_task = _StubTask()  # type: ignore[attr-defined]
    training_tasks_stub.celery_app = SimpleNamespace(control=SimpleNamespace())
    sys.modules["app.tasks.training_tasks"] = training_tasks_stub

    import importlib  # local import to avoid polluting module namespace

    tasks_pkg = importlib.import_module("app.tasks")
    tasks_pkg.training_tasks = training_tasks_stub


_install_optional_dependency_stubs()

# ruff: noqa: E402
# Delayed import until after dependency stubs are installed
from app.main import app as fastapi_app


def export_openapi(app: FastAPI, output_path: Path) -> None:
  """Generate the OpenAPI schema for *app* and write it to *output_path*.

  The schema is serialized with UTF-8 encoding and pretty-printed so it can
  be reviewed in version control.
  """
  schema = app.openapi()
  output_path.parent.mkdir(parents=True, exist_ok=True)
  output_path.write_text(
    json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )


def main() -> None:
  project_root = Path(__file__).resolve().parents[1]
  docs_dir = project_root / "docs"
  export_openapi(fastapi_app, docs_dir / "openapi.json")


if __name__ == "__main__":
  main()
