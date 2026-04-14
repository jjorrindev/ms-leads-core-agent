from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum

class NivelLead(str, Enum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAJO = "BAJO"
    MUY_BAJO = "MUY_BAJO"
    ERROR = "ERROR"

class ConversacionRequest(BaseModel):
    """Request para evaluar una conversación"""
    conversacion: str = Field(..., min_length=10, description="Texto de la conversación")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Metadatos adicionales")
    
    @field_validator('conversacion')
    @classmethod
    def validar_formato(cls, v):
        """Valida que la conversación tenga formato básico"""
        if not any(rol in v.upper() for rol in ['VENDEDOR', 'LEAD', 'AGENTE', 'CLIENTE']):
            raise ValueError('La conversación debe incluir roles como VENDEDOR o LEAD')
        return v

class ConversacionBatchRequest(BaseModel):
    """Request para evaluar múltiples conversaciones"""
    conversaciones: List[ConversacionRequest] = Field(..., max_length=50, description="Máximo 50 conversaciones por lote")
    generar_reporte: bool = False

class LeadEvaluationResponse(BaseModel):
    """Response con la evaluación completa"""
    score_total: int
    nivel: NivelLead
    desglose: Dict[str, int]
    ajustes: Dict[str, int]
    interpretacion: str
    proxima_accion: str
    frases_clave_detectadas: List[str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BatchEvaluationResponse(BaseModel):
    """Response para evaluaciones por lote"""
    total_procesados: int
    resultados: List[Dict]
    resumen: Dict[str, int]
    reporte_markdown: Optional[str] = None

class HealthResponse(BaseModel):
    """Response para health check"""
    status: str
    modelo: str
    version: str = "1.0.0"
    timestamp: datetime

class MetricasResponse(BaseModel):
    """Response con métricas del sistema"""
    total_evaluaciones: int
    evaluaciones_por_nivel: Dict[str, int]
    tiempo_promedio_respuesta_ms: float
    cache_hit_rate: float
    cache_hits: int
    cache_misses: int