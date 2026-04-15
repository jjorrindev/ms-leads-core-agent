from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Dict, Union
import logging
from datetime import datetime

from app.models import (
    ConversacionTextRequest,
    ConversacionJSONRequest,
    ConversacionBatchRequest,
    LeadEvaluationResponse,
    BatchEvaluationResponse,
    HealthResponse,
    MetricasResponse
)
from app.api.dependencies import get_scoring_service
from app.utils.json_converter import JSONToTextConverter

logger = logging.getLogger(__name__)
router = APIRouter()

# ============ ENDPOINT ORIGINAL (TEXTO PLANO) - MANTENIDO POR COMPATIBILIDAD ============
@router.post("/evaluar", response_model=LeadEvaluationResponse, status_code=200)
async def evaluar_conversacion_texto(
    request: ConversacionTextRequest,
    scoring_service = Depends(get_scoring_service)
):
    """
    Evalúa una conversación en formato texto plano.
    Este endpoint se mantiene por compatibilidad con versiones anteriores.
    
    Formato esperado:
    {
        "conversacion": "VENDEDOR: Hola\\nLEAD: Me interesa",
        "metadata": {"fuente": "api"}
    }
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

# ============ NUEVO ENDPOINT: JSON ESTRUCTURADO CON FORMATO ESPECÍFICO ============
@router.post("/evaluar/json", response_model=LeadEvaluationResponse, status_code=200)
async def evaluar_conversacion_json(
    request: ConversacionJSONRequest,
    scoring_service = Depends(get_scoring_service)
):
    """
    Evalúa una conversación en formato JSON estructurado según la especificación.
    
    Formato esperado:
    {
        "conversacion_id": "conv_20240414_001",
        "lead_id": "LEAD_12345",
        "chat_id": "CHAT_12345",
        "fecha": "2024-04-14T10:30:00Z",
        "canal": "chatbot",
        "mensajes": [
            {"orden": 1, "timestamp": "...", "rol": "VENDEDOR", "mensaje": "Hola"},
            {"orden": 2, "timestamp": "...", "rol": "LEAD", "mensaje": "Me interesa"}
        ],
        "metadata": {"fuente": "api_externa", "campaña": "ventas2024"}
    }
    """
    try:
        # Convertir JSON a texto plano
        conversacion_texto = JSONToTextConverter.convertir_a_texto(request.dict())
        
        # Extraer metadata incluyendo todos los campos
        metadata = {
            "conversacion_id": request.conversacion_id,
            "lead_id": request.lead_id,
            "chat_id": request.chat_id,
            "canal": request.canal,
            "fecha": request.fecha.isoformat() if request.fecha else None,
            **request.metadata
        }
        
        # Filtrar valores None
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        logger.info(f"Procesando conversación {request.conversacion_id} para lead {request.lead_id}")
        
        # Evaluar
        resultado = await scoring_service.evaluar_conversacion(
            conversacion_texto,
            metadata
        )
        
        # Agregar identificadores a la respuesta
        resultado["conversacion_id"] = request.conversacion_id
        resultado["lead_id"] = request.lead_id
        resultado["chat_id"] = request.chat_id
        
        return resultado
        
    except Exception as e:
        logger.error(f"Error en endpoint /evaluar/json: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ ENDPOINT PARA BATCH CON JSON ============
@router.post("/evaluar/batch", response_model=BatchEvaluationResponse)
async def evaluar_batch_json(
    request: ConversacionBatchRequest,
    background_tasks: BackgroundTasks,
    scoring_service = Depends(get_scoring_service)
):
    """
    Evalúa múltiples conversaciones en formato JSON.
    
    Formato esperado:
    {
        "conversaciones": [
            {
                "conversacion_id": "conv_001",
                "lead_id": "LEAD_001",
                "mensajes": [...]
            },
            {
                "conversacion_id": "conv_002", 
                "lead_id": "LEAD_002",
                "mensajes": [...]
            }
        ],
        "generar_reporte": true
    }
    """
    try:
        resultados = []
        
        for conv in request.conversaciones:
            # Convertir cada conversación
            conversacion_texto = JSONToTextConverter.convertir_a_texto(conv.dict())
            
            # Extraer metadata
            metadata = {
                "conversacion_id": conv.conversacion_id,
                "lead_id": conv.lead_id,
                "chat_id": conv.chat_id,
                "canal": conv.canal,
                "fecha": conv.fecha.isoformat() if conv.fecha else None,
                **conv.metadata
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            # Evaluar
            resultado = await scoring_service.evaluar_conversacion(
                conversacion_texto,
                metadata
            )
            
            # Agregar identificadores
            resultado["conversacion_id"] = conv.conversacion_id
            resultado["lead_id"] = conv.lead_id
            resultado["chat_id"] = conv.chat_id
            
            resultados.append(resultado)
        
        # Generar resumen
        resumen = {
            "ALTO": sum(1 for r in resultados if r.get("nivel") == "ALTO"),
            "MEDIO": sum(1 for r in resultados if r.get("nivel") == "MEDIO"),
            "BAJO": sum(1 for r in resultados if r.get("nivel") == "BAJO"),
            "MUY_BAJO": sum(1 for r in resultados if r.get("nivel") == "MUY_BAJO"),
            "ERROR": sum(1 for r in resultados if r.get("nivel") == "ERROR")
        }
        
        # Generar reporte si se solicita
        reporte_md = None
        if request.generar_reporte:
            reporte_md = await _generar_reporte_markdown(resultados, resumen)
        
        return BatchEvaluationResponse(
            total_procesados=len(resultados),
            resultados=resultados,
            resumen=resumen,
            reporte_markdown=reporte_md
        )
        
    except Exception as e:
        logger.error(f"Error en batch json: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ ENDPOINT UNIVERSAL (AUTO-DETECTA FORMATO) ============
@router.post("/evaluar/universal", response_model=LeadEvaluationResponse, status_code=200)
async def evaluar_conversacion_universal(
    request: Dict,
    scoring_service = Depends(get_scoring_service)
):
    """
    Endpoint universal que detecta automáticamente el formato de la conversación.
    Acepta texto plano o JSON estructurado.
    """
    try:
        # Detectar formato automáticamente
        if "conversacion" in request and isinstance(request["conversacion"], str):
            # Formato texto plano
            conversacion_texto = request["conversacion"]
            metadata = request.get("metadata", {})
            resultado = await scoring_service.evaluar_conversacion(conversacion_texto, metadata)
        
        elif "mensajes" in request:
            # Formato JSON estándar
            conversacion_texto = JSONToTextConverter.convertir_a_texto(request)
            metadata = {
                "conversacion_id": request.get("conversacion_id"),
                "lead_id": request.get("lead_id"),
                "chat_id": request.get("chat_id"),
                "canal": request.get("canal"),
                "fecha": request.get("fecha"),
                **request.get("metadata", {})
            }
            metadata = {k: v for k, v in metadata.items() if v is not None}
            
            resultado = await scoring_service.evaluar_conversacion(conversacion_texto, metadata)
            
            # Agregar identificadores a la respuesta
            if request.get("conversacion_id"):
                resultado["conversacion_id"] = request["conversacion_id"]
            if request.get("lead_id"):
                resultado["lead_id"] = request["lead_id"]
            if request.get("chat_id"):
                resultado["chat_id"] = request["chat_id"]
        
        else:
            raise HTTPException(
                status_code=400, 
                detail="Formato no reconocido. Use 'conversacion' (texto) o 'mensajes' (JSON)"
            )
        
        return resultado
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint /evaluar/universal: {e}")
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
        timestamp=datetime.now()
    )

async def _generar_reporte_markdown(resultados: List[Dict], resumen: Dict) -> str:
    """Genera reporte en Markdown"""
    reporte = "# 📊 Reporte de Calificación de Leads\n\n"
    reporte += f"**Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    reporte += f"## Resumen\n"
    reporte += f"- Total evaluaciones: {len(resultados)}\n"
    reporte += f"- 🔥 Leads ALTO: {resumen['ALTO']}\n"
    reporte += f"- 📊 Leads MEDIO: {resumen['MEDIO']}\n"
    reporte += f"- ❄️ Leads BAJO: {resumen['BAJO']}\n"
    reporte += f"- ⚠️ Errores: {resumen['ERROR']}\n\n"
    
    reporte += "## Detalle por Lead\n\n"
    for resultado in resultados:
        reporte += f"### Conversación: {resultado.get('conversacion_id', 'N/A')}\n"
        reporte += f"- **Lead ID**: {resultado.get('lead_id', 'N/A')}\n"
        reporte += f"- **Chat ID**: {resultado.get('chat_id', 'N/A')}\n"
        reporte += f"- **Score**: {resultado.get('score_total', 'N/A')}/100\n"
        reporte += f"- **Nivel**: {resultado.get('nivel', 'N/A')}\n"
        reporte += f"- **Próxima acción**: {resultado.get('proxima_accion', 'N/A')}\n"
        reporte += f"- **Interpretación**: {resultado.get('interpretacion', 'N/A')}\n\n"
    
    return reporte