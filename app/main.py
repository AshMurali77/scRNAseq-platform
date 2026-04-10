from fastapi import FastAPI, UploadFile, File
from app.models.schemas import PipelineParams, PipelineResult

app = FastAPI(title="scRNA-seq Annotation Platform")


@app.post("/analyze", response_model=PipelineResult)
async def analyze(
    file: UploadFile = File(...),
    params: PipelineParams = ...,
) -> PipelineResult:
    """Accept a .h5ad upload, run the full preprocessing pipeline, and return results."""
    pass
