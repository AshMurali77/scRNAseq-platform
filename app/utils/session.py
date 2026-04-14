"""Session storage for caching processed AnnData objects.

After /analyze completes, the processed AnnData is written to a temp file
so downstream analysis endpoints (/downstream/de, /downstream/trajectory)
can reload it without re-running the full pipeline.
"""

import logging
import pathlib
import uuid

import anndata as ad

logger = logging.getLogger(__name__)

_SESSION_DIR = pathlib.Path("/tmp/scrnaseq_sessions")
_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def save_session(adata: ad.AnnData) -> str:
    """Persist a processed AnnData object and return a UUID session key.

    The file is written to /tmp/scrnaseq_sessions/<uuid>.h5ad. Cleanup is
    left to the OS; sessions are not explicitly expired.

    Args:
        adata: Fully processed AnnData (post-celltypist, pre-result assembly).

    Returns:
        A UUID string that can be passed to load_session().

    Raises:
        OSError: If the h5ad file cannot be written.
    """
    session_id = str(uuid.uuid4())
    path = _SESSION_DIR / f"{session_id}.h5ad"
    adata.write_h5ad(path)
    logger.info("Session saved: %s (%d cells)", session_id, adata.n_obs)
    return session_id


def load_session(session_id: str) -> ad.AnnData:
    """Load a previously saved AnnData object by session ID.

    Args:
        session_id: UUID returned by save_session().

    Returns:
        The AnnData object as it was when saved.

    Raises:
        FileNotFoundError: If no session file exists for the given ID.
    """
    path = _SESSION_DIR / f"{session_id}.h5ad"
    if not path.exists():
        raise FileNotFoundError(
            f"Session '{session_id}' not found. "
            "It may have expired or never existed."
        )
    adata = ad.read_h5ad(path)
    logger.info("Session loaded: %s (%d cells)", session_id, adata.n_obs)
    return adata
