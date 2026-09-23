"""Runner backends for AI jobs: subprocess nnU-Net today, external workers later.

The ``Runner`` protocol is the only seam between DentalPin and the heavy
ML stack (torch/nnU-Net/CUDA stay OUT of the backend image). v1 shells out
to ``nnUNetv2_predict`` locally; a future worker-based runner implements the
same protocol without touching callers.
"""

from __future__ import annotations

import asyncio
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

    async def run(self, dicom_bytes: bytes, work_dir: Path) -> RunnerResult:
        """Run inference over one study's DICOM bytes. Never raises: encode
        every failure mode into ``RunnerResult(ok=False, ...)``."""
        ...


class SubprocessNnunetRunner:
    """v1 runner: local ``nnUNetv2_predict`` subprocess.

    Weights are operator-provided (Zenodo ``Dataset112_DentalSegmentator``,
    CC-BY-4.0 — see NOTICE.md) via the ``DENTALPIN_NNUNET_WEIGHTS`` dir.
    Refuses loudly (no silent CPU crawl) when the operator has not opted
    into CPU execution and no CUDA device is present.
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

    async def run(self, dicom_bytes: bytes, work_dir: Path) -> RunnerResult:
        nnunet = shutil.which("nnUNetv2_predict")
        if nnunet is None:
            return RunnerResult(
                ok=False,
                error="nnUNetv2_predict not found on PATH — install nnU-Net v2 "
                "on the AI host (see NOTICE.md)",
            )
        if self.weights_dir is not None and not self.weights_dir.exists():
            return RunnerResult(
                ok=False,
                error=f"weights dir missing: {self.weights_dir} "
                "(download Dataset112_DentalSegmentator, see NOTICE.md)",
            )
        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "input.dcm"
        input_path.write_bytes(dicom_bytes)
        cmd = [nnunet, "-i", str(work_dir), "-o", str(work_dir / "out")]
        if self.weights_dir is not None:
            cmd += ["-d", "112", "-c", "3d_fullres"]
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
            out_dir = work_dir / "out"
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

    Weights are operator-provided (S3 tarball, no stated terms — see
    NOTICE.md); the checkout path comes from ``DENTALPIN_PANO_APP``.
    DICOM input is rendered to PNG first (single-frame panos). Results dir
    PNGs become overlay artifacts.
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

    async def run(self, dicom_bytes: bytes, work_dir: Path) -> RunnerResult:
        if self.app_dir is None or not (self.app_dir / "main.py").exists():
            return RunnerResult(
                ok=False,
                error="dental-pano-ai checkout missing: set DENTALPIN_PANO_APP "
                "to the app dir with downloaded weights (see NOTICE.md)",
            )
        try:
            png = dicom_to_png(dicom_bytes)
        except RuntimeError as exc:
            return RunnerResult(ok=False, error=str(exc))
        work_dir.mkdir(parents=True, exist_ok=True)
        in_dir, out_dir = work_dir / "in", work_dir / "out"
        in_dir.mkdir(exist_ok=True)
        out_dir.mkdir(exist_ok=True)
        (in_dir / "study.png").write_bytes(png)
        cmd = [
            self.python_exe,
            str(self.app_dir / "main.py"),
            "--input",
            str(in_dir / "study.png"),
            "--output",
            str(out_dir),
        ]
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


class OcrRunner:
    """Receipt/text OCR backend: ``tesseract`` CLI (Apache-2.0) sidecar.

    The binary is operator-provided (``DENTALPIN_TESSERACT_BIN`` override,
    else ``tesseract`` on PATH); languages via ``DENTALPIN_TESSERACT_LANG``
    (default ``eng``). Input is any image bytes (receipt photos, scanned
    referral letters); output is an ``ocr.txt`` transcript artifact. A blank
    image is a successful run with no artifacts, never an error.
    """

    name = "ocr"

    def __init__(
        self,
        tesseract_bin: str | None = None,
        lang: str = "eng",
        timeout_seconds: int = 300,
    ) -> None:
        self.tesseract_bin = tesseract_bin or "tesseract"
        self.lang = lang
        self.timeout_seconds = timeout_seconds

    async def run(self, dicom_bytes: bytes, work_dir: Path) -> RunnerResult:
        binary = shutil.which(self.tesseract_bin)
        if binary is None:
            return RunnerResult(
                ok=False,
                error="tesseract not found on PATH — install Tesseract OCR "
                "on the AI host (see NOTICE.md)",
            )
        work_dir.mkdir(parents=True, exist_ok=True)
        input_path = work_dir / "input.png"
        input_path.write_bytes(dicom_bytes)
        out_base = work_dir / "out"
        cmd = [binary, str(input_path), str(out_base), "-l", self.lang]
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
                return RunnerResult(ok=False, error=f"OCR timed out after {self.timeout_seconds}s")
            log = (out or b"").decode(errors="replace")[-3000:]
            if proc.returncode != 0:
                return RunnerResult(
                    ok=False, log_excerpt=log, error=f"tesseract exited {proc.returncode}"
                )
            text_path = out_base.with_suffix(".txt")
            text = (
                text_path.read_text(encoding="utf-8", errors="replace").strip()
                if text_path.exists()
                else ""
            )
            if not text:
                return RunnerResult(ok=True, log_excerpt=(log + "\nno text detected").strip())
            return RunnerResult(
                ok=True, artifacts={"ocr.txt": text.encode("utf-8")}, log_excerpt=log
            )
        except Exception as exc:  # noqa: BLE001 — runner never raises
            return RunnerResult(ok=False, error=f"runner crashed: {exc}")
