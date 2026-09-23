"""Background Proactive Trigger Engine orchestrating continuous evaluation and anomaly detection."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import ProactiveTriggerModel
from packages.shared.nexus_shared.proactive.evaluator import TriggerEvaluator
from packages.shared.nexus_shared.proactive.models import (
    SystemMetricsSnapshot,
    TriggerEvaluationResult,
)
from packages.shared.nexus_shared.proactive.remediation import RemediationCoordinator
from packages.shared.nexus_shared.proactive.watcher import SystemWatcher, get_system_watcher

logger = get_logger("nexus.proactive.engine")


class ProactiveTriggerEngine:
    """Continuous background worker evaluating proactive conditions and orchestrating self-healing."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        watcher: SystemWatcher | None = None,
        evaluator: TriggerEvaluator | None = None,
        remediation_coordinator: RemediationCoordinator | None = None,
        poll_interval_sec: float = 5.0,
        event_broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._watcher = watcher or get_system_watcher()
        self._evaluator = evaluator or TriggerEvaluator()
        self._remediation = remediation_coordinator or RemediationCoordinator(
            event_broadcaster=event_broadcaster
        )
        self._poll_interval = poll_interval_sec
        self._broadcaster = event_broadcaster
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def set_session_factory(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = factory

    def set_event_broadcaster(
        self, broadcaster: Callable[[str, dict[str, Any]], Awaitable[None]]
    ) -> None:
        self._broadcaster = broadcaster
        self._remediation._broadcaster = broadcaster

    async def start(self) -> None:
        """Start the background monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="nexus_proactive_engine_loop")
        logger.info("proactive_engine_started", poll_interval=self._poll_interval)

    async def stop(self) -> None:
        """Stop the background monitoring loop with graceful cancellation."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("proactive_engine_stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                if self._session_factory:
                    async with self._session_factory() as session:
                        await self.evaluate_all(session)
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                logger.info("proactive_engine_cancelled")
                break
            except Exception as e:  # noqa: BLE001
                logger.error("proactive_engine_cycle_failed", error=str(e))
                await asyncio.sleep(self._poll_interval)

    async def evaluate_all(
        self,
        session: AsyncSession,
        metrics: SystemMetricsSnapshot | None = None,
    ) -> list[TriggerEvaluationResult]:
        """Evaluate all active proactive triggers against current metrics."""
        current_metrics = metrics or self._watcher.capture_metrics()

        stmt = select(ProactiveTriggerModel).where(ProactiveTriggerModel.is_active.is_(True))
        result = await session.execute(stmt)
        triggers = list(result.scalars().all())

        results: list[TriggerEvaluationResult] = []
        for trigger in triggers:
            is_triggered, reason, observed = self._evaluator.evaluate(
                trigger, metrics=current_metrics
            )
            if is_triggered:
                eval_res = await self._remediation.handle_evaluation_result(
                    session=session,
                    trigger=trigger,
                    reason=reason,
                    observed_data=observed,
                )
                results.append(eval_res)

        return results

    async def evaluate_single_trigger(
        self,
        session: AsyncSession,
        trigger_id: str,
        metrics: SystemMetricsSnapshot | None = None,
    ) -> TriggerEvaluationResult | None:
        """Evaluate a specific trigger on demand."""
        stmt = select(ProactiveTriggerModel).where(ProactiveTriggerModel.id == trigger_id)
        result = await session.execute(stmt)
        trigger = result.scalar_one_or_none()
        if not trigger:
            return None

        current_metrics = metrics or self._watcher.capture_metrics()
        is_triggered, reason, observed = self._evaluator.evaluate(trigger, metrics=current_metrics)

        if is_triggered:
            return await self._remediation.handle_evaluation_result(
                session=session,
                trigger=trigger,
                reason=reason,
                observed_data=observed,
            )

        return TriggerEvaluationResult(
            triggered=False,
            trigger_id=trigger.id,
            trigger_name=trigger.name,
            reason=reason,
            observed_data=observed,
            action_capability=trigger.action_capability,
            action_params=trigger.action_params,
            requires_approval=False,
            status="detected",
        )


_global_engine: ProactiveTriggerEngine | None = None


def get_proactive_engine() -> ProactiveTriggerEngine:
    global _global_engine
    if _global_engine is None:
        _global_engine = ProactiveTriggerEngine()
    return _global_engine
