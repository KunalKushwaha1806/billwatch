"""
BillWatch — AI Revenue Recovery Agent
FastAPI application entry point.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables
from app.routes import batch, pipeline, signals, actions, audit, metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    create_tables()
    yield


app = FastAPI(
    title="BillWatch — AI Revenue Recovery Agent",
    description=(
        "Detects revenue at risk from failed payments and abandoned checkouts, "
        "diagnoses root causes, decides on bounded recovery actions with explicit "
        "stopping rules, and executes simulated recovery with a full audit trail."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(batch.router, tags=["Batch"])
app.include_router(pipeline.router, tags=["Pipeline"])
app.include_router(signals.router, tags=["Signals"])
app.include_router(actions.router, tags=["Actions"])
app.include_router(audit.router, tags=["Audit"])
app.include_router(metrics.router, tags=["Metrics"])


@app.get("/")
def root():
    return {
        "name": "BillWatch — AI Revenue Recovery Agent",
        "version": "1.0.0",
        "endpoints": [
            "POST /batch/load",
            "POST /pipeline/run",
            "GET /signals",
            "GET /actions",
            "GET /audit/{entity_id}",
            "GET /metrics/summary",
        ],
    }
