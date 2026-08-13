from fastapi import FastAPI
from app.database import init_pool, close_pool, get_connection
from app.routers import accounts, bulk_upload

app = FastAPI(title="Demat Account Lifecycle & Client Master API")

@app.on_event("startup")
def startup_event():
    init_pool()

@app.on_event("shutdown")
def shutdown_event():
    close_pool()

@app.get("/health")
def health_check():
    return {"status": "healthy"}

app.include_router(accounts.router)
app.include_router(accounts.router)
app.include_router(bulk_upload.router)