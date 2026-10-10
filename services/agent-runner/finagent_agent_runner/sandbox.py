"""Sandboxed Python execution.

Agent-submitted code never runs inside the API process. It runs in a short-lived child
interpreter with CPU, memory, file-size and process rlimits, no network (socket primitives
are replaced before user code runs), an import allow-list enforced through the sandbox
namespace's builtins, a static AST pre-scan, a temporary working directory, a scrubbed
environment and a wall-clock timeout with process-group kill.

**Documented limitation:** this is OS-process isolation, not kernel-level isolation. A
CPython escape could still read files the service user can read. The production target is a
dedicated container/gVisor sandbox worker; this interface is unchanged when that lands (see
``docs/SECURITY.md``).
"""

from __future__ import annotations

import ast
import json
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from finagent_core.errors import SandboxDeniedError, SandboxTimeoutError
from finagent_core.logging import get_logger

logger = get_logger(__name__)

#: Modules an analyst legitimately needs for quantitative work.
ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "math", "statistics", "decimal", "fractions", "json", "datetime", "random", "itertools",
        "functools", "collections", "re", "typing", "dataclasses", "numbers", "operator",
        "string", "textwrap", "numpy", "pandas",
    }
)

#: Names that may never appear in submitted code.
FORBIDDEN_NAMES: frozenset[str] = frozenset(
    {
        "eval", "exec", "compile", "open", "input", "breakpoint", "globals", "locals", "vars",
        "getattr", "setattr", "delattr", "__import__", "exit", "quit", "help", "memoryview",
    }
)

#: Bootstrap source lives beside this module so it can be linted and reviewed as code.
_BOOTSTRAP_PATH = Path(__file__).with_name("sandbox_bootstrap.py.tmpl")


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution_time_ms: int = 0
    exit_code: int = 0
    timed_out: bool = False

    @property
    def succeeded(self) -> bool:
        return self.error is None and not self.timed_out and self.exit_code == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "results": self.results,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "timed_out": self.timed_out,
            "succeeded": self.succeeded,
        }


def static_scan(source: str) -> None:
    """Reject code that cannot be safely executed. Raises :class:`SandboxDeniedError`."""
    if len(source) > 100_000:
        raise SandboxDeniedError("submitted code exceeds the 100,000 character limit")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise SandboxDeniedError(f"syntax error: {exc.msg} (line {exc.lineno})") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_MODULES:
                    raise SandboxDeniedError(
                        f"import of '{alias.name}' is not permitted",
                        details={"allowed_modules": sorted(ALLOWED_MODULES)},
                    )
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_MODULES:
                raise SandboxDeniedError(
                    f"import from '{node.module}' is not permitted",
                    details={"allowed_modules": sorted(ALLOWED_MODULES)},
                )
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise SandboxDeniedError(f"use of '{node.id}' is not permitted")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise SandboxDeniedError(f"access to dunder attribute '{node.attr}' is not permitted")


class PythonSandbox:
    """Runs Python code in a restricted child process."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        memory_mb: int = 512,
        cpu_seconds: int = 15,
        max_output_bytes: int = 200_000,
        max_file_bytes: int = 8 * 1024 * 1024,
        python_executable: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.memory_mb = memory_mb
        self.cpu_seconds = cpu_seconds
        self.max_output_bytes = max_output_bytes
        self.max_file_bytes = max_file_bytes
        self.python_executable = python_executable or sys.executable

    def _preexec(self) -> None:  # pragma: no cover - runs in the child process
        os.setsid()
        memory_bytes = self.memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
        resource.setrlimit(resource.RLIMIT_CPU, (self.cpu_seconds, self.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (self.max_file_bytes, self.max_file_bytes))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    def run(self, source: str, *, timeout_seconds: float | None = None) -> SandboxResult:
        static_scan(source)
        timeout = timeout_seconds or self.timeout_seconds
        workdir = tempfile.mkdtemp(prefix="finagent-sandbox-")
        code_path = os.path.join(workdir, "submitted.py")
        result_path = os.path.join(workdir, "result.json")
        bootstrap_path = os.path.join(workdir, "bootstrap.py")

        try:
            Path(code_path).write_text(source, encoding="utf-8")
            Path(bootstrap_path).write_text(
                _BOOTSTRAP_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )

            environment = {
                "PATH": "/usr/bin:/bin",
                "HOME": workdir,
                "TMPDIR": workdir,
                "PYTHONHASHSEED": "0",
                "PYTHONDONTWRITEBYTECODE": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "MPLBACKEND": "Agg",
            }
            started = time.perf_counter()
            process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                [
                    self.python_executable,
                    "-I",
                    "-B",
                    bootstrap_path,
                    result_path,
                    code_path,
                    json.dumps(sorted(ALLOWED_MODULES)),
                ],
                cwd=workdir,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=self._preexec,
                text=True,
            )
            timed_out = False
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                except ProcessLookupError:  # pragma: no cover - race with exit
                    pass
                stdout, stderr = process.communicate()
            wall_ms = int((time.perf_counter() - started) * 1000)

            if timed_out:
                logger.warning("sandbox_timeout", extra={"timeout_seconds": timeout})
                raise SandboxTimeoutError(
                    f"code execution exceeded {timeout:.0f}s", details={"timeout_seconds": timeout}
                )

            payload: dict[str, Any] = {}
            if os.path.exists(result_path):
                try:
                    payload = json.loads(Path(result_path).read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    payload = {}

            return SandboxResult(
                stdout=(payload.get("stdout") or stdout or "")[: self.max_output_bytes],
                stderr=((payload.get("stderr") or "") + (stderr or ""))[: self.max_output_bytes],
                results=payload.get("results") or {},
                error=payload.get("error"),
                execution_time_ms=int(payload.get("execution_time_ms") or wall_ms),
                exit_code=process.returncode or 0,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def describe(self) -> dict[str, Any]:
        return {
            "isolation": "subprocess+rlimits",
            "network": "disabled",
            "timeout_seconds": self.timeout_seconds,
            "memory_mb": self.memory_mb,
            "cpu_seconds": self.cpu_seconds,
            "allowed_modules": sorted(ALLOWED_MODULES),
            "production_target": "dedicated container sandbox worker",
        }
