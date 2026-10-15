"""Self-Correction, Dynamic Replanning & Error Recovery module."""

from packages.shared.nexus_shared.agents.recovery.classifier import ErrorClassifier
from packages.shared.nexus_shared.agents.recovery.coordinator import SelfCorrectionCoordinator
from packages.shared.nexus_shared.agents.recovery.dag_patcher import DAGPatcher
from packages.shared.nexus_shared.agents.recovery.reflector import SelfCorrectionReflector
from packages.shared.nexus_shared.agents.recovery.schemas import (
    ErrorCategory,
    ProposedRecoveryStep,
    RecoveryStrategy,
    ReplanRecordResponse,
    SelfCorrectionProposal,
)

_global_coordinator: SelfCorrectionCoordinator | None = None


def get_recovery_coordinator() -> SelfCorrectionCoordinator:
    """Return the singleton instance of SelfCorrectionCoordinator."""
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = SelfCorrectionCoordinator()
    return _global_coordinator


__all__ = [
    "DAGPatcher",
    "ErrorCategory",
    "ErrorClassifier",
    "ProposedRecoveryStep",
    "RecoveryStrategy",
    "ReplanRecordResponse",
    "SelfCorrectionCoordinator",
    "SelfCorrectionProposal",
    "SelfCorrectionReflector",
    "get_recovery_coordinator",
]
