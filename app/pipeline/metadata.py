import logging

import anndata as ad

from app.models.schemas import DatasetMetadata

logger = logging.getLogger(__name__)

# Scientific name → common name normalisation map.
# Used to compare file-reported organism against user-provided organism.
_ORGANISM_SYNONYMS: dict[str, str] = {
    "homo sapiens": "human",
    "mus musculus": "mouse",
    "rattus norvegicus": "rat",
    "danio rerio": "zebrafish",
    "drosophila melanogaster": "fly",
    "caenorhabditis elegans": "worm",
    "ncbitaxon:9606": "human",
    "ncbitaxon:10090": "mouse",
    "ncbitaxon:10116": "rat",
    "ncbitaxon:7955": "zebrafish",
}

# Known AnnData uns/obs keys for organism and tissue, in priority order.
_ORGANISM_KEYS = [
    "organism",
    "species",
    "Species",
    "Organism",
    "organism_ontology_term_id",
]
_TISSUE_KEYS = [
    "tissue",
    "tissue_type",
    "organ",
    "Tissue",
    "tissue_ontology_term_id",
]


def _read_scalar_or_mode(adata: ad.AnnData, key: str) -> str | None:
    """Return a string value from uns or the modal obs column value.

    Args:
        adata: Loaded AnnData object.
        key: Metadata key to look up.

    Returns:
        String value if found and non-empty, else None.
    """
    # uns takes priority — it's a dataset-level attribute
    val = adata.uns.get(key)
    if val is not None and isinstance(val, str) and val.strip():
        return val.strip()

    # Fall back to obs column (take the modal value — most cells share one label)
    if key in adata.obs.columns:
        try:
            mode = adata.obs[key].mode()
            if len(mode) > 0:
                result = str(mode.iloc[0]).strip()
                if result:
                    return result
        except Exception:
            pass

    return None


def _normalise_organism(value: str) -> str:
    """Lowercase and apply synonym map to a raw organism string."""
    return _ORGANISM_SYNONYMS.get(value.lower().strip(), value.lower().strip())


def extract_and_check_metadata(
    adata: ad.AnnData,
    provided_tissue: str,
    provided_organism: str,
) -> DatasetMetadata:
    """Extract organism/tissue metadata from h5ad and compare against user inputs.

    Checks adata.uns and adata.obs for known metadata keys. Normalises scientific
    organism names (e.g. 'Homo sapiens') to common names for comparison.

    Args:
        adata: Loaded AnnData object (pre-QC is fine).
        provided_tissue: Tissue string the user entered in the UI.
        provided_organism: Organism string the user selected in the UI.

    Returns:
        DatasetMetadata with raw file values and an organism_mismatch flag.
    """
    organism_in_file: str | None = None
    tissue_in_file: str | None = None

    for key in _ORGANISM_KEYS:
        val = _read_scalar_or_mode(adata, key)
        if val:
            organism_in_file = val
            logger.info("Found organism in file ('%s'): %s", key, val)
            break

    for key in _TISSUE_KEYS:
        val = _read_scalar_or_mode(adata, key)
        if val:
            tissue_in_file = val
            logger.info("Found tissue in file ('%s'): %s", key, val)
            break

    organism_mismatch = False
    if organism_in_file:
        norm_file = _normalise_organism(organism_in_file)
        norm_provided = provided_organism.lower().strip()
        if norm_file != norm_provided:
            logger.warning(
                "Organism mismatch: file reports '%s' (normalised: '%s'), "
                "user provided '%s'.",
                organism_in_file,
                norm_file,
                provided_organism,
            )
            organism_mismatch = True

    return DatasetMetadata(
        organism_in_file=organism_in_file,
        tissue_in_file=tissue_in_file,
        organism_mismatch=organism_mismatch,
    )
