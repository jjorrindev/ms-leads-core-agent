from functools import lru_cache
from app.services.scoring_service import ScoringService
from app.agent import LeadScoringAgent

_agent_instance = None
_scoring_service_instance = None

@lru_cache()
def get_agent():
    """Obtiene o crea la instancia del agente (singleton) con force_ia=True"""
    global _agent_instance
    if _agent_instance is None:
        # force_ia=True fuerza el uso del agente IA, no usa fallback
        _agent_instance = LeadScoringAgent(force_ia=True)
    return _agent_instance

@lru_cache()
def get_scoring_service():
    """Obtiene o crea la instancia del servicio de scoring"""
    global _scoring_service_instance
    if _scoring_service_instance is None:
        agent = get_agent()
        _scoring_service_instance = ScoringService(agent, cache_client=None)
    return _scoring_service_instance