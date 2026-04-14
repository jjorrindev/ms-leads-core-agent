import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import router
from app.models import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Maneja el ciclo de vida de la aplicación"""
    logger.info("🚀 Iniciando Lead Scoring Microservice...")
    logger.info("✅ Servicio listo para recibir peticiones")
    yield
    logger.info("👋 Cerrando Lead Scoring Microservice...")

app = FastAPI(
    title="Lead Scoring Microservice",
    description="Microservicio para calificación automática de leads usando IA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS: no se puede usar allow_origins=["*"] con allow_credentials=True (viola la spec CORS).
# Definir los orígenes permitidos explícitamente o usar la variable de entorno ALLOWED_ORIGINS.
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

Instrumentator().instrument(app).expose(app, endpoint="/api/metrics")

app.include_router(router, prefix="/api/v1", tags=["lead-scoring"])

@app.get("/", response_model=dict)
async def root():
    """Endpoint raíz"""
    return {
        "service": "Lead Scoring Microservice",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/v1/health"
    }

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check simple"""
    return HealthResponse(
        status="healthy",
        modelo="phi3:mini",
        timestamp=datetime.now(timezone.utc)
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )