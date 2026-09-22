"""NEXUS Action Reversal Engine & Snapshot Manager.

Provides pre-execution state capture, unified diff generation,
side-effect journaling, undo/revert mechanics, and filesystem safeguards.
"""

import difflib
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.shared.nexus_shared.errors import StateConflictError
from packages.shared.nexus_shared.logging import get_logger
from packages.shared.nexus_shared.models import ActionSnapshotModel, AuditLogModel
from packages.shared.nexus_shared.policy.utils import normalize_resource_target

logger = get_logger("nexus.reversal.manager")

# Maximum inline text content size (1MB) to prevent database bloat
MAX_INLINE_SIZE = 1024 * 1024


def compute_sha256(content: str | bytes) -> str:
    """Compute hex SHA-256 hash of text or bytes."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


def is_binary_bytes(data: bytes) -> bool:
    """Detect binary data containing null bytes or failing UTF-8 decode."""
    if b"\x00" in data:
        return True
    try:
        data.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


class SnapshotManager:
    """Manages pre-execution snapshots, unified diffs, and reversible state rollbacks."""

    @staticmethod
    def classify_action(
        capability_name: str,
        action_type: str | dict[str, Any] | None = None,
        target_path: str | None = None,
    ) -> tuple[str, bool]:
        """Classify action type and explicit reversibility."""
        if isinstance(action_type, dict):
            params = action_type
            action_type = None
            if not target_path:
                target_path = params.get("path") or params.get("file_path") or params.get("target")

        if action_type:
            atype = str(action_type).upper()
            if atype in ("FILE_CREATE", "FILE_MODIFY", "FILE_DELETE", "FILE_MOVE"):
                return atype, True
            if atype in ("COMMAND_EXECUTE", "EXTERNAL_MUTATION", "EXTERNAL_ACTION"):
                return atype, False

        cap = capability_name.lower()
        if cap in ("filesystem.write",):
            if target_path and Path(normalize_resource_target(str(target_path))).exists():
                return "FILE_MODIFY", True
            return "FILE_CREATE", True
        if cap in ("filesystem.modify",):
            return "FILE_MODIFY", True
        if cap in ("filesystem.delete",):
            return "FILE_DELETE", True
        if cap in ("terminal.execute",):
            return "COMMAND_EXECUTE", False
        if cap in (
            "browser.open",
            "browser.interact",
            "browser.navigate",
            "network.request",
            "system.configure",
        ):
            return "EXTERNAL_MUTATION", False

        return "COMMAND_EXECUTE", False

    @staticmethod
    def count_diff_lines(diff_patch: str) -> tuple[int, int]:
        """Count added and removed lines from unified diff patch."""
        added = sum(
            1
            for line in diff_patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        removed = sum(
            1
            for line in diff_patch.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )
        return added, removed

    @staticmethod
    def generate_diff(before_content: str, after_content: str, filename: str = "file.txt") -> str:
        """Generate unified git-style diff representation."""
        before_lines = before_content.splitlines(keepends=True)
        after_lines = after_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )
        return "".join(diff)

    @staticmethod
    def capture_pre_state(target_path: str, action_type: str = "FILE_MODIFY") -> dict[str, Any]:
        """Safeguard: Capture file before-state respecting 1MB limit and binary files."""
        normalized = normalize_resource_target(target_path)
        path = Path(normalized)

        if not path.exists():
            return {
                "exists": False,
                "target_path": normalized,
                "sha256": None,
                "content": None,
                "size_bytes": 0,
                "is_binary": False,
                "is_oversized": False,
                "oversized": False,
            }

        try:
            raw_bytes = path.read_bytes()
            size = len(raw_bytes)
            file_hash = hashlib.sha256(raw_bytes).hexdigest()

            # Safeguard 2: Oversized & Binary handling
            if size > MAX_INLINE_SIZE:
                return {
                    "exists": True,
                    "target_path": normalized,
                    "sha256": file_hash,
                    "oversized": True,
                    "is_oversized": True,
                    "is_binary": False,
                    "size_bytes": size,
                    "content": None,
                    "notice": "Binary or oversized file diff omitted",
                }

            if is_binary_bytes(raw_bytes):
                return {
                    "exists": True,
                    "target_path": normalized,
                    "sha256": file_hash,
                    "is_binary": True,
                    "oversized": False,
                    "is_oversized": False,
                    "size_bytes": size,
                    "content": None,
                    "notice": "Binary or oversized file diff omitted",
                }

            text = raw_bytes.decode("utf-8")
            return {
                "exists": True,
                "target_path": normalized,
                "sha256": file_hash,
                "content": text,
                "size_bytes": size,
                "is_binary": False,
                "is_oversized": False,
                "oversized": False,
            }
        except (OSError, RuntimeError) as e:
            logger.warning("failed_to_capture_pre_state", path=normalized, error=str(e))
            return {
                "exists": True,
                "target_path": normalized,
                "sha256": None,
                "content": None,
                "error": str(e),
                "is_binary": False,
                "is_oversized": False,
                "oversized": False,
            }

    @classmethod
    async def create_snapshot(
        cls,
        db: AsyncSession | None = None,
        user_id: str = "",
        capability_name: str = "",
        target_path: str | None = None,
        action_type: str | None = None,
        proposed_content: str | None = None,
        task_id: str | None = None,
        step_id: str | None = None,
        auto_apply: bool = False,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        diff_patch: str | None = None,
        is_reversible: bool | None = None,
        status: str | None = None,
        session: AsyncSession | None = None,
    ) -> ActionSnapshotModel:
        """Create a new action snapshot before executing mutation."""
        effective_db = db or session
        if effective_db is None:
            raise ValueError("An active AsyncSession (db or session) is required.")

        now = datetime.now(UTC)
        normalized_path = normalize_resource_target(target_path) if target_path else None
        effective_action, auto_reversible = cls.classify_action(
            capability_name, action_type, target_path=normalized_path
        )
        effective_reversibility = is_reversible if is_reversible is not None else auto_reversible

        filename = Path(normalized_path).name if normalized_path else "target"

        if (
            before_state is None
            and normalized_path
            and effective_action
            in (
                "FILE_CREATE",
                "FILE_MODIFY",
                "FILE_DELETE",
                "FILE_MOVE",
            )
        ):
            before_state = cls.capture_pre_state(normalized_path, effective_action)

            # Build proposed after-state
            if after_state is None and proposed_content is not None:
                content_bytes = proposed_content.encode("utf-8")
                after_size = len(content_bytes)
                after_hash = hashlib.sha256(content_bytes).hexdigest()

                if after_size > MAX_INLINE_SIZE:
                    after_state = {
                        "exists": True,
                        "sha256": after_hash,
                        "oversized": True,
                        "is_oversized": True,
                        "size_bytes": after_size,
                        "notice": "Binary or oversized file diff omitted",
                    }
                    diff_patch = f"--- a/{filename}\n+++ b/{filename}\n@@ [Binary or oversized file diff omitted] @@\n"
                else:
                    after_state = {
                        "exists": True,
                        "sha256": after_hash,
                        "content": proposed_content,
                        "size_bytes": after_size,
                    }
                    before_text = before_state.get("content", "") or ""
                    diff_patch = cls.generate_diff(before_text, proposed_content, filename)
            elif after_state is None and effective_action == "FILE_DELETE":
                after_state = {"exists": False, "sha256": None, "content": "", "size_bytes": 0}
                before_text = before_state.get("content", "") or ""
                diff_patch = cls.generate_diff(before_text, "", filename)

        if status is None:
            status = "APPLIED" if auto_apply else "CAPTURED"

        snapshot = ActionSnapshotModel(
            user_id=user_id,
            task_id=task_id,
            step_id=step_id,
            capability_name=capability_name,
            action_type=effective_action,
            is_reversible=effective_reversibility,
            target_path=normalized_path,
            before_state=before_state,
            after_state=after_state,
            diff_patch=diff_patch,
            status=status,
            created_at=now,
        )
        effective_db.add(snapshot)
        await effective_db.commit()
        await effective_db.refresh(snapshot)
        return snapshot

    @classmethod
    async def revert_action(
        cls,
        db: AsyncSession | None = None,
        snapshot_id: str = "",
        user_id: str = "",
        force: bool = False,
        ip_address: str | None = None,
        session: AsyncSession | None = None,
    ) -> ActionSnapshotModel:
        """Safeguard: Revert an applied reversible mutation with drift detection."""
        effective_db = db or session
        if effective_db is None:
            raise ValueError("An active AsyncSession (db or session) is required.")

        now = datetime.now(UTC)

        stmt = select(ActionSnapshotModel).where(
            ActionSnapshotModel.id == snapshot_id,
            ActionSnapshotModel.user_id == user_id,
        )
        res = await effective_db.execute(stmt)
        snapshot = res.scalar_one_or_none()

        if snapshot is None:
            raise ValueError(f"Action snapshot '{snapshot_id}' not found.")

        # Reversibility verification
        if not snapshot.is_reversible:
            raise ValueError(
                f"Action '{snapshot.action_type}' is non-reversible and cannot be reverted."
            )

        if snapshot.status == "REVERTED":
            raise ValueError(f"Action snapshot '{snapshot_id}' is already reverted.")

        if snapshot.status not in ("APPLIED", "CAPTURED"):
            raise ValueError(
                f"Cannot revert action snapshot '{snapshot_id}' with status '{snapshot.status}'."
            )

        target_path_str = snapshot.target_path
        if not target_path_str:
            raise ValueError(
                f"Snapshot '{snapshot_id}' has no target path for filesystem rollback."
            )

        path = Path(target_path_str)

        # Safeguard 1: State Drift Detection
        if path.exists() and snapshot.after_state and snapshot.after_state.get("sha256"):
            current_bytes = path.read_bytes()
            current_hash = hashlib.sha256(current_bytes).hexdigest()
            expected_hash = str(snapshot.after_state.get("sha256") or "")

            if current_hash != expected_hash and not force:
                raise StateConflictError(
                    f"State drift detected on '{target_path_str}': current hash ({current_hash[:8]}) "
                    f"does not match expected applied hash ({expected_hash[:8]}). "
                    f"Pass force=True to override and revert."
                )

        # Execute Filesystem Reversal
        atype = snapshot.action_type
        before_state = snapshot.before_state or {}

        if atype == "FILE_CREATE":
            # Action created the file; rollback deletes it
            if path.exists():
                path.unlink()
        elif atype in ("FILE_MODIFY", "FILE_DELETE", "FILE_MOVE"):
            # Action modified or deleted file; rollback restores original content
            # Safeguard 3: Safe Directory Hierarchy Recreation
            path.parent.mkdir(parents=True, exist_ok=True)
            original_content = before_state.get("content", "")
            path.write_text(original_content, encoding="utf-8")

        # Update snapshot status
        snapshot.status = "REVERTED"
        snapshot.reverted_at = now

        # Append-Only Audit Logging
        audit_entry = AuditLogModel(
            user_id=user_id,
            session_id="reversal_session",
            agent_name="user",
            tool_name=snapshot.capability_name,
            action_type="MODIFY",
            risk_level="MEDIUM",
            event_type="ACTION_REVERTED",
            capability_name=snapshot.capability_name,
            status="SUCCESS",
            policy_verdict="REVERTED",
            details={
                "snapshot_id": snapshot.id,
                "action_type": snapshot.action_type,
                "target_path": target_path_str,
                "force": force,
                "reverted_at": now.isoformat(),
            },
            ip_address=ip_address,
            duration_ms=1.0,
            created_at=now,
            timestamp=now,
        )
        effective_db.add(audit_entry)
        await effective_db.commit()
        await effective_db.refresh(snapshot)
        return snapshot
