from fastapi import FastAPI
from app.api.routes_uniprot import router as uniprot_router
from app.api.routes_pipeline import router as pipeline_router
from app.api.routes_master import router as master_router

app = FastAPI(title="QRETIX Target Pipeline", debug=True)

app.include_router(uniprot_router)
app.include_router(pipeline_router)
app.include_router(master_router)

@app.get("/health")
def health():
    return {"status": "ok"}