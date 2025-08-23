from __future__ import annotations
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import health, ingest, query

app = FastAPI(
    title="RAG Microservice", 
    version="0.1.0",
    description="Simple RAG pipeline with FastAPI and Qdrant"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(query.router)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "RAG Microservice RSM", 
        "health": "/health"
    }