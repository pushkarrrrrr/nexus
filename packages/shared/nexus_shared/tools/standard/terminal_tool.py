"""Standard Terminal Execution Tool with security allowlist and buffer caps."""

import shlex
from typing import Any

from pydantic import BaseModel, Field

from packages.shared.nexus_shared.computer.base import is_protected_directory
from packages.shared.nexus_shared.policy.utils import normalize_resource_target
from packages.shared.nexus_shared.tools.base import BaseTool

# Binary execution allowlist for controlled commands
ALLOWED_BINARIES: frozenset[str] = frozenset(
    {
        "git",
        "pytest",
        "npm",
        "node",
        "npx",
        "python",
        "python3",
        "ls",
        "cat",
        "grep",
        "find",
        "echo",
        "pwd",
        "head",
        "tail",
        "wc",
        "diff",
        "which",
        "curl",
        "date",
        "uname",
    }
)

# Characters that indicate unescaped subshell command injection
DANGEROUS_SHELL_CHARS: tuple[str, ...] = (";", "|", "&", "`", "$", "(", ")", ">", "<", "\n")


class TerminalExecuteInput(BaseModel):
    command: list[str] | str = Field(
        ...,
        description="Command and arguments to execute as a list of strings or clean command line string",
    )
    cwd: str | None = Field(
        default=None,
        description="Working directory for the command. Must not target protected system directories.",
    )
    timeout_seconds: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Maximum execution timeout in seconds (default 30s, max 120s)",
    )


class TerminalExecuteOutput(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    cwd: str | None
    truncated: bool


class TerminalExecuteTool(BaseTool):
    name = "terminal.execute"
    description = (
        "Execute a controlled subprocess command with binary allowlist verification, "
        "strict timeouts, CWD protection, and buffer caps."
    )
    input_schema = TerminalExecuteInput
    output_schema = TerminalExecuteOutput
    required_capability = "terminal.execute"
    default_risk_level = "HIGH"
    timeout_seconds = 30.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: TerminalExecuteInput,
        context: dict[str, Any] | None = None,
    ) -> TerminalExecuteOutput:
        # Tokenize command if passed as string
        if isinstance(params.command, str):
            cmd_str = params.command.strip()
            # Reject raw subshell injection
            if any(ch in cmd_str for ch in DANGEROUS_SHELL_CHARS):
                raise ValueError(
                    f"Command contains unallowed shell operators or injection characters: '{cmd_str}'"
                )
            tokens = shlex.split(cmd_str)
        else:
            tokens = list(params.command)

        if not tokens:
            raise ValueError("Command token list cannot be empty.")

        binary_name = tokens[0].split("/")[-1].lower()

        # Binary Allowlist Verification
        is_allowed_binary = binary_name in ALLOWED_BINARIES or (
            binary_name.startswith("python3.") and binary_name[8:].replace(".", "").isdigit()
        )
        if not is_allowed_binary:
            raise PermissionError(
                f"Binary '{binary_name}' is not in the approved execution allowlist. "
                f"Allowed binaries: {', '.join(sorted(ALLOWED_BINARIES))}"
            )

        # Safeguard 1: Workspace / CWD Path Validation
        if params.cwd:
            normalized_cwd = normalize_resource_target(params.cwd)
            if is_protected_directory(normalized_cwd):
                raise PermissionError(
                    f"Execution denied: working directory '{normalized_cwd}' is a protected system directory."
                )

        # Execute via ComputerControlAdapter with Safeguard 2 (100 KB buffer cap)
        res = await self.adapter.run_command(
            command=tokens,
            timeout_seconds=params.timeout_seconds,
            cwd=params.cwd,
        )

        return TerminalExecuteOutput(**res)
