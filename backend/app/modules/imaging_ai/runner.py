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
from collections.abc import Sequence
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
    binary: str,
    in_dir: Path,
    out_dir: Path,
    *,
    weights: bool,
    allow_cpu: bool,
    folds: Sequence[int] | None = None,
) -> list[str]:
    """Pure nnU-Net argv builder (pinned by tests — this is how CLI-contract
    drift slipped through before). ``-d 112 -c 3d_fullres`` selects the
    DentalSegmentator weights; ``-device cpu`` only on explicit opt-in.

    ``folds`` is passed as ``-f <n> ...`` because ``nnUNetv2_predict``
    otherwise defaults to ``-f 0 1 2 3 4`` and dies on the first fold that
    was never downloaded: the operator-facing Zenodo zip of
    Dataset112_DentalSegmentator ships ``fold_0`` only, so the run failed
    after doing the work. ``None`` means "let nnU-Net decide" (used only
    when a full 5-fold download is present and the caller did not restrict).
    """
    cmd = [binary, "-i", str(in_dir), "-o", str(out_dir)]
    if weights:
        cmd += ["-d", "112", "-c", "3d_fullres"]
    if folds:
        cmd += ["-f", *[str(f) for f in folds]]
    if allow_cpu:
        cmd += ["-device", "cpu"]
    return cmd


def available_folds(weights_dir: Path) -> list[int]:
    """Folds actually present under the operator's weights dir.

    nnU-Net resolves ``-d 112`` through its own results tree, so the model
    lives at ``<weights_dir>/Dataset112_*/`` with one ``fold_<n>``
    subdirectory per fold. Asking nnU-Net for a fold that was never
    downloaded aborts the whole prediction, so the runner asks for exactly
    what is on disk. Empty means "let nnU-Net decide" (its default applies).
    """
    if not weights_dir.exists():
        return []
    folds: set[int] = set()
    for dataset_dir in weights_dir.glob("Dataset112_*"):
        for fold_dir in dataset_dir.glob("fold_*"):
            token = fold_dir.name.removeprefix("fold_")
            if token.isdigit():
                folds.add(int(token))
    return sorted(folds)


def build_pano_cmd(python_exe: str, app_main: Path, input_png: Path, out_dir: Path) -> list[str]:
    """Pure pano argv builder (pinned by tests against UPSTREAM's contract).

    ``--debug`` is what makes dental-pano-ai emit the overlay images at all:
    without it upstream ``main.py`` writes only ``<output>/<stem>.csv`` and
    exits 0, so the run looks successful while producing nothing we could
    show. The CSV is ingested either way; the images are the point of
    ``--debug``. Model paths (``--deeplab_config`` and friends) are left at
    their upstream ``./models/...`` defaults and resolved by running with
    ``cwd=app_dir`` (see ``PanoRunner.run``) rather than by baking absolute
    paths into the command, so a checkout keeps working wherever it is
    mounted.
    """
    return [
        python_exe,
        str(app_main),
        "--input",
        str(input_png),
        "--output",
        str(out_dir),
        "--debug",
    ]


PANO_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
PANO_TABLE_SUFFIX = ".csv"


def collect_pano_artifacts(out_dir: Path) -> dict[str, bytes]:
    """Read every artifact a pano run left, wherever upstream put it.

    Upstream (stmharry/dental-pano-ai) layout: the per-FDI findings table
    ``<output>/<stem>.csv`` at the top level, and with ``--debug`` the
    overlays in the ``<output>/<stem>/`` subdirectory. Scanning only the top
    level (the previous behaviour) meant a real run produced "no images" and
    silently dropped the clinically useful CSV. Keys are namespaced by
    relative path so the subdirectory and the top level cannot collide.
    """
    artifacts: dict[str, bytes] = {}
    if not out_dir.exists():
        return artifacts
    for child in sorted(out_dir.rglob("*")):
        if not child.is_file():
            continue
        suffix = child.suffix.lower()
        if suffix not in PANO_IMAGE_SUFFIXES and suffix != PANO_TABLE_SUFFIX:
            continue
        key = child.relative_to(out_dir).as_posix()
        try:
            artifacts[key] = child.read_bytes()
        except OSError:
            continue
    return artifacts


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
        folds = available_folds(self.weights_dir)
        cmd = build_nnunet_cmd(
            nnunet, in_dir, out_dir, weights=True, allow_cpu=self.allow_cpu, folds=folds
        )
        # nnU-Net resolves `-d 112` through nnUNet_results, not through any
        # flag we pass: without this env var the subprocess searched the
        # backend's cwd and never found the operator's weights (the dir was
        # existence-checked and then silently unused).
        child_env = nnunet_child_env(self.weights_dir)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                env=child_env,
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
    the checkout path comes from ``DENTALPIN_PANO_APP`` and the interpreter
    from ``DENTALPIN_PANO_PYTHON`` (the checkout needs its own venv: its
    main.py imports torch/detectron2/ultralytics, which stay out of the
    backend image by design). DICOM input is rendered to PNG first
    (single-frame panos). Overlay images AND the per-FDI findings CSV
    become draft artifacts. This is the default backend: the one path that
    runs end to end on single-frame input.
    """

    name = "pano"

    def __init__(
        self,
        app_dir: Path | None = None,
        python_exe: str | None = None,
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
        # Interpreter: the operator's own venv when configured, else the
        # backend's. Refusing early with an actionable message beats a
        # traceback from inside upstream's imports.
        python_exe = self.python_exe or sys.executable
        if shutil.which(python_exe) is None and not Path(python_exe).exists():
            return RunnerResult(
                ok=False,
                error=f"pano interpreter not found: {python_exe!r} — set "
                "DENTALPIN_PANO_PYTHON to the dental-pano-ai venv python "
                "(see NOTICE.md)",
            )
        cmd = build_pano_cmd(python_exe, self.app_dir / "main.py", in_dir / "study.png", out_dir)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                # Upstream resolves its model paths relative to cwd
                # (./models/...), so the checkout dir IS the cwd.
                cwd=str(self.app_dir),
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
            artifacts = collect_pano_artifacts(out_dir)
            if not artifacts:
                return RunnerResult(
                    ok=False,
                    log_excerpt=log,
                    error="pano produced no images and no findings table "
                    "(expected <stem>.csv, plus overlays with --debug)",
                )
            return RunnerResult(ok=True, artifacts=artifacts, log_excerpt=log)
        except Exception as exc:  # noqa: BLE001 — runner never raises
            return RunnerResult(ok=False, error=f"runner crashed: {exc}")


def nnunet_child_env(weights_dir: Path) -> dict[str, str]:
    """Environment for the nnU-Net subprocess.

    nnU-Net resolves ``-d 112`` through ``nnUNet_results``, not through any
    flag we pass, so without this the operator's weights were never seen:
    the dir was existence-checked and then dropped, and the subprocess
    searched the backend's cwd. Pure and exported so a test can pin it on
    any platform (a fake binary would have to be POSIX-only to run at all).
    """
    return {**os.environ, "nnUNet_results": str(weights_dir)}


def nnunet_env() -> tuple[Path | None, bool]:
    """Read the nnU-Net operator env (single place — docs mirror this)."""
    raw_dir = os.environ.get("DENTALPIN_NNUNET_WEIGHTS")
    weights = Path(raw_dir) if raw_dir else None
    allow_cpu = os.environ.get("DENTALPIN_NNUNET_ALLOW_CPU") == "1"
    return weights, allow_cpu


def pano_env() -> tuple[Path | None, str | None]:
    """Read the pano operator env (single place — docs mirror this).

    ``DENTALPIN_PANO_APP`` is the checkout dir; ``DENTALPIN_PANO_PYTHON`` is
    the interpreter that can import that checkout's dependencies (torch,
    detectron2, ultralytics), which by design never enter the backend image.
    ``None`` for the interpreter means "use the backend's own", which is only
    correct for a checkout that happens to share its site-packages.
    """
    raw_dir = os.environ.get("DENTALPIN_PANO_APP")
    app_dir = Path(raw_dir) if raw_dir else None
    python_exe = os.environ.get("DENTALPIN_PANO_PYTHON") or None
    return app_dir, python_exe
