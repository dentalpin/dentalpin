"""DICOM-series to NIfTI volume conversion for volumetric backends.

nnU-Net (``nnUNetv2_predict -i``) consumes NIfTI volumes named
``<case>_0000.nii.gz`` — not the single-frame DICOM bytes a study row
holds. This module stacks one series' slices (sorted by instance
number) into a minimal single-file NIfTI-1 volume (``.nii.gz``) with
identity orientation and voxel spacing from the DICOM tags.

Deliberate v1 limits (documented, not silent): orientation is identity
(``qform`` from the first slice's position, no direction cosines), so
a clinic must sanity-check overlays on first use; intensities are raw
(+ RescaleSlope/Intercept) with no windowing. Anything that cannot
form a coherent volume raises ``VolumeError`` with an actionable
message — the runner turns it into a terminal job failure, never a
traceback.
"""

from __future__ import annotations

import gzip
import io
import struct
from dataclasses import dataclass


class VolumeError(ValueError):
    """A DICOM set cannot form an nnU-Net-ready volume."""


@dataclass
class NiftiVolume:
    """One stacked series, ready to write as ``<case>_0000.nii.gz``."""

    data: bytes
    nx: int
    ny: int
    nz: int
    spacing: tuple[float, float, float]
    series_uid: str


def _read_slices(dicom_blobs: list[bytes]) -> list[dict]:
    try:
        import numpy as np
        import pydicom
    except ImportError as exc:
        raise VolumeError(f"volume input needs pydicom+numpy installed: {exc}") from exc
    if not dicom_blobs:
        raise VolumeError("nnunet needs a volume: no DICOM slices provided")
    parsed = []
    for i, blob in enumerate(dicom_blobs):
        try:
            ds = pydicom.dcmread(io.BytesIO(blob))
            arr = ds.pixel_array
        except Exception as exc:
            raise VolumeError(f"slice {i} is not decodable DICOM: {exc}") from exc
        if arr.ndim == 3 and arr.shape[0] == 1:
            arr = arr[0]
        if arr.ndim != 2:
            raise VolumeError(
                f"slice {i} is not a single frame (shape {arr.shape}); "
                "multi-frame volumes are not supported, queue one series"
            )
        slope = float(getattr(ds, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(ds, "RescaleIntercept", 0.0) or 0.0)
        pixels = (arr.astype("float64") * slope + intercept).clip(-32768, 32767).astype(np.int16)
        pos = getattr(ds, "ImagePositionPatient", None)
        try:
            inst = int(getattr(ds, "InstanceNumber", i))
        except (TypeError, ValueError):
            inst = i
        parsed.append(
            {
                "series_uid": str(getattr(ds, "SeriesInstanceUID", "") or ""),
                "instance": inst,
                "z": float(pos[2]) if pos is not None and len(pos) == 3 else float(inst),
                "rows": int(ds.Rows),
                "columns": int(ds.Columns),
                "pixels": pixels,
                "row_spacing": _spacing(ds, "PixelSpacing", 0, 1.0),
                "col_spacing": _spacing(ds, "PixelSpacing", 1, 1.0),
                "slice_spacing": _slice_spacing(ds),
                "origin": [float(v) for v in pos]
                if pos is not None and len(pos) == 3
                else [0.0, 0.0, 0.0],
            }
        )
    return parsed


def _spacing(ds, tag: str, idx: int, default: float) -> float:
    try:
        values = getattr(ds, tag)
        return float(values[idx])
    except (AttributeError, TypeError, ValueError, IndexError):
        return default


def _slice_spacing(ds) -> float:
    try:
        return float(ds.SliceThickness)
    except (AttributeError, TypeError, ValueError):
        return 1.0


def dicom_series_to_nifti(dicom_blobs: list[bytes]) -> NiftiVolume:
    """Stack one DICOM series into a NIfTI-1 ``.nii.gz`` payload."""
    parsed = _read_slices(dicom_blobs)
    uids = {p["series_uid"] for p in parsed if p["series_uid"]}
    if len(uids) > 1:
        raise VolumeError(
            f"mixed series in one job ({len(uids)} SeriesInstanceUIDs); queue one series per job"
        )
    geoms = {(p["rows"], p["columns"]) for p in parsed}
    if len(geoms) > 1:
        raise VolumeError(f"inconsistent slice geometry {sorted(geoms)}; queue one series per job")
    if len(parsed) < 2:
        raise VolumeError(
            "nnunet needs a volume: a single frame cannot segment; "
            "queue the series (or use the pano backend for single frames)"
        )
    ordered = sorted(parsed, key=lambda p: (p["instance"], p["z"]))
    rows, columns = ordered[0]["rows"], ordered[0]["columns"]
    try:
        import numpy as np
    except ImportError as exc:
        raise VolumeError(f"volume input needs numpy installed: {exc}") from exc
    stacked = np.stack([p["pixels"] for p in ordered]).astype(np.int16)  # (nz, ny, nx)
    # NIfTI stores x fastest: (nx, ny, nz) Fortran order.
    volume = np.asfortranarray(stacked.transpose(2, 1, 0))
    first = ordered[0]
    spacing = (first["col_spacing"], first["row_spacing"], _z_spacing(ordered))
    header = _nifti1_header(
        nx=columns,
        ny=rows,
        nz=len(ordered),
        pixdim=(1.0, *spacing, 0.0, 0.0, 0.0, 0.0),
        qoffset=tuple(first["origin"]),
    )
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(header)
        gz.write(volume.tobytes(order="F"))
    return NiftiVolume(
        data=buf.getvalue(),
        nx=columns,
        ny=rows,
        nz=len(ordered),
        spacing=spacing,
        series_uid=first["series_uid"],
    )


def _z_spacing(ordered: list[dict]) -> float:
    if len(ordered) < 2:
        return ordered[0]["slice_spacing"]
    gaps = [abs(ordered[i + 1]["z"] - ordered[i]["z"]) for i in range(len(ordered) - 1)]
    gaps = [g for g in gaps if g > 0]
    return min(gaps) if gaps else ordered[0]["slice_spacing"]


def _nifti1_header(
    nx: int, ny: int, nz: int, pixdim: tuple[float, ...], qoffset: tuple[float, float, float]
) -> bytes:
    """Minimal NIfTI-1 single-file header (348 bytes + 4 zero extension bytes)."""
    h = bytearray(348)
    struct.pack_into("<i", h, 0, 348)  # sizeof_hdr
    # dim[0]=3, dim[1..3]=(nx, ny, nz)
    struct.pack_into("<8h", h, 40, 3, nx, ny, nz, 1, 1, 1, 1)
    struct.pack_into("<h", h, 70, 4)  # datatype INT16
    struct.pack_into("<h", h, 72, 16)  # bitpix
    struct.pack_into("<8f", h, 76, *pixdim)  # pixdim
    struct.pack_into("<f", h, 108, 352.0)  # vox_offset
    struct.pack_into("<h", h, 124, 1)  # qform_code (scanner position, identity rotation)
    struct.pack_into("<h", h, 126, 0)  # sform_code
    struct.pack_into("<3f", h, 268, 1.0, 0.0, 0.0)  # quatern_b/c/d (identity)
    struct.pack_into("<3f", h, 280, *qoffset)  # qoffset
    h[344:348] = b"n+1\x00"  # magic: single-file .nii
    return bytes(h) + b"\x00\x00\x00\x00"
