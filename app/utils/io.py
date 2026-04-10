import shutil
import tempfile
from pathlib import Path

import anndata as ad
from fastapi import UploadFile

from app.utils.errors import PipelineStepError


def load_h5ad(path: Path) -> ad.AnnData:
    """Load an .h5ad file from disk into an AnnData object.

    Args:
        path: Path to the .h5ad file.

    Returns:
        Loaded AnnData object.

    Raises:
        PipelineStepError: If the file cannot be read or is not a valid .h5ad.
    """
    if path.suffix != ".h5ad":
        raise PipelineStepError("io", f"Expected a .h5ad file, got '{path.suffix}'")
    try:
        return ad.read_h5ad(path)
    except Exception as e:
        raise PipelineStepError("io", f"Failed to read {path.name}: {e}") from e


def save_h5ad(adata: ad.AnnData, path: Path) -> None:
    """Save an AnnData object to disk as .h5ad.

    Args:
        adata: AnnData object to persist.
        path: Destination path for the .h5ad file.

    Raises:
        PipelineStepError: If the file cannot be written.
    """
    try:
        adata.write_h5ad(path)
    except Exception as e:
        raise PipelineStepError("io", f"Failed to write {path.name}: {e}") from e


def stage_upload(upload: UploadFile) -> Path:
    """Write an uploaded file to a temporary path on disk and return the path.

    The caller is responsible for deleting the file after use.

    Args:
        upload: FastAPI UploadFile from the /analyze route.

    Returns:
        Path to the staged temporary file.

    Raises:
        PipelineStepError: If the upload cannot be written to disk.
    """
    suffix = Path(upload.filename).suffix if upload.filename else ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(upload.file, tmp)
            return Path(tmp.name)
    except Exception as e:
        raise PipelineStepError("io", f"Failed to stage uploaded file: {e}") from e
