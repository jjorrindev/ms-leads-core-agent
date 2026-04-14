import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.agent import LeadScoringAgent, LeadEvaluation


# ─── Tests de lógica pura (sin dependencia de Ollama/ADK) ────────────────────

def test_fallback_analysis():
    """Test análisis de respaldo con keywords — no requiere Ollama"""
    with patch.object(LeadScoringAgent, '_crear_agente_evaluador', return_value=MagicMock()), \
         patch.object(LeadScoringAgent, '__init__', lambda self: None):
        agent = LeadScoringAgent.__new__(LeadScoringAgent)
        agent.keywords = agent._cargar_keywords = LeadScoringAgent._cargar_keywords
        agent.keywords = LeadScoringAgent._cargar_keywords(agent)

    conversacion = "LEAD: Estoy interesado, necesito comprar urgente"
    resultado = agent._evaluacion_fallback_con_analisis(conversacion)
    assert resultado.score_total > 0
    assert resultado.nivel in ["ALTO", "MEDIO", "BAJO", "MUY_BAJO"]


def test_deteccion_frases_clave():
    """Test detección de frases clave — no requiere Ollama"""
    with patch.object(LeadScoringAgent, '_crear_agente_evaluador', return_value=MagicMock()), \
         patch.object(LeadScoringAgent, '__init__', lambda self: None):
        agent = LeadScoringAgent.__new__(LeadScoringAgent)
        agent.keywords = LeadScoringAgent._cargar_keywords(agent)

    conversacion = "Estoy muy interesado en el precio, lo necesito urgente"
    frases = agent._detectar_frases_clave(conversacion)
    assert len(frases) > 0


def test_safe_int():
    """Test conversión segura de enteros — no requiere Ollama"""
    with patch.object(LeadScoringAgent, '_crear_agente_evaluador', return_value=MagicMock()), \
         patch.object(LeadScoringAgent, '__init__', lambda self: None):
        agent = LeadScoringAgent.__new__(LeadScoringAgent)

    assert agent._safe_int(42) == 42
    assert agent._safe_int("15") == 15
    assert agent._safe_int("-") == 0
    assert agent._safe_int(None) == 0
    assert agent._safe_int("abc") == 0


# ─── Tests de integración (requieren Ollama corriendo) ───────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_initialization():
    """[INTEGRACIÓN] Test inicialización del agente — requiere Ollama en localhost:11434"""
    agent = LeadScoringAgent()
    assert agent is not None
    assert agent.modelo == "phi3:mini"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluacion_conversacion_valida():
    """[INTEGRACIÓN] Test evaluación de conversación válida — requiere Ollama en localhost:11434"""
    agent = LeadScoringAgent()
    conversacion = """
    VENDEDOR: Hola, ¿cómo estás?
    LEAD: Muy bien, gracias. Estoy buscando un producto como el tuyo.
    """
    resultado = await agent.evaluar_conversacion(conversacion)
    assert resultado is not None
    assert hasattr(resultado, 'score_total')
    assert hasattr(resultado, 'nivel')


@pytest.mark.asyncio
@pytest.mark.integration
async def test_evaluacion_conversacion_vacia():
    """[INTEGRACIÓN] Test con conversación vacía — requiere Ollama en localhost:11434"""
    agent = LeadScoringAgent()
    resultado = await agent.evaluar_conversacion("")
    assert resultado.nivel == "ERROR"