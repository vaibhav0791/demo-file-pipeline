from pydantic import BaseModel, Field
from typing import List

class UniProtBatchRequest(BaseModel):
    disease_id: str = Field(..., examples=["breast_cancer"])
    gene_symbols: List[str] = Field(..., min_length=1, max_length=100, examples=[["TP53", "BRCA1", "EGFR"]])
    requested_by: str = Field(default="vaibhav")

class GeneIngestResult(BaseModel):
    gene_symbol: str
    inserted: int
    skipped: int
    total_fetched: int
    status: str = "ok"

class UniProtBatchResponse(BaseModel):
    run_id: int
    disease_id: str
    requested_by: str
    total_genes: int
    summary: dict
    results: List[GeneIngestResult]