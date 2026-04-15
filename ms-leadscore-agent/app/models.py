from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum

class NivelLead(str, Enum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAJO = "BAJO"
    MUY_BAJO = "MUY_BAJO"
    ERROR = "ERROR"

class RolMensaje(str, Enum):
    VENDEDOR = "VENDEDOR"
    LEAD = "LEAD"
    AGENTE = "AGENTE"
    CLIENTE = "CLIENTE"

class MensajeJSON(BaseModel):
    """Modelo para un mensaje individual en formato JSON"""
    orden: int = Field(..., description="Orden del mensaje en la conversación")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp del mensaje")
    rol: str = Field(..., description="Rol del emisor (VENDEDOR/LEAD)")
    mensaje: str = Field(..., min_length=1, description="Contenido del mensaje")
    
    @validator('rol')
    def validar_rol(cls, v):
        rol_upper = v.upper()
        if rol_upper not in ['VENDEDOR', 'LEAD', 'AGENTE', 'CLIENTE']:
            raise ValueError(f'Rol no válido: {v}. Debe ser VENDEDOR o LEAD')
        return rol_upper

class ConversacionJSONRequest(BaseModel):
    """Request para evaluar conversación en formato JSON según especificación"""
    conversacion_id: str = Field(..., description="ID único de la conversación")
    lead_id: str = Field(..., description="ID del lead")
    chat_id: Optional[str] = Field(default=None, description="ID del chat")
    fecha: Optional[datetime] = Field(default=None, description="Fecha de la conversación")
    canal: Optional[str] = Field(default=None, description="Canal de la conversación")
    mensajes: List[MensajeJSON] = Field(..., min_items=1, description="Lista de mensajes")
    metadata: Optional[Dict] = Field(default={}, description="Metadatos adicionales")
    
    @validator('mensajes')
    def validar_mensajes(cls, v):
        if len(v) < 2:
            raise ValueError('La conversación debe tener al menos 2 mensajes')
        
        # Validar que haya al menos un mensaje de VENDEDOR y uno de LEAD
        roles = set(msg.rol.upper() for msg in v)
        if 'VENDEDOR' not in roles or 'LEAD' not in roles:
            raise ValueError('La conversación debe incluir mensajes de VENDEDOR y LEAD')
        
        return v

class ConversacionTextRequest(BaseModel):
    """Request para evaluar conversación en texto plano"""
    conversacion: str = Field(..., min_length=10, description="Texto de la conversación")
    metadata: Optional[Dict] = Field(default={}, description="Metadatos adicionales")
    
    @validator('conversacion')
    def validar_formato(cls, v):
        if not any(rol in v.upper() for rol in ['VENDEDOR', 'LEAD', 'AGENTE', 'CLIENTE']):
            raise ValueError('La conversación debe incluir roles como VENDEDOR o LEAD')
        return v

class ConversacionBatchRequest(BaseModel):
    """Request para evaluar múltiples conversaciones"""
    conversaciones: List[ConversacionJSONRequest]
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
    conversacion_id: Optional[str] = None
    lead_id: Optional[str] = None
    chat_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

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