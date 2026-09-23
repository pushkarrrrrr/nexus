"""Trigger Evaluator checking conditions, thresholds, and cooldowns."""

import os
from datetime import UTC, datetime
from typing import Any

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import ProactiveTriggerModel
from packages.shared.nexus_shared.proactive.models import SystemMetricsSnapshot

logger = get_logger("nexus.proactive.evaluator")


class TriggerEvaluator:
    """Evaluates proactive conditions against host telemetry and system events."""

    def evaluate(
        self,
        trigger: ProactiveTriggerModel,
        metrics: SystemMetricsSnapshot | None = None,
        context_event: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> tuple[bool, str, dict[str, Any]]:
        """Evaluate if trigger conditions are met.

        Returns: (triggered, reason, observed_data)
        """
        if not trigger.is_active:
            return False, "Trigger is inactive", {}

        current_time = now or datetime.now(UTC)

        # 1. Cooldown Check
        if trigger.last_triggered_at is not None:
            last_dt = trigger.last_triggered_at
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            elapsed = (current_time - last_dt).total_seconds()
            if elapsed < trigger.cooldown_seconds:
                return (
                    False,
                    f"Cooldown active ({int(elapsed)}s < {trigger.cooldown_seconds}s)",
                    {"elapsed_seconds": elapsed, "cooldown_seconds": trigger.cooldown_seconds},
                )

        cond = trigger.condition or {}

        # 2. Type-specific evaluation
        if trigger.trigger_type == "threshold":
            if metrics is None:
                return False, "No system metrics provided for threshold evaluation", {}

            metric_name = cond.get("metric_name", "cpu_percent")
            operator = cond.get("operator", ">")
            threshold = float(cond.get("threshold_value", 80.0))

            current_val = getattr(metrics, metric_name, None)
            if current_val is None:
                return False, f"Unknown metric: {metric_name}", {}

            current_val_float = float(current_val)
            observed = {
                "metric_name": metric_name,
                "current_value": current_val_float,
                "threshold_value": threshold,
                "operator": operator,
            }

            triggered = self._compare(current_val_float, operator, threshold)
            if triggered:
                reason = (
                    f"Metric {metric_name} ({current_val_float}) {operator} threshold ({threshold})"
                )
                return True, reason, observed
            return (
                False,
                f"Metric {metric_name} ({current_val_float}) did not breach threshold ({threshold})",
                observed,
            )

        elif trigger.trigger_type == "file_watch":
            target_path = cond.get("target_path")
            if not target_path:
                return False, "Missing target_path in file_watch condition", {}

            expanded_path = os.path.expanduser(target_path)
            exists = os.path.exists(expanded_path)
            size = os.path.getsize(expanded_path) if exists else 0
            observed = {"target_path": target_path, "exists": exists, "size_bytes": size}

            expected_state = cond.get("expected_state", "exists")
            if expected_state == "exists" and exists:
                return True, f"Watched file exists: {target_path}", observed
            elif expected_state == "missing" and not exists:
                return True, f"Watched file is missing: {target_path}", observed
            elif expected_state == "size_exceeds":
                max_bytes = int(cond.get("max_size_bytes", 10 * 1024 * 1024))
                if size > max_bytes:
                    return True, f"File size {size} exceeds {max_bytes} bytes", observed

            return False, f"File condition '{expected_state}' not met for {target_path}", observed

        elif trigger.trigger_type == "task_failure":
            if not context_event:
                return False, "No task failure event provided", {}
            task_status = context_event.get("status")
            if task_status == "failed":
                return (
                    True,
                    f"Detected failed task: {context_event.get('task_id', 'unknown')}",
                    context_event,
                )
            return False, "Task is not in failed state", context_event

        elif trigger.trigger_type == "schedule":
            interval = int(cond.get("schedule_interval_sec", 300))
            if trigger.last_triggered_at is None:
                return (
                    True,
                    f"Initial schedule interval ({interval}s) reached",
                    {"interval": interval},
                )
            last_dt = trigger.last_triggered_at
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=UTC)
            elapsed = (current_time - last_dt).total_seconds()
            if elapsed >= interval:
                return (
                    True,
                    f"Schedule interval elapsed ({int(elapsed)}s >= {interval}s)",
                    {"elapsed": elapsed, "interval": interval},
                )
            return (
                False,
                f"Schedule interval not reached ({int(elapsed)}s < {interval}s)",
                {"elapsed": elapsed, "interval": interval},
            )

        elif trigger.trigger_type == "system_event":
            if context_event and context_event.get("event_type") == cond.get("event_type"):
                return True, f"Matched system event: {cond.get('event_type')}", context_event
            return False, "System event did not match", {}

        return False, f"Unsupported trigger type: {trigger.trigger_type}", {}

    @staticmethod
    def _compare(val: float, op: str, threshold: float) -> bool:
        if op == ">":
            return val > threshold
        if op == ">=":
            return val >= threshold
        if op == "<":
            return val < threshold
        if op == "<=":
            return val <= threshold
        if op == "==":
            return abs(val - threshold) < 1e-6
        if op == "!=":
            return abs(val - threshold) >= 1e-6
        return False
