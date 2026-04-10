export interface QCParams {
  min_genes: number
  max_genes: number
  max_pct_mt: number
  min_cells: number
}

export interface PipelineParams {
  tissue: string
  organism: string
  qc: QCParams
  n_top_genes: number
  n_pcs: number
  n_neighbors: number
  leiden_resolution: number
  n_marker_genes: number
}

export interface CellMetadata {
  cell_id: string
  leiden_cluster: string
  celltypist_cell_type: string
  umap_x: number
  umap_y: number
}

export interface MarkerGene {
  gene: string
  cluster: string
  score: number
  log_fold_change: number
  pval_adj: number
}

export interface ClusterSummary {
  cluster_id: string
  celltypist_label: string
}

export interface PipelineResult {
  n_cells_input: number
  n_cells_after_qc: number
  n_hvgs: number
  n_clusters: number
  model_display_name: string
  model_description: string
  cluster_summaries: ClusterSummary[]
  cells: CellMetadata[]
  marker_genes: MarkerGene[]
}
