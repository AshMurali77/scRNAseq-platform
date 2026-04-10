import anndata as ad
from pathlib import Path


def load_h5ad(path: Path) -> ad.AnnData:
    """Load an .h5ad file from disk into an AnnData object.

    Args:
        path: Path to the .h5ad file.

    Returns:
        Loaded AnnData object.

    Raises:
        PipelineStepError: If the file cannot be read or is not a valid .h5ad.
    """
    pass


def save_h5ad(adata: ad.AnnData, path: Path) -> None:
    """Save an AnnData object to disk as .h5ad.

    Args:
        adata: AnnData object to persist.
        path: Destination path for the .h5ad file.

    Raises:
        PipelineStepError: If the file cannot be written.
    """
    pass
