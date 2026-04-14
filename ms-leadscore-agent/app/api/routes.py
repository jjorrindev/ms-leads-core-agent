from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
import logging
from datetime import datetime, timezone

from app.models import (
    ConversacionRequest, 
    LeadEvaluationResponse,
    ConversacionBatchRequest,
    BatchEvaluationResponse,
    HealthResponse,
    MetricasResponse
)
from app.api.dependencies import get_scoring_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/evaluar", response_model=LeadEvaluationResponse, status_code=200)
async def evaluar_conversacion(
    request: ConversacionRequest,
    scoring_service = Depends(get_scoring_service)
):
    """
    Evalúa una conversación individual y devuelve la puntuación del lead.
    
    - **conversacion**: Texto completo de la conversación con roles (VENDEDOR/LEAD)
    - **metadata**: Datos adicionales opcionales para tracking
    """
    try:
        resultado = await scoring_service.evaluar_conversacion(
            request.conversacion,
            request.metadata
        )
        return resultado
    except Exception as e:
        logger.error(f"Error en endpoint /evaluar: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluar/batch", response_model=BatchEvaluationResponse)
async def evaluar_batch(
    request: ConversacionBatchRequest,
    scoring_service = Depends(get_scoring_service)
):
    """
    Evalúa múltiples conversaciones en lote.
    
    - **conversaciones**: Lista de conversaciones a evaluar
    - **generar_reporte**: Si es True, genera un reporte Markdown
    """
    try:
        conversaciones_list = [
            {"conversacion": conv.conversacion, "metadata": conv.metadata}
            for conv in request.conversaciones
        ]
        
        resultados = await scoring_service.evaluar_batch(conversaciones_list)
        
        exitosos = [r for r in resultados if "error" not in r]
        
        resumen = {
            "ALTO": sum(1 for r in exitosos if r.get("nivel") == "ALTO"),
            "MEDIO": sum(1 for r in exitosos if r.get("nivel") == "MEDIO"),
            "BAJO": sum(1 for r in exitosos if r.get("nivel") == "BAJO"),
            "MUY_BAJO": sum(1 for r in exitosos if r.get("nivel") == "MUY_BAJO"),
            "ERROR": len(resultados) - len(exitosos)
        }
        
        reporte_md = None
        if request.generar_reporte:
            reporte_md = _generar_reporte_markdown(resultados, resumen)
        
        return BatchEvaluationResponse(
            total_procesados=len(resultados),
            resultados=exitosos,
            resumen=resumen,
            reporte_markdown=reporte_md
        )
        
    except Exception as e:
        logger.error(f"Error en batch evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metricas", response_model=MetricasResponse)
async def obtener_metricas(
    scoring_service = Depends(get_scoring_service)
):
    """Obtiene métricas del servicio de calificación"""
    try:
        metricas = scoring_service.obtener_metricas()
        return metricas
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del microservicio"""
    return HealthResponse(
        status="healthy",
        modelo="phi3:mini",
        timestamp=datetime.now(timezone.utc)
    )

def _generar_reporte_markdown(resultados: List[Dict], resumen: Dict) -> str:
    """Genera reporte en Markdown"""
    reporte = "# 📊 Reporte de Calificación de Leads\n\n"
    reporte += f"**Fecha**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n"
    reporte += f"## Resumen\n"
    reporte += f"- Total evaluaciones: {len(resultados)}\n"
    reporte += f"- 🔥 Leads ALTO: {resumen['ALTO']}\n"
    reporte += f"- 📊 Leads MEDIO: {resumen['MEDIO']}\n"
    reporte += f"- ❄️ Leads BAJO: {resumen['BAJO']}\n"
    reporte += f"- ⚠️ Errores: {resumen['ERROR']}\n\n"
    
    reporte += "## Detalle por Lead\n\n"
    for i, resultado in enumerate(resultados, 1):
        if "error" not in resultado:
            reporte += f"### Lead {i}\n"
            reporte += f"- **Score**: {resultado['score_total']}/100\n"
            reporte += f"- **Nivel**: {resultado['nivel']}\n"
            reporte += f"- **Próxima acción**: {resultado['proxima_accion']}\n"
            reporte += f"- **Interpretación**: {resultado['interpretacion']}\n\n"
        else:
            reporte += f"### Lead {i} - ERROR\n"
            reporte += f"- **Error**: {resultado['error']}\n\n"
    
    return reporte