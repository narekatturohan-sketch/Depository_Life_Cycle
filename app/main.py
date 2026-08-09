from fastapi import FastAPI
from app.database import init_pool, close_pool, get_connection

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