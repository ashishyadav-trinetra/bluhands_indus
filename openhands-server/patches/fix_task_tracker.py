"""Monkey-patches for qwen3.6-35b-a3b compatibility with OpenHands tools.

Two issues:
1. TaskItem.title is required but qwen omits it — auto-fill from notes.
2. security_risk field is required by some tool schemas but qwen omits it.

Loaded via sitecustomize.py at interpreter startup.
"""


def _apply_task_tracker_patches():
    try:
        from openhands.tools.task_tracker.definition import TaskItem

        _orig_validate = TaskItem.model_validate

        @classmethod
        def _patched_validate(cls, obj, **kwargs):
            if isinstance(obj, dict) and not obj.get("title"):
                notes = obj.get("notes", "")
                obj = dict(obj)
                obj["title"] = (
                    notes.split("\n")[0][:80] if notes else "Untitled task"
                )
            return _orig_validate.__func__(cls, obj, **kwargs)

        TaskItem.model_validate = _patched_validate.__func__
    except Exception:
        pass


def _apply_security_risk_patches():
    try:
        from openhands.sdk.agent.agent import Agent
        from openhands.sdk.security import risk

        _orig_extract = Agent._extract_security_risk

        def _patched_extract(self, arguments, tool_name, read_only_tool, security_analyzer=None):
            raw = arguments.pop("security_risk", None)
            if read_only_tool or raw is None or security_analyzer is None:
                return risk.SecurityRisk.UNKNOWN
            return risk.SecurityRisk(raw)

        Agent._extract_security_risk = _patched_extract
    except Exception:
        pass


_apply_task_tracker_patches()
_apply_security_risk_patches()
