import json
import logging
import re
from typing import Dict, List, Optional
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
    score_total: int
    nivel: str
    desglose: Dict[str, int]
    ajustes: Dict[str, int]
    interpretacion: str
    proxima_accion: str
    frases_clave_detectadas: List[str]

class LeadScoringAgent:
    """Agente especializado en calificación de leads"""
    
    def __init__(self):
        self.modelo = "phi3:mini"
        self.api_base = "http://localhost:11434"
        
        self.evaluador = self._crear_agente_evaluador()
        
        self.app_name = "lead_scoring_app"
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name=self.app_name,
            agent=self.evaluador,
            session_service=self.session_service
        )
        
        self.keywords = self._cargar_keywords()
    
    def _cargar_keywords(self) -> Dict:
        """Carga palabras clave para análisis rápido"""
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
    
    async def evaluar_conversacion(self, conversacion: str) -> LeadEvaluation:
        """Evalúa una conversación y devuelve la puntuación del lead"""
        try:
            if not conversacion or len(conversacion.strip()) < 10:
                return self._evaluacion_fallback("Conversación demasiado corta o vacía")
            
            prompt = f"""
## CONVERSACIÓN A ANALIZAR

{conversacion}

Analiza esta conversación y devuelve el JSON con la evaluación.
"""
            
            session = await self.session_service.create_session(
                app_name=self.app_name,
                user_id="evaluador",
                state={}
            )
            
            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
            
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
            
            evaluacion = self._parsear_respuesta(respuesta_texto)
            
            if not evaluacion:
                logger.warning("Falló parseo de JSON, usando método de respaldo")
                evaluacion = self._evaluacion_fallback_con_analisis(conversacion)
            
            return evaluacion
            
        except Exception as e:
            logger.error(f"Error en evaluación: {e}")
            return self._evaluacion_fallback(f"Error: {str(e)}")
    
    def _parsear_respuesta(self, texto: str) -> Optional[LeadEvaluation]:
        """Extrae y parsea el JSON de la respuesta del agente"""
        try:
            # Extraer el bloque JSON más externo de forma robusta
            start = texto.find('{')
            end = texto.rfind('}') + 1
            if start != -1 and end > start:
                data = json.loads(texto[start:end])
                
                score_total = self._safe_int(data.get("score_total", 0))
                
                desglose_raw = data.get("desglose", {})
                desglose = {
                    key: self._safe_int(value) 
                    for key, value in desglose_raw.items()
                }
                
                for key in ["interes_explicito", "urgencia", "presupuesto_autoridad", 
                           "calidad_respuestas", "senales_compra"]:
                    if key not in desglose:
                        desglose[key] = 0
                
                ajustes_raw = data.get("ajustes", {})
                ajustes = {
                    key: self._safe_int(value)
                    for key, value in ajustes_raw.items()
                }
                
                return LeadEvaluation(
                    score_total=score_total,
                    nivel=str(data.get("nivel", "MUY_BAJO")),
                    desglose=desglose,
                    ajustes=ajustes,
                    interpretacion=str(data.get("interpretacion", "")),
                    proxima_accion=str(data.get("proxima_accion", "")),
                    frases_clave_detectadas=data.get("frases_clave_detectadas", [])
                )
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
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
                if cleaned and cleaned != '-':
                    return int(cleaned)
                return default
            return default
        except (ValueError, TypeError):
            return default
    
    def _evaluacion_fallback(self, error_msg: str) -> LeadEvaluation:
        """Evaluación de respaldo cuando hay error"""
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
            interpretacion=f"Error en análisis: {error_msg}",
            proxima_accion="Revisar la conversación manualmente",
            frases_clave_detectadas=[]
        )
    
    def _evaluacion_fallback_con_analisis(self, conversacion: str) -> LeadEvaluation:
        """Evaluación de respaldo usando análisis de keywords"""
        conversacion_lower = conversacion.lower()
        
        score = 0
        desglose = {k: 0 for k in ["interes_explicito", "urgencia", "presupuesto_autoridad", 
                                    "calidad_respuestas", "senales_compra"]}
        
        if any(kw in conversacion_lower for kw in self.keywords["interes_alto"]):
            desglose["interes_explicito"] = 20
            score += 20
        
        if any(kw in conversacion_lower for kw in self.keywords["urgencia_alta"]):
            desglose["urgencia"] = 20
            score += 20
        elif any(kw in conversacion_lower for kw in self.keywords["urgencia_media"]):
            desglose["urgencia"] = 15
            score += 15
        
        if any(kw in conversacion_lower for kw in self.keywords["autoridad"]):
            desglose["presupuesto_autoridad"] = 20
            score += 20
        
        if any(kw in conversacion_lower for kw in self.keywords["senales_compra"]):
            desglose["senales_compra"] = 20
            score += 20
        
        lineas_lead = [l for l in conversacion.split('\n') if l.startswith("LEAD")]
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
        
        penalizaciones = 0
        if any(kw in conversacion_lower for kw in self.keywords["objeciones"]):
            penalizaciones += 10
        
        bonificaciones = 0
        if any(kw in conversacion_lower for kw in self.keywords["entusiasmo"]):
            bonificaciones += 5
        
        if conversacion.strip().startswith("LEAD"):
            bonificaciones += 10
        
        score_total = max(0, min(100, score - penalizaciones + bonificaciones))
        
        if score_total >= 70:
            nivel = "ALTO"
        elif score_total >= 50:
            nivel = "MEDIO"
        elif score_total >= 25:
            nivel = "BAJO"
        else:
            nivel = "MUY_BAJO"
        
        return LeadEvaluation(
            score_total=score_total,
            nivel=nivel,
            desglose=desglose,
            ajustes={"penalizaciones": penalizaciones, "bonificaciones": bonificaciones},
            interpretacion=f"Evaluación automática por keywords. Score: {score_total}",
            proxima_accion=self._recomendar_accion(nivel),
            frases_clave_detectadas=self._detectar_frases_clave(conversacion)
        )
    
    def _detectar_frases_clave(self, conversacion: str) -> List[str]:
        """Detecta frases clave en la conversación"""
        frases = []
        for categoria, palabras in self.keywords.items():
            for palabra in palabras:
                if palabra.lower() in conversacion.lower():
                    frases.append(palabra)
        return list(set(frases))[:10]
    
    def _recomendar_accion(self, nivel: str) -> str:
        """Recomienda acción según el nivel del lead"""
        acciones = {
            "ALTO": "🔥 Lead caliente - Contactar inmediatamente, priorizar seguimiento",
            "MEDIO": "📊 Lead tibio - Enviar más información y agendar llamada",
            "BAJO": "📧 Lead frío - Nutrir con newsletter, no priorizar",
            "MUY_BAJO": "⏸️ Lead descartado - No invertir más tiempo",
            "ERROR": "⚠️ Revisar manualmente la conversación"
        }
        return acciones.get(nivel, acciones["MUY_BAJO"])