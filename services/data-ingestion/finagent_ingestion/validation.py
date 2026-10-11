"""Upload validation: type allow-list, size limits, content sniffing, malware-scan seam."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from finagent_core.errors import FileTooLargeError, UnsupportedFileTypeError, ValidationFailedError
from finagent_core.logging import get_logger

logger = get_logger(__name__)

#: extension → (canonical mime type, magic prefixes). Empty prefixes = text formats.
ALLOWED_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "pdf": ("application/pdf", (b"%PDF-",)),
    "csv": ("text/csv", ()),
    "txt": ("text/plain", ()),
    "md": ("text/markdown", ()),
    "docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        (b"PK\x03\x04",),
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        (b"PK\x03\x04",),
    ),
}

MAX_FILE_BYTES = 100 * 1024 * 1024
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ]+")


@dataclass(frozen=True)
class ScanVerdict:
    scanned: bool
    clean: bool
    scanner: str
    detail: str = ""


class MalwareScanner(Protocol):
    """Seam for a real scanner (ClamAV/vendor API) in enterprise deployments."""

    name: str

    def scan(self, payload: bytes, filename: str) -> ScanVerdict: ...


class UnscannedScanner:
    """Default no-op scanner that says so.

    Returning ``scanned=False`` is deliberate: documents surface a "not scanned for malware"
    warning rather than an unearned clean bill of health.
    """

    name = "none"

    def scan(self, payload: bytes, filename: str) -> ScanVerdict:
        return ScanVerdict(
            scanned=False,
            clean=True,
            scanner=self.name,
            detail="No malware scanner is configured; the file was not scanned.",
        )


class ExecutableContentScanner:
    """Built-in heuristic: reject files whose bytes look like an executable.

    Not a substitute for a real anti-malware engine; it exists so the default deployment
    still rejects the most obvious hostile uploads.
    """

    name = "builtin-heuristic"
    _SIGNATURES: tuple[tuple[bytes, str], ...] = (
        (b"MZ\x90\x00", "DOS/PE executable"),
        (b"\x7fELF", "ELF executable"),
        (b"\xca\xfe\xba\xbe", "Mach-O/Java class"),
        (b"#!/bin/sh", "shell script"),
        (b"#!/usr/bin/env", "interpreter script"),
    )

    def scan(self, payload: bytes, filename: str) -> ScanVerdict:
        head = payload[:64]
        for signature, label in self._SIGNATURES:
            if head.startswith(signature):
                return ScanVerdict(scanned=True, clean=False, scanner=self.name, detail=f"rejected: {label}")
        return ScanVerdict(scanned=True, clean=True, scanner=self.name, detail="no executable signature")


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    extension: str
    mime_type: str
    size_bytes: int
    sha256: str
    scan: ScanVerdict


def sanitize_filename(filename: str) -> str:
    base = (filename or "").replace("\\", "/").split("/")[-1].strip()
    cleaned = _SAFE_NAME_RE.sub("_", base)[:200]
    if not cleaned or cleaned in {".", ".."}:
        raise ValidationFailedError("filename is not usable")
    return cleaned


def validate_upload(
    payload: bytes,
    filename: str,
    *,
    max_bytes: int = MAX_FILE_BYTES,
    scanner: MalwareScanner | None = None,
) -> ValidatedUpload:
    """Validate an uploaded file before anything touches its contents."""
    safe_name = sanitize_filename(filename)
    if not payload:
        raise ValidationFailedError("uploaded file is empty")
    if len(payload) > max_bytes:
        raise FileTooLargeError(
            f"file is {len(payload)} bytes, limit is {max_bytes}",
            details={"size_bytes": len(payload), "max_bytes": max_bytes},
        )

    extension = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if extension not in ALLOWED_TYPES:
        raise UnsupportedFileTypeError(
            f"unsupported extension: {extension or '(none)'}",
            details={"allowed": sorted(ALLOWED_TYPES)},
        )

    mime_type, magic_prefixes = ALLOWED_TYPES[extension]
    if magic_prefixes and not any(payload.startswith(prefix) for prefix in magic_prefixes):
        raise ValidationFailedError(
            "file contents do not match its extension", details={"extension": extension}
        )
    if not magic_prefixes and b"\x00" in payload[:4096]:
        # Text formats: reject binary payloads masquerading as text.
        raise ValidationFailedError("text file contains binary data", details={"extension": extension})

    verdict = (scanner or ExecutableContentScanner()).scan(payload, safe_name)
    if verdict.scanned and not verdict.clean:
        raise ValidationFailedError(
            f"file rejected by scanner: {verdict.detail}", details={"scanner": verdict.scanner}
        )

    return ValidatedUpload(
        filename=safe_name,
        extension=extension,
        mime_type=mime_type,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        scan=verdict,
    )
