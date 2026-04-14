from functools import lru_cache
from app.services.scoring_service import ScoringService
from app.agent import LeadScoringAgent


@lru_cache(maxsize=1)
def get_agent():
    """Obtiene o crea la instancia del agente (singleton)"""
    return LeadScoringAgent()


@lru_cache(maxsize=1)
def get_scoring_service():
    """Obtiene o crea la instancia del servicio de scoring"""
    return ScoringService(get_agent(), cache_client=None)