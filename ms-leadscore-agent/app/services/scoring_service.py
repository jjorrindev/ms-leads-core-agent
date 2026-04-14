import asyncio
import hashlib
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional
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
    
    async def evaluar_conversacion(self, conversacion: str, metadata: Optional[Dict] = None) -> Dict:
        """Evalúa una conversación individual con caché"""
        start_time = time.time()
        
        cache_key = self._generar_cache_key(conversacion)
        
        if self.cache:
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                self.metricas["cache_hits"] += 1
                logger.info(f"Cache hit para conversación")
                return cached_result
        
        self.metricas["cache_misses"] += 1
        
        try:
            evaluacion = await self._evaluar_con_retry(conversacion)
            
            self.metricas["total_evaluaciones"] += 1
            self.metricas["evaluaciones_por_nivel"][evaluacion.nivel] += 1
            
            elapsed_time = (time.time() - start_time) * 1000
            self.metricas["tiempos_respuesta"].append(elapsed_time)
            
            if len(self.metricas["tiempos_respuesta"]) > 1000:
                self.metricas["tiempos_respuesta"] = self.metricas["tiempos_respuesta"][-1000:]
            
            response = self._evaluacion_to_dict(evaluacion)
            
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
    async def _evaluar_con_retry(self, conversacion: str):
        """Evalúa con reintentos automáticos"""
        return await self.evaluador.evaluar_conversacion(conversacion)
    
    async def evaluar_batch(self, conversaciones: List[Dict]) -> List[Dict]:
        """Evalúa múltiples conversaciones concurrentemente"""
        tasks = [
            self.evaluar_conversacion(conv["conversacion"], conv.get("metadata"))
            for conv in conversaciones
        ]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
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
    
    def _generar_cache_key(self, conversacion: str) -> str:
        """Genera clave de caché para la conversación"""
        return f"lead_scoring:{hashlib.md5(conversacion.encode()).hexdigest()}"
    
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
    
    def _evaluacion_to_dict(self, evaluacion) -> Dict:
        """Convierte objeto LeadEvaluation a dict"""
        return {
            "score_total": evaluacion.score_total,
            "nivel": evaluacion.nivel,
            "desglose": evaluacion.desglose,
            "ajustes": evaluacion.ajustes,
            "interpretacion": evaluacion.interpretacion,
            "proxima_accion": evaluacion.proxima_accion,
            "frases_clave_detectadas": evaluacion.frases_clave_detectadas,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }