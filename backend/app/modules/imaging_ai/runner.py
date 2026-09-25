"""Runner backends for AI jobs: pano by default, nnU-Net for volumes.

The ``Runner`` protocol is the only seam between DentalPin and the heavy
ML stack (torch/nnU-Net/CUDA stay OUT of the backend image). Runners are
clinic-agnostic pure functions of (input bytes, work dir); tenancy lives
in the service. Every failure encodes into ``RunnerResult(ok=False, ...)``
— a runner never raises.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class RunnerResult:
    """Outcome of one runner invocation."""

    ok: bool
    # Name -> file bytes produced by the backend (segmentations, previews).
    artifacts: dict[str, bytes] = field(default_factory=dict)
    # Bounded tail of stdout/stderr for the job log.
    log_excerpt: str = ""
    error: str | None = None


class Runner(Protocol):
    """Pluggable AI backend. Implementations must be clinic-agnostic pure
    functions of (input bytes, work dir): tenancy lives in the service."""

    name: str

    async def run(self, input_bytes: bytes, work_dir: Path) -> RunnerResult:
        """Run inference over one job's input bytes. Never raises: encode
        every failure mode into ``RunnerResult(ok=False, ...)``."""
        ...


def build_nnunet_cmd(
    binary: str, in_dir: Path, out_dir: Path, *, weights: bool, allow_cpu: bool
) -> list[str]:
    """Pure nnU-Net argv builder (pinned by tests — this is how CLI-contract
    drift slipped through before). ``-d 112 -c 3d_fullres`` selects the
    DentalSegmentator weights; ``-device cpu`` only on explicit opt-in."""
    cmd = [binary, "-i", str(in_dir), "-o", str(out_dir)]
    if weights:
        cmd += ["-d", "112", "-c", "3d_fullres"]
    if allow_cpu:
        cmd += ["-device", "cpu"]
    return cmd


def build_pano_cmd(python_exe: str, app_main: Path, input_png: Path, out_dir: Path) -> list[str]:
    """Pure pano argv builder (pinned by tests)."""
    return [python_exe, str(app_main), "--input", str(input_png), "--output", str(out_dir)]


def _has_cuda() -> bool:
    """CUDA presence without importing torch (which never enters the image)."""
    return shutil.which("nvidia-smi") is not None


class SubprocessNnunetRunner:
    """Volumetric runner: local ``nnUNetv2_predict`` subprocess.

    Input is a ready ``.nii.gz`` volume (the service stacks the job's
    DICOM series via :mod:`volume` first — a lone frame fails there with
    an actionable message, never here). Weights are operator-provided
    (Zenodo ``Dataset112_DentalSegmentator``, CC-BY-4.0 — see NOTICE.md)
    via the ``DENTALPIN_NNUNET_WEIGHTS`` dir, and the runner refuses
    without them (nnUNet requires ``-d``/``-c``). Without CUDA the runner
    refuses unless the operator explicitly opts into CPU via
    ``DENTALPIN_NNUNET_ALLOW_CPU=1`` (no silent CPU crawl).
    """

    name = "nnunet"

    def __init__(
        self,
        weights_dir: Path | None = None,
        allow_cpu: bool = False,
        timeout_seconds: int = 3600,
    ) -> None:
        self.weights_dir = weights_dir
        self.allow_cpu = allow_cpu
        self.timeout_seconds = timeout_seconds

    async def run(self, input_bytes: bytes, work_dir: Path) -> RunnerResult:
        nnunet = shutil.which("nnUNetv2_predict")
        if nnunet is None:
            return RunnerResult(
                ok=False,
                error="nnUNetv2_predict not found on PATH — install nnU-Net v2 "
                "on the AI host (see NOTICE.md)",
            )
        if self.weights_dir is None or not self.weights_dir.exists():
            return RunnerResult(
                ok=False,
                error="nnU-Net weights missing: set DENTALPIN_NNUNET_WEIGHTS to the "
                "Dataset112_DentalSegmentator dir (see NOTICE.md)",
            )
        if not self.allow_cpu and not _has_cuda():
            return RunnerResult(
                ok=False,
                error="no CUDA device found and CPU not opted in: set "
                "DENTALPIN_NNUNET_ALLOW_CPU=1 to run on CPU (slow) or use "
                "the pano backend for single frames",
            )
        work_dir.mkdir(parents=True, exist_ok=True)
        in_dir, out_dir = work_dir / "in", work_dir / "out"
        in_dir.mkdir(exist_ok=True)
        out_dir.mkdir(exist_ok=True)
        (in_dir / "case_0000.nii.gz").write_bytes(input_bytes)
        cmd = build_nnunet_cmd(nnunet, in_dir, out_dir, weights=True, allow_cpu=self.allow_cpu)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
            except TimeoutError:
                proc.kill()
                return RunnerResult(
                    ok=False, error=f"nnU-Net timed out after {self.timeout_seconds}s"
                )
            log = (out or b"").decode(errors="replace")[-3000:]
            if proc.returncode != 0:
                return RunnerResult(
                    ok=False, log_excerpt=log, error=f"nnU-Net exited {proc.returncode}"
                )
            artifacts: dict[str, bytes] = {}
            if out_dir.exists():
                for child in sorted(out_dir.iterdir()):
                    if child.is_file() and child.suffix.lower() in {
                        ".nii",
                        ".gz",
                        ".png",
                        ".jpg",
                    }:
                        artifacts[child.name] = child.read_bytes()
            return RunnerResult(ok=True, artifacts=artifacts, log_excerpt=log)
        except Exception as exc:  # noqa: BLE001 — runner never raises
            return RunnerResult(ok=False, error=f"runner crashed: {exc}")


def dicom_to_png(dicom_bytes: bytes) -> bytes:
    """Render single-frame DICOM bytes to PNG. Raises ``RuntimeError`` with
    an actionable message when the pixel stack is unavailable."""
    try:
        import io

        import pydicom
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(f"pano input needs pydicom+Pillow installed: {exc}") from exc
    try:
        import numpy as np

        ds = pydicom.dcmread(io.BytesIO(dicom_bytes))
        arr = ds.pixel_array
    except Exception as exc:
        raise RuntimeError(f"cannot decode DICOM pixels: {exc}") from exc
    if arr.ndim == 3:
        arr = arr[0]
    lo, hi = float(np.min(arr)), float(np.max(arr))
    norm = ((arr.astype(float) - lo) / (hi - lo + 1e-9) * 255.0).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(norm).save(buf, format="PNG")
    return buf.getvalue()


class PanoRunner:
    """Pano detection backend: ``dental-pano-ai`` (MIT) ``main.py`` CLI.

    Weights are operator-provided (S3 tarball, no stated terms — the
    clinic must confirm the license before production use, see NOTICE.md);
    the checkout path comes from ``DENTALPIN_PANO_APP``. DICOM input is
    rendered to PNG first (single-frame panos). Results dir PNGs become
    overlay artifacts. This is the default backend: the one path that
    runs end to end on single-frame input.
    """

    name = "pano"

    def __init__(
        self,
        app_dir: Path | None = None,
        python_exe: str = sys.executable,
        timeout_seconds: int = 1800,
    ) -> None:
        self.app_dir = app_dir
        self.python_exe = python_exe
        self.timeout_seconds = timeout_seconds

    async def run(self, input_bytes: bytes, work_dir: Path) -> RunnerResult:
        if self.app_dir is None or not (self.app_dir / "main.py").exists():
            return RunnerResult(
                ok=False,
                error="dental-pano-ai checkout missing: set DENTALPIN_PANO_APP "
                "to the app dir with downloaded weights (see NOTICE.md)",
            )
        try:
            png = dicom_to_png(input_bytes)
        except RuntimeError as exc:
            return RunnerResult(ok=False, error=str(exc))
        work_dir.mkdir(parents=True, exist_ok=True)
        in_dir, out_dir = work_dir / "in", work_dir / "out"
        in_dir.mkdir(exist_ok=True)
        out_dir.mkdir(exist_ok=True)
        (in_dir / "study.png").write_bytes(png)
        cmd = build_pano_cmd(
            self.python_exe, self.app_dir / "main.py", in_dir / "study.png", out_dir
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
            except TimeoutError:
                proc.kill()
                return RunnerResult(
                    ok=False, error=f"pano run timed out after {self.timeout_seconds}s"
                )
            log = (out or b"").decode(errors="replace")[-3000:]
            if proc.returncode != 0:
                return RunnerResult(
                    ok=False, log_excerpt=log, error=f"pano exited {proc.returncode}"
                )
            artifacts: dict[str, bytes] = {}
            for child in sorted(out_dir.iterdir()):
                if child.is_file() and child.suffix.lower() in {".png", ".jpg"}:
                    artifacts[child.name] = child.read_bytes()
            if not artifacts:
                return RunnerResult(ok=False, log_excerpt=log, error="pano produced no images")
            return RunnerResult(ok=True, artifacts=artifacts, log_excerpt=log)
        except Exception as exc:  # noqa: BLE001 — runner never raises
            return RunnerResult(ok=False, error=f"runner crashed: {exc}")


def nnunet_env() -> tuple[Path | None, bool]:
    """Read the nnU-Net operator env (single place — docs mirror this)."""
    raw_dir = os.environ.get("DENTALPIN_NNUNET_WEIGHTS")
    weights = Path(raw_dir) if raw_dir else None
    allow_cpu = os.environ.get("DENTALPIN_NNUNET_ALLOW_CPU") == "1"
    return weights, allow_cpu
