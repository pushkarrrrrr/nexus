"""Standard Filesystem Tools for NEXUS."""

from typing import Any

from pydantic import BaseModel, Field

from packages.shared.nexus_shared.tools.base import BaseTool

# ---------------------------------------------------------------------------
# 1. filesystem.read
# ---------------------------------------------------------------------------


class FilesystemReadInput(BaseModel):
    path: str = Field(..., description="Absolute or relative file path to read")
    max_bytes: int | None = Field(
        default=1024 * 1024, description="Maximum bytes to read (default 1MB)"
    )


class FilesystemReadOutput(BaseModel):
    content: str
    path: str
    size_bytes: int


class FilesystemReadTool(BaseTool):
    name = "filesystem.read"
    description = "Read text content from a file on the host filesystem."
    input_schema = FilesystemReadInput
    output_schema = FilesystemReadOutput
    required_capability = "filesystem.read"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: FilesystemReadInput,
        context: dict[str, Any] | None = None,
    ) -> FilesystemReadOutput:
        content = await self.adapter.read_file(params.path, max_bytes=params.max_bytes)
        return FilesystemReadOutput(
            content=content,
            path=params.path,
            size_bytes=len(content.encode("utf-8")),
        )


# ---------------------------------------------------------------------------
# 2. filesystem.write
# ---------------------------------------------------------------------------


class FilesystemWriteInput(BaseModel):
    path: str = Field(..., description="Target file path to create or overwrite")
    content: str = Field(..., description="Text content to write to the file")


class FilesystemWriteOutput(BaseModel):
    status: str
    path: str
    bytes_written: int


class FilesystemWriteTool(BaseTool):
    name = "filesystem.write"
    description = "Create or overwrite a file with pre-execution snapshot capture."
    input_schema = FilesystemWriteInput
    output_schema = FilesystemWriteOutput
    required_capability = "filesystem.write"
    default_risk_level = "MEDIUM"
    timeout_seconds = 15.0
    is_reversible = True

    async def run(
        self,
        user_id: str,
        params: FilesystemWriteInput,
        context: dict[str, Any] | None = None,
    ) -> FilesystemWriteOutput:
        res = await self.adapter.write_file(params.path, params.content)
        return FilesystemWriteOutput(**res)


# ---------------------------------------------------------------------------
# 3. filesystem.move
# ---------------------------------------------------------------------------


class FilesystemMoveInput(BaseModel):
    source_path: str = Field(..., description="Source file path to move")
    dest_path: str = Field(..., description="Destination file path")


class FilesystemMoveOutput(BaseModel):
    status: str
    source: str
    destination: str


class FilesystemMoveTool(BaseTool):
    name = "filesystem.move"
    description = "Move or rename a file with pre-execution snapshot capture."
    input_schema = FilesystemMoveInput
    output_schema = FilesystemMoveOutput
    required_capability = "filesystem.write"
    default_risk_level = "MEDIUM"
    timeout_seconds = 15.0
    is_reversible = True

    async def run(
        self,
        user_id: str,
        params: FilesystemMoveInput,
        context: dict[str, Any] | None = None,
    ) -> FilesystemMoveOutput:
        res = await self.adapter.move_file(params.source_path, params.dest_path)
        return FilesystemMoveOutput(**res)


# ---------------------------------------------------------------------------
# 4. filesystem.delete
# ---------------------------------------------------------------------------


class FilesystemDeleteInput(BaseModel):
    path: str = Field(..., description="Target file or directory path to delete")


class FilesystemDeleteOutput(BaseModel):
    status: str
    deleted_path: str


class FilesystemDeleteTool(BaseTool):
    name = "filesystem.delete"
    description = "Delete a file with automatic pre-state backup snapshot."
    input_schema = FilesystemDeleteInput
    output_schema = FilesystemDeleteOutput
    required_capability = "filesystem.delete"
    default_risk_level = "HIGH"
    timeout_seconds = 15.0
    is_reversible = True

    async def run(
        self,
        user_id: str,
        params: FilesystemDeleteInput,
        context: dict[str, Any] | None = None,
    ) -> FilesystemDeleteOutput:
        res = await self.adapter.delete_file(params.path)
        return FilesystemDeleteOutput(**res)


# ---------------------------------------------------------------------------
# 5. filesystem.list_dir
# ---------------------------------------------------------------------------


class FilesystemListDirInput(BaseModel):
    path: str = Field(..., description="Directory path to inspect")


class FileItemMetadata(BaseModel):
    name: str
    path: str
    is_dir: bool
    size_bytes: int


class FilesystemListDirOutput(BaseModel):
    path: str
    items: list[FileItemMetadata]
    total: int


class FilesystemListDirTool(BaseTool):
    name = "filesystem.list_dir"
    description = "Safely list directory contents with file metadata."
    input_schema = FilesystemListDirInput
    output_schema = FilesystemListDirOutput
    required_capability = "filesystem.read"
    default_risk_level = "LOW"
    timeout_seconds = 10.0
    is_reversible = False

    async def run(
        self,
        user_id: str,
        params: FilesystemListDirInput,
        context: dict[str, Any] | None = None,
    ) -> FilesystemListDirOutput:
        items = await self.adapter.list_dir(params.path)
        parsed_items = [FileItemMetadata(**item) for item in items]
        return FilesystemListDirOutput(
            path=params.path,
            items=parsed_items,
            total=len(parsed_items),
        )
