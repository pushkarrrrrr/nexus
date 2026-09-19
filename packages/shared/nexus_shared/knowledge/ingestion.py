"""Document Ingestion & Semantic Chunking Engine.

Extracts text from multi-format files (PDF, Markdown, TXT, CSV, JSON)
and partitions text into semantically coherent, overlapping chunks with
precise source attribution (page numbers, character offsets).
"""

import csv
import io
import json
import re
from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class ParsedChunk:
    chunk_index: int
    content: str
    page_number: int | None
    char_start: int
    char_end: int


class DocumentIngestor:
    """Parses files and splits content into indexed chunks."""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def extract_and_chunk(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: str,
    ) -> list[ParsedChunk]:
        """Parse raw file bytes based on type and return a list of ParsedChunks."""
        ft = file_type.lower().strip().lstrip(".")

        if ft == "pdf":
            return self._parse_pdf(file_bytes)
        if ft in ("txt", "text", "log"):
            return self._parse_text(file_bytes.decode("utf-8", errors="replace"))
        if ft in ("md", "markdown"):
            return self._parse_markdown(file_bytes.decode("utf-8", errors="replace"))
        if ft == "csv":
            return self._parse_csv(file_bytes.decode("utf-8", errors="replace"))
        if ft == "json":
            return self._parse_json(file_bytes.decode("utf-8", errors="replace"))

        # Fallback to UTF-8 text interpretation
        return self._parse_text(file_bytes.decode("utf-8", errors="replace"))

    def _parse_pdf(self, file_bytes: bytes) -> list[ParsedChunk]:
        """Extract text from PDF page by page and chunk with page attribution."""
        reader = PdfReader(io.BytesIO(file_bytes))
        chunks: list[ParsedChunk] = []
        global_index = 0

        for page_idx, page in enumerate(reader.pages):
            page_number = page_idx + 1
            text = page.extract_text() or ""
            text = text.strip()
            if not text:
                continue

            page_chunks = self._chunk_text(text, page_number=page_number, start_index=global_index)
            chunks.extend(page_chunks)
            global_index += len(page_chunks)

        return chunks

    def _parse_markdown(self, content: str) -> list[ParsedChunk]:
        """Extract markdown content, preserving section headers in context."""
        return self._chunk_text(content, page_number=None)

    def _parse_text(self, content: str) -> list[ParsedChunk]:
        """Extract plain text and chunk with character boundary offsets."""
        return self._chunk_text(content, page_number=None)

    def _parse_csv(self, content: str) -> list[ParsedChunk]:
        """Convert CSV rows to structured natural text blocks before chunking."""
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return []

        header = rows[0]
        formatted_rows: list[str] = []
        for row in rows[1:]:
            pairs = [
                f"{header[i]}: {row[i]}"
                for i in range(min(len(header), len(row)))
                if row[i].strip()
            ]
            if pairs:
                formatted_rows.append("; ".join(pairs))

        combined = "\n".join(formatted_rows)
        return self._chunk_text(combined, page_number=None)

    def _parse_json(self, content: str) -> list[ParsedChunk]:
        """Format JSON documents into indented structural blocks for chunking."""
        try:
            parsed = json.loads(content)
            formatted = json.dumps(parsed, indent=2)
        except (json.JSONDecodeError, TypeError, ValueError):
            formatted = content
        return self._chunk_text(formatted, page_number=None)

    def _chunk_text(
        self,
        text: str,
        page_number: int | None = None,
        start_index: int = 0,
    ) -> list[ParsedChunk]:
        """Split text into overlapping chunks respecting sentence/paragraph boundaries."""
        chunks: list[ParsedChunk] = []
        if not text.strip():
            return chunks

        # Paragraph/sentence splitting regex
        paragraphs = re.split(r"(\n\n+)", text)
        current_chunk = ""
        current_start = 0
        global_char_offset = 0
        chunk_idx = start_index

        for piece in paragraphs:
            if not piece:
                continue

            if len(current_chunk) + len(piece) <= self.chunk_size:
                current_chunk += piece
            else:
                if current_chunk.strip():
                    char_end = current_start + len(current_chunk)
                    chunks.append(
                        ParsedChunk(
                            chunk_index=chunk_idx,
                            content=current_chunk.strip(),
                            page_number=page_number,
                            char_start=current_start,
                            char_end=char_end,
                        )
                    )
                    chunk_idx += 1

                    # Overlap handling
                    overlap_len = min(len(current_chunk), self.chunk_overlap)
                    overlap_text = current_chunk[-overlap_len:]
                    current_start = char_end - overlap_len
                    current_chunk = overlap_text + piece
                else:
                    # Single piece larger than chunk_size: slice hard
                    piece_offset = 0
                    while piece_offset < len(piece):
                        slice_text = piece[piece_offset : piece_offset + self.chunk_size]
                        chunks.append(
                            ParsedChunk(
                                chunk_index=chunk_idx,
                                content=slice_text.strip(),
                                page_number=page_number,
                                char_start=global_char_offset + piece_offset,
                                char_end=global_char_offset + piece_offset + len(slice_text),
                            )
                        )
                        chunk_idx += 1
                        piece_offset += self.chunk_size - self.chunk_overlap
                    current_chunk = ""
                    current_start = global_char_offset + len(piece)

            global_char_offset += len(piece)

        if current_chunk.strip():
            chunks.append(
                ParsedChunk(
                    chunk_index=chunk_idx,
                    content=current_chunk.strip(),
                    page_number=page_number,
                    char_start=current_start,
                    char_end=current_start + len(current_chunk),
                )
            )

        return chunks
