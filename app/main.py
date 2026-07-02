from fastapi import FastAPI
from app.api.routes_uniprot import router as uniprot_router
from app.api.routes_delivery import router as delivery_router
from app.api.routes_manual import router as manual_router
from app.api.routes_pipeline import router as pipeline_router

app = FastAPI(title="QRETIX Target Pipeline")

app.include_router(uniprot_router)
app.include_router(delivery_router)
app.include_router(manual_router)
app.include_router(pipeline_router)

@app.get("/health")
def health():
    return {"status": "ok"}