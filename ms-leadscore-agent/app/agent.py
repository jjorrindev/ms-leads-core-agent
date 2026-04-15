import asyncio
import json
import logging
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LeadEvaluation:
    """Estructura para almacenar la evaluación del lead"""
    # Campos sin valor por defecto (obligatorios)
    nivel: str
    desglose: Dict[str, int]
    ajustes: Dict[str, int]
    interpretacion: str
    proxima_accion: str
    frases_clave_detectadas: List[str]
    score_total: int
    
    # Campos con valor por defecto (opcionales) - deben ir al final
    score_actual: Optional[int] = None
    score_final: Optional[int] = None

class LeadScoringAgent:
    """Agente especializado en calificación de leads - Versión que fuerza uso de IA"""
    
    def __init__(self, force_ia: bool = True):
        """
        Inicializa el agente
        
        Args:
            force_ia: Si es True, fuerza el uso del agente IA y no usa fallback
        """
        self.modelo = "phi3:mini"
        self.api_base = "http://localhost:11434"
        self.force_ia = force_ia  # Forzar uso de IA
        
        self.evaluador = self._crear_agente_evaluador()
        
        self.app_name = "lead_scoring_app"
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name=self.app_name,
            agent=self.evaluador,
            session_service=self.session_service
        )
        
        self.keywords = self._cargar_keywords()
        logger.info(f"LeadScoringAgent inicializado con force_ia={self.force_ia}")
    
    def _cargar_keywords(self) -> Dict:
        """Carga palabras clave para análisis rápido (solo usado si force_ia=False)"""
        return {
            "interes_alto": ["precio", "costo", "disponibilidad", "cuánto cuesta", "interesado", "quiero", "necesito"],
            "urgencia_alta": ["urgente", "hoy", "mañana", "esta semana", "inmediato", "cuanto antes"],
            "urgencia_media": ["pronto", "próximos días", "esta semana"],
            "autoridad": ["yo decido", "soy el dueño", "tengo presupuesto", "soy el responsable"],
            "senales_compra": ["empezar", "contrato", "garantía", "cuándo podemos", "cómo es el proceso"],
            "objeciones": ["no me interesa", "déjame en paz", "muy caro", "no tengo tiempo"],
            "entusiasmo": ["😊", "👍", "🎯", "excelente", "genial", "perfecto", "!"]
        }
    
    def _crear_agente_evaluador(self) -> Agent:
        """Crea el agente con la plantilla de evaluación"""
        
        instruccion_completa = """
Actúa como un experto en calificación de leads basado en análisis conversacional.

Tu tarea es analizar una conversación entre un vendedor (nosotros) y un prospecto (lead), 
y asignar una puntuación del 0 al 100 que indique la probabilidad de que este lead se convierta en cliente.

## CRITERIOS DE EVALUACIÓN

Evalúa la conversación según estas 5 dimensiones (cada una suma hasta 20 puntos):

### 1. INTERÉS EXPLÍCITO (0-20 puntos)
- 20: El lead pregunta precios, tiempos de entrega, disponibilidad, o dice explícitamente "estoy interesado"
- 15: Pide información adicional, una demo o cotización
- 10: Responde positivamente pero sin preguntas concretas
- 5: Responde con monosílabos o evasivo
- 0: Ignora preguntas clave o cambia de tema

### 2. URGENCIA (0-20 puntos)
- 20: Menciona una fecha límite o necesidad inmediata ("esta semana", "mañana", "urgente")
- 15: Dice "pronto", "en los próximos días"
- 10: Menciona un plazo de semanas o meses
- 5: No hay mención de tiempo o dice "cuando pueda"
- 0: Dice "no tengo prisa" o "más adelante"

### 3. PRESUPUESTO Y AUTORIDAD (0-20 puntos)
- 20: Menciona presupuesto disponible Y confirma que es quien toma decisiones
- 15: Confirma tener presupuesto pero duda sobre autoridad
- 10: Pregunta precios pero no menciona presupuesto
- 5: Dice "tengo que consultar con mi jefe"
- 0: Evita hablar de presupuesto o dice "no tengo presupuesto"

### 4. CALIDAD DE LAS RESPUESTAS (0-20 puntos)
- 20: Responde preguntas con detalles, datos concretos, contexto
- 15: Responde completo pero sin mucho detalle
- 10: Responde justo lo que se pregunta, sin elaborar
- 5: Responde con evasivas o respuestas cortas
- 0: No responde preguntas directas

### 5. SEÑALES DE COMPRA (0-20 puntos)
- 20: Usa frases como "¿cuándo podemos empezar?", "¿cómo es el contrato?", "¿qué garantía tienen?"
- 15: Pide ver el producto/servicio en acción
- 10: Compara con competidores o pide referencias
- 5: Solo lee o mira pero no interactúa
- 0: Pone objeciones no relacionadas o se queja de precios sin fundamento

## REGLAS ADICIONALES

- RESTA -10 puntos si el lead dice "no me interesa", "déjame en paz", o bloquea/ignora el último mensaje
- RESTA -15 puntos si hay más de 3 mensajes seguidos del vendedor sin respuesta del lead
- SUMA +5 puntos si el lead usa emojis positivos (😊👍🎯) o signos de exclamación mostrando entusiasmo
- SUMA +10 puntos si el lead es quien inicia la conversación

## FORMATO DE RESPUESTA

Debes responder ÚNICAMENTE con un JSON válido en este formato:

{
  "score_total": 0,
  "nivel": "ALTO|MEDIO|BAJO|MUY_BAJO",
  "desglose": {
    "interes_explicito": 0,
    "urgencia": 0,
    "presupuesto_autoridad": 0,
    "calidad_respuestas": 0,
    "senales_compra": 0
  },
  "ajustes": {
    "penalizaciones": 0,
    "bonificaciones": 0
  },
  "interpretacion": "breve explicación de por qué se asignó este puntaje",
  "proxima_accion": "qué debería hacer el vendedor ahora",
  "frases_clave_detectadas": ["frase1", "frase2"]
}

Asegúrate de que el JSON sea válido y no incluir texto adicional fuera del JSON.
"""
        
        return Agent(
            name="lead_scorer",
            model=LiteLlm(model=f"ollama/{self.modelo}", api_base=self.api_base),
            instruction=instruccion_completa,
            description="Experto en calificación de leads conversacionales",
        )
    
    async def evaluar_conversacion(self, conversacion: str, score_actual: int = None, metadata: Dict = None) -> LeadEvaluation:
        """
        Evalúa una conversación usando el agente IA.
        
        Si force_ia=True, no usa fallback y lanza excepción si hay error.
        Si force_ia=False, usa fallback por keywords si es necesario.
        """
        try:
            # Validar conversación
            if not conversacion or len(conversacion.strip()) < 10:
                error_msg = f"Conversación demasiado corta o vacía (longitud: {len(conversacion) if conversacion else 0})"
                logger.error(error_msg)
                if self.force_ia:
                    raise ValueError(error_msg)
                return self._evaluacion_fallback(error_msg, score_actual)
            
            # Construir prompt incluyendo el score actual si existe
            prompt_base = f"""
## CONVERSACIÓN A ANALIZAR

{conversacion}
"""
            
            # Agregar metadata al prompt si existe
            if metadata:
                prompt_base += f"\n## METADATA DE LA CONVERSACIÓN\n"
                for key, value in metadata.items():
                    if value:
                        prompt_base += f"- {key}: {value}\n"
            
            if score_actual is not None:
                prompt_base += f"""

## CONTEXTO ADICIONAL
El lead tiene un puntaje actual de {score_actual}/100.
Por favor, considera este puntaje existente junto con el análisis de la nueva conversación
para determinar el puntaje total final. El puntaje final debe ser un promedio ponderado
que combine el puntaje histórico con la nueva evaluación (60% nueva evaluación, 40% puntaje histórico).
"""
            
            prompt_base += """

Analiza esta conversación y devuelve el JSON con la evaluación.
"""
            
            logger.info("Creando sesión para el agente IA...")
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id="evaluador",
                state={}
            )
            
            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt_base)]
            )
            
            logger.info("Ejecutando agente IA...")
            respuesta_texto = ""
            async for event in self.runner.run_async(
                user_id="evaluador",
                session_id=session.id,
                new_message=user_content
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            respuesta_texto += part.text
                
                if event.is_final_response():
                    break
            
            logger.info(f"Respuesta del agente IA recibida (longitud: {len(respuesta_texto)} caracteres)")
            
            # Parsear respuesta
            evaluacion = self._parsear_respuesta(respuesta_texto, score_actual)
            
            if not evaluacion:
                error_msg = "No se pudo parsear la respuesta del agente IA"
                logger.error(error_msg)
                logger.error(f"Respuesta recibida: {respuesta_texto[:500]}...")
                
                if self.force_ia:
                    raise ValueError(error_msg)
                else:
                    logger.warning("Usando método de respaldo por keywords")
                    evaluacion = self._evaluacion_fallback_con_analisis(conversacion, score_actual)
            
            return evaluacion
            
        except Exception as e:
            logger.error(f"Error en evaluación con IA: {e}")
            if self.force_ia:
                # Relanzar el error para que sea visible
                raise Exception(f"Error del agente IA: {str(e)}. Verifica que Ollama esté corriendo y el modelo phi3:mini esté disponible.")
            else:
                logger.warning("Usando método de respaldo por error")
                return self._evaluacion_fallback(f"Error: {str(e)}", score_actual)
    
    def _parsear_respuesta(self, texto: str, score_actual: int = None) -> LeadEvaluation:
        """Extrae y parsea el JSON de la respuesta del agente"""
        try:
            # Buscar JSON en la respuesta
            json_match = re.search(r'\{.*\}', texto, re.DOTALL)
            if not json_match:
                logger.error("No se encontró JSON en la respuesta")
                return None
            
            data = json.loads(json_match.group())
            
            score_nuevo = self._safe_int(data.get("score_total", 0))
            
            # Calcular score final considerando score_actual
            score_final = score_nuevo
            if score_actual is not None:
                # 60% nueva evaluación, 40% score histórico
                score_final = int((score_nuevo * 0.6) + (score_actual * 0.4))
                score_final = max(0, min(100, score_final))
            
            desglose_raw = data.get("desglose", {})
            desglose = {
                key: self._safe_int(value) 
                for key, value in desglose_raw.items()
            }
            
            # Asegurar que todas las claves existan
            for key in ["interes_explicito", "urgencia", "presupuesto_autoridad", 
                       "calidad_respuestas", "senales_compra"]:
                if key not in desglose:
                    desglose[key] = 0
            
            ajustes_raw = data.get("ajustes", {})
            ajustes = {
                key: self._safe_int(value)
                for key, value in ajustes_raw.items()
            }
            
            # Determinar nivel basado en score_final
            if score_final >= 70:
                nivel = "ALTO"
            elif score_final >= 50:
                nivel = "MEDIO"
            elif score_final >= 25:
                nivel = "BAJO"
            else:
                nivel = "MUY_BAJO"
            
            interpretacion = str(data.get("interpretacion", ""))
            # Marcar que esta evaluación proviene del agente IA
            if not interpretacion.startswith("[IA]"):
                interpretacion = f"[IA] {interpretacion}"
            
            return LeadEvaluation(
                score_total=score_nuevo,
                nivel=nivel,
                desglose=desglose,
                ajustes=ajustes,
                interpretacion=interpretacion,
                proxima_accion=str(data.get("proxima_accion", "")),
                frases_clave_detectadas=data.get("frases_clave_detectadas", []),
                score_actual=score_actual,
                score_final=score_final
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
            logger.error(f"Texto que causó error: {texto[:200]}...")
        except Exception as e:
            logger.error(f"Error procesando evaluación: {e}")
        return None
    
    def _safe_int(self, value, default=0) -> int:
        """Convierte cualquier valor a entero de forma segura"""
        try:
            if value is None:
                return default
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                cleaned = re.sub(r'[^\d-]', '', value)
                return int(cleaned) if cleaned else default
            return default
        except (ValueError, TypeError):
            return default
    
    def _evaluacion_fallback(self, error_msg: str, score_actual: int = None) -> LeadEvaluation:
        """Evaluación de respaldo cuando hay error (solo usado si force_ia=False)"""
        score_final = score_actual if score_actual is not None else 0
        return LeadEvaluation(
            score_total=0,
            nivel="ERROR",
            desglose={
                "interes_explicito": 0,
                "urgencia": 0,
                "presupuesto_autoridad": 0,
                "calidad_respuestas": 0,
                "senales_compra": 0
            },
            ajustes={"penalizaciones": 0, "bonificaciones": 0},
            interpretacion=f"[FALLBACK] Error en análisis: {error_msg}",
            proxima_accion="Revisar la conversación manualmente y verificar conexión con Ollama",
            frases_clave_detectadas=[],
            score_actual=score_actual,
            score_final=score_final
        )
    
    def _evaluacion_fallback_con_analisis(self, conversacion: str, score_actual: int = None) -> LeadEvaluation:
        """Evaluación de respaldo usando análisis de keywords (solo usado si force_ia=False)"""
        conversacion_lower = conversacion.lower()
        
        score = 0
        desglose = {k: 0 for k in ["interes_explicito", "urgencia", "presupuesto_autoridad", 
                                    "calidad_respuestas", "senales_compra"]}
        
        # Análisis de interés
        if any(kw in conversacion_lower for kw in self.keywords["interes_alto"]):
            desglose["interes_explicito"] = 20
            score += 20
        elif any(kw in conversacion_lower for kw in ["tal vez", "quizás", "puede ser"]):
            desglose["interes_explicito"] = 10
            score += 10
        
        # Análisis de urgencia
        if any(kw in conversacion_lower for kw in self.keywords["urgencia_alta"]):
            desglose["urgencia"] = 20
            score += 20
        elif any(kw in conversacion_lower for kw in self.keywords["urgencia_media"]):
            desglose["urgencia"] = 15
            score += 15
        
        # Análisis de autoridad y presupuesto
        if any(kw in conversacion_lower for kw in self.keywords["autoridad"]):
            if any(kw in conversacion_lower for kw in ["presupuesto", "$", "dólares", "euros"]):
                desglose["presupuesto_autoridad"] = 20
                score += 20
            else:
                desglose["presupuesto_autoridad"] = 15
                score += 15
        elif any(kw in conversacion_lower for kw in ["presupuesto", "$", "dólares", "euros"]):
            desglose["presupuesto_autoridad"] = 10
            score += 10
        
        # Análisis de señales de compra
        if any(kw in conversacion_lower for kw in self.keywords["senales_compra"]):
            desglose["senales_compra"] = 20
            score += 20
        
        # Calidad de respuestas (aproximado por longitud)
        lineas_lead = [l for l in conversacion.split('\n') if l.upper().startswith("LEAD")]
        if lineas_lead:
            longitud_promedio = sum(len(l) for l in lineas_lead) / len(lineas_lead)
            if longitud_promedio > 100:
                desglose["calidad_respuestas"] = 20
                score += 20
            elif longitud_promedio > 50:
                desglose["calidad_respuestas"] = 15
                score += 15
            elif longitud_promedio > 20:
                desglose["calidad_respuestas"] = 10
                score += 10
            else:
                desglose["calidad_respuestas"] = 5
                score += 5
        
        # Penalizaciones
        penalizaciones = 0
        if any(kw in conversacion_lower for kw in self.keywords["objeciones"]):
            penalizaciones += 10
        
        # Contar mensajes del vendedor sin respuesta
        lineas_vendedor = [l for l in conversacion.split('\n') if l.upper().startswith("VENDEDOR")]
        if len(lineas_vendedor) > 3:
            penalizaciones += 15
        
        # Bonificaciones
        bonificaciones = 0
        if any(kw in conversacion_lower for kw in self.keywords["entusiasmo"]):
            bonificaciones += 5
        
        # Bonus si el lead inicia la conversación
        if conversacion.strip().upper().startswith("LEAD"):
            bonificaciones += 10
        
        # Calcular score nuevo
        score_nuevo = max(0, min(100, score - penalizaciones + bonificaciones))
        
        # Calcular score final considerando score_actual
        score_final = score_nuevo
        if score_actual is not None:
            score_final = int((score_nuevo * 0.6) + (score_actual * 0.4))
            score_final = max(0, min(100, score_final))
        
        # Determinar nivel
        if score_final >= 70:
            nivel = "ALTO"
        elif score_final >= 50:
            nivel = "MEDIO"
        elif score_final >= 25:
            nivel = "BAJO"
        else:
            nivel = "MUY_BAJO"
        
        return LeadEvaluation(
            score_total=score_nuevo,
            nivel=nivel,
            desglose=desglose,
            ajustes={"penalizaciones": penalizaciones, "bonificaciones": bonificaciones},
            interpretacion=f"[FALLBACK-KEYWORDS] Evaluación automática por keywords. Score nuevo: {score_nuevo}, Score final: {score_final}",
            proxima_accion=self._recomendar_accion(nivel),
            frases_clave_detectadas=self._detectar_frases_clave(conversacion),
            score_actual=score_actual,
            score_final=score_final
        )
    
    def _detectar_frases_clave(self, conversacion: str) -> List[str]:
        """Detecta frases clave en la conversación"""
        frases = []
        for categoria, palabras in self.keywords.items():
            for palabra in palabras:
                if palabra.lower() in conversacion.lower():
                    frases.append(palabra)
        return list(set(frases[:10]))
    
    def _recomendar_accion(self, nivel: str) -> str:
        """Recomienda acción según el nivel del lead"""
        acciones = {
            "ALTO": "🔥 Lead caliente - Contactar inmediatamente, priorizar seguimiento",
            "MEDIO": "📊 Lead tibio - Enviar más información y agendar llamada",
            "BAJO": "📧 Lead frío - Nutrir con newsletter, no priorizar",
            "MUY_BAJO": "⏸️ Lead descartado - No invertir más tiempo",
            "ERROR": "⚠️ Revisar manualmente la conversación y verificar conexión con Ollama"
        }
        return acciones.get(nivel, acciones["MUY_BAJO"])