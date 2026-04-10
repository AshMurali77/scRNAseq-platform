import logging
from dataclasses import dataclass

import anndata as ad
import celltypist
import scanpy as sc

from app.utils.errors import PipelineStepError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

@dataclass
class ModelSelection:
    """The result of selecting a CellTypist model for a given tissue and organism.

    Designed to be extended in Phase 3: the LLM-backed select_model() will
    populate the same type and add reasoning and confidence fields without
    requiring any changes to callers.

    Attributes:
        model_name: CellTypist model filename (e.g. 'Immune_All_Low.pkl').
        display_name: Short human-readable name shown in the UI.
        description: One-sentence description of the model's scope.
    """

    model_name: str
    display_name: str
    description: str


# Lookup table: (tissue_lower, organism_lower) -> ModelSelection.
# Tissue and organism inputs are lowercased before lookup.
# Keys use common synonyms so users don't need exact spelling.
_MODEL_LOOKUP: dict[tuple[str, str], ModelSelection] = {
    # Human immune / blood
    ("blood", "human"):        ModelSelection("Immune_All_Low.pkl",   "Immune All Low",   "Pan-human immune atlas, fine-grained labels."),
    ("pbmc", "human"):         ModelSelection("Immune_All_Low.pkl",   "Immune All Low",   "Pan-human immune atlas, fine-grained labels."),
    ("bone marrow", "human"):  ModelSelection("Immune_All_High.pkl",  "Immune All High",  "Pan-human immune atlas, coarse labels."),
    ("spleen", "human"):       ModelSelection("Immune_All_Low.pkl",   "Immune All Low",   "Pan-human immune atlas, fine-grained labels."),
    ("lymph node", "human"):   ModelSelection("Immune_All_Low.pkl",   "Immune All Low",   "Pan-human immune atlas, fine-grained labels."),
    ("thymus", "human"):       ModelSelection("Immune_All_High.pkl",  "Immune All High",  "Pan-human immune atlas, coarse labels."),
    # Human lung
    ("lung", "human"):         ModelSelection("Human_Lung_Atlas.pkl", "Human Lung Atlas", "Human lung cell atlas covering healthy and disease states."),
    # Human brain
    ("brain", "human"):        ModelSelection("Human_AdultAged_Hippocampus.pkl", "Human Hippocampus", "Adult and aged human hippocampus."),
    ("hippocampus", "human"):  ModelSelection("Human_AdultAged_Hippocampus.pkl", "Human Hippocampus", "Adult and aged human hippocampus."),
    # Human colon
    ("colon", "human"):        ModelSelection("Human_Colorectal_Cancer.pkl", "Human Colorectal",  "Human colorectal tissue including cancer."),
    ("colorectal", "human"):   ModelSelection("Human_Colorectal_Cancer.pkl", "Human Colorectal",  "Human colorectal tissue including cancer."),
    # Human heart
    ("heart", "human"):        ModelSelection("Healthy_Adult_Heart.pkl", "Healthy Adult Heart", "Healthy adult human heart."),
    # Mouse lung
    ("lung", "mouse"):         ModelSelection("Mouse_Lung.pkl",       "Mouse Lung",       "Mouse lung cell atlas."),
    # Mouse brain
    ("brain", "mouse"):        ModelSelection("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
    ("hippocampus", "mouse"):  ModelSelection("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
    ("cortex", "mouse"):       ModelSelection("Mouse_Isocortex_Hippocampus.pkl", "Mouse Brain", "Mouse isocortex and hippocampus."),
}

def select_model(tissue: str, organism: str) -> ModelSelection:
    """Select a CellTypist model based on tissue type and organism.

    Performs a case-insensitive lookup against a curated table of
    (tissue, organism) → model mappings. Raises PipelineStepError if no
    match is found so the user is prompted to supply valid inputs rather
    than silently receiving results from a mismatched model.

    This function has a stable interface — Phase 3 will replace the lookup
    table with an LLM call but the signature and return type will not change.

    Args:
        tissue: Tissue type (e.g. 'blood', 'lung', 'brain').
        organism: Source organism (e.g. 'human', 'mouse').

    Returns:
        ModelSelection with model_name, display_name, and description.

    Raises:
        PipelineStepError: If no model is available for the given
            tissue and organism combination.
    """
    key = (tissue.strip().lower(), organism.strip().lower())
    selection = _MODEL_LOOKUP.get(key)

    if selection is None:
        supported = sorted(
            f"{t} / {o}" for t, o in _MODEL_LOOKUP
        )
        raise PipelineStepError(
            "annotate",
            f"No CellTypist model found for tissue='{tissue}' organism='{organism}'. "
            f"Supported combinations: {', '.join(supported)}.",
        )

    logger.info(
        "Selected model '%s' for tissue='%s' organism='%s'.",
        selection.model_name, tissue, organism,
    )
    return selection


# ---------------------------------------------------------------------------
# Model cache
# ---------------------------------------------------------------------------

# In-memory cache: model_name -> loaded Model object.
# Populated on first use; subsequent requests reuse the loaded model.
# Phase 3 extension point: replace this dict with a ModelCache class that
# supports eviction, pre-warming, or remote storage without changing callers.
_model_cache: dict[str, celltypist.models.Model] = {}


def _get_model(model_name: str) -> celltypist.models.Model:
    """Return a loaded CellTypist model, loading it on first use.

    Args:
        model_name: CellTypist model filename (e.g. 'Immune_All_Low.pkl').

    Returns:
        Loaded celltypist.models.Model instance.

    Raises:
        PipelineStepError: If the model file cannot be loaded.
    """
    if model_name not in _model_cache:
        try:
            _model_cache[model_name] = celltypist.models.Model.load(model=model_name)
            logger.info("Loaded and cached CellTypist model '%s'.", model_name)
        except Exception as e:
            raise PipelineStepError(
                "annotate", f"Failed to load CellTypist model '{model_name}': {e}"
            ) from e
    else:
        logger.info("Using cached CellTypist model '%s'.", model_name)

    return _model_cache[model_name]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def run_marker_genes(adata: ad.AnnData, n_genes: int = 25) -> ad.AnnData:
    """Compute per-cluster marker genes using rank_genes_groups.

    Uses the Wilcoxon rank-sum test, comparing each cluster against all
    others. Results are stored in adata.uns['rank_genes_groups'].

    Args:
        adata: Clustered AnnData object with 'leiden' in obs.
        n_genes: Number of top marker genes to compute per cluster.

    Returns:
        AnnData object with rank_genes_groups results stored in uns.

    Raises:
        PipelineStepError: If cluster labels are missing or the test fails.
    """
    if "leiden" not in adata.obs.columns:
        raise PipelineStepError(
            "annotate",
            "'leiden' column not found in adata.obs. Run run_cluster() first.",
        )

    try:
        sc.tl.rank_genes_groups(
            adata, groupby="leiden", method="wilcoxon", n_genes=n_genes
        )
    except Exception as e:
        raise PipelineStepError("annotate", f"rank_genes_groups failed: {e}") from e

    return adata


def run_celltypist(adata: ad.AnnData, model: str = "Immune_All_Low.pkl") -> ad.AnnData:
    """Annotate cell types using CellTypist.

    Expects log1p-normalized counts (target sum 10,000) as produced by
    run_normalize(). Majority-vote prediction is used to assign a single
    cell type label per Leiden cluster.

    Args:
        adata: AnnData object with normalized counts and 'leiden' in obs.
        model: CellTypist model filename to use for annotation.

    Returns:
        AnnData object with 'celltypist_cell_type' added to obs.

    Raises:
        PipelineStepError: If the model cannot be loaded or annotation fails.
    """
    if "leiden" not in adata.obs.columns:
        raise PipelineStepError(
            "annotate",
            "'leiden' column not found in adata.obs. Run run_cluster() first.",
        )

    ct_model = _get_model(model)

    # Use the full log-normalized matrix stored in adata.raw so CellTypist
    # sees all genes, not just the HVG subset used for clustering.
    adata_full = adata.raw.to_adata()
    adata_full.obs["leiden"] = adata.obs["leiden"]

    try:
        predictions = celltypist.annotate(
            adata_full, model=ct_model, majority_voting=True, over_clustering="leiden"
        )
        adata.obs["celltypist_cell_type"] = predictions.predicted_labels[
            "majority_voting"
        ]
    except Exception as e:
        raise PipelineStepError("annotate", f"CellTypist annotation failed: {e}") from e

    return adata
