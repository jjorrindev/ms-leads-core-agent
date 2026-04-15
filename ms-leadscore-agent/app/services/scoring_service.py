import asyncio
import logging
import json
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import time
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class ScoringService:
    """Servicio para manejar la lógica de calificación con caché y métricas"""
    
    def __init__(self, evaluador, cache_client=None):
        self.evaluador = evaluador
        self.cache = cache_client
        self.metricas = {
            "total_evaluaciones": 0,
            "evaluaciones_por_nivel": defaultdict(int),
            "tiempos_respuesta": [],
            "cache_hits": 0,
            "cache_misses": 0
        }
    
    async def evaluar_conversacion(self, conversacion: str, metadata: Dict = None, score_actual: int = None) -> Dict:
        """Evalúa una conversación individual con caché, metadata y score_actual"""
        start_time = time.time()
        
        # Incluir score_actual y metadata en la clave de caché
        cache_key = self._generar_cache_key(conversacion, score_actual, metadata)
        
        # Intentar obtener del caché
        if self.cache:
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                self.metricas["cache_hits"] += 1
                logger.info(f"Cache hit para conversación")
                return cached_result
        
        self.metricas["cache_misses"] += 1
        
        try:
            # Evaluar la conversación
            evaluacion = await self._evaluar_con_retry(conversacion, score_actual, metadata)
            
            # Actualizar métricas
            self.metricas["total_evaluaciones"] += 1
            self.metricas["evaluaciones_por_nivel"][evaluacion.nivel] += 1
            
            # Calcular tiempo de respuesta
            elapsed_time = (time.time() - start_time) * 1000
            self.metricas["tiempos_respuesta"].append(elapsed_time)
            
            # Mantener solo últimos 1000 tiempos
            if len(self.metricas["tiempos_respuesta"]) > 1000:
                self.metricas["tiempos_respuesta"] = self.metricas["tiempos_respuesta"][-1000:]
            
            # Preparar respuesta
            response = self._evaluacion_to_dict(evaluacion, metadata)
            
            # Guardar en caché
            if self.cache:
                await self._save_to_cache(cache_key, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error evaluando conversación: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _evaluar_con_retry(self, conversacion: str, score_actual: int = None, metadata: Dict = None):
        """Evalúa con reintentos automáticos"""
        return await self.evaluador.evaluar_conversacion(conversacion, score_actual, metadata)
    
    async def evaluar_batch(self, conversaciones: List[Dict]) -> List[Dict]:
        """Evalúa múltiples conversaciones concurrentemente"""
        tasks = [
            self.evaluar_conversacion(
                conv["conversacion"], 
                conv.get("metadata"),
                conv.get("score_actual")
            )
            for conv in conversaciones
        ]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Procesar resultados
        processed_results = []
        for resultado in resultados:
            if isinstance(resultado, Exception):
                processed_results.append({"error": str(resultado)})
            else:
                processed_results.append(resultado)
        
        return processed_results
    
    def obtener_metricas(self) -> Dict:
        """Obtiene métricas actuales del servicio"""
        tiempo_promedio = sum(self.metricas["tiempos_respuesta"]) / len(self.metricas["tiempos_respuesta"]) if self.metricas["tiempos_respuesta"] else 0
        
        total_cache = self.metricas["cache_hits"] + self.metricas["cache_misses"]
        cache_hit_rate = self.metricas["cache_hits"] / total_cache if total_cache > 0 else 0
        
        return {
            "total_evaluaciones": self.metricas["total_evaluaciones"],
            "evaluaciones_por_nivel": dict(self.metricas["evaluaciones_por_nivel"]),
            "tiempo_promedio_respuesta_ms": round(tiempo_promedio, 2),
            "cache_hit_rate": round(cache_hit_rate, 2),
            "cache_hits": self.metricas["cache_hits"],
            "cache_misses": self.metricas["cache_misses"]
        }
    
    def _generar_cache_key(self, conversacion: str, score_actual: int = None, metadata: Dict = None) -> str:
        """Genera clave de caché para la conversación incluyendo score_actual y metadata relevante"""
        import hashlib
        key_data = conversacion
        if score_actual is not None:
            key_data += f"|score:{score_actual}"
        if metadata:
            # Incluir identificadores en la clave de caché
            conv_id = metadata.get("conversacion_id")
            lead_id = metadata.get("lead_id")
            chat_id = metadata.get("chat_id")
            if conv_id:
                key_data += f"|conv_id:{conv_id}"
            if lead_id:
                key_data += f"|lead_id:{lead_id}"
            if chat_id:
                key_data += f"|chat_id:{chat_id}"
        return f"lead_scoring:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Obtiene del caché (Redis)"""
        if not self.cache:
            return None
        try:
            data = await self.cache.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Error leyendo caché: {e}")
        return None
    
    async def _save_to_cache(self, key: str, value: Dict, ttl: int = 3600):
        """Guarda en caché con TTL de 1 hora"""
        if not self.cache:
            return
        try:
            await self.cache.set(key, json.dumps(value), ex=ttl)
        except Exception as e:
            logger.warning(f"Error guardando en caché: {e}")
    
    def _evaluacion_to_dict(self, evaluacion, metadata: Dict = None) -> Dict:
        """Convierte objeto LeadEvaluation a dict incluyendo nuevos campos y metadata"""
        # Calcular diferencia
        diferencia = None
        if evaluacion.score_final is not None and evaluacion.score_actual is not None:
            diferencia = evaluacion.score_final - evaluacion.score_actual
        
        result = {
            "score_total": evaluacion.score_total,
            "score_anterior": evaluacion.score_actual,
            "score_nuevo": evaluacion.score_final if evaluacion.score_final is not None else evaluacion.score_total,
            "diferencia": diferencia,
            "nivel": evaluacion.nivel,
            "desglose": evaluacion.desglose,
            "ajustes": evaluacion.ajustes,
            "interpretacion": evaluacion.interpretacion,
            "proxima_accion": evaluacion.proxima_accion,
            "frases_clave_detectadas": evaluacion.frases_clave_detectadas,
            "timestamp": datetime.now().isoformat()
        }
        
        # Agregar metadata si existe
        if metadata:
            if metadata.get("conversacion_id"):
                result["conversacion_id"] = metadata["conversacion_id"]
            if metadata.get("lead_id"):
                result["lead_id"] = metadata["lead_id"]
            if metadata.get("chat_id"):
                result["chat_id"] = metadata["chat_id"]
        
        return result