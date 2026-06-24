"""Unit test for CeleryBuildDispatcher (deterministic task id, apply_async call)."""

from __future__ import annotations

import uuid

from app.services.celery_dispatcher import CeleryBuildDispatcher


def test_dispatch_uses_deterministic_task_id(monkeypatch) -> None:
    calls = {}

    def _fake_apply_async(*, args, task_id, queue):
        calls["args"], calls["task_id"], calls["queue"] = args, task_id, queue

    import app.tasks.build_tasks as bt
    monkeypatch.setattr(bt.run_build, "apply_async", _fake_apply_async)

    build_id = uuid.uuid4()
    task_id = CeleryBuildDispatcher().dispatch(build_id, queue="high")
    assert task_id == f"build:{build_id}"
    assert calls["args"] == [str(build_id)]
    assert calls["queue"] == "high"
