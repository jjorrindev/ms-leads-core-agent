import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """Test endpoint de health"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root_endpoint():
    """Test endpoint raíz"""
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()

def test_evaluar_conversacion():
    """Test evaluación de conversación"""
    conversacion_test = """
    VENDEDOR: Hola, ¿te interesa nuestro producto?
    LEAD: Sí, estoy muy interesado. Necesito esto urgentemente para esta semana.
    """
    
    response = client.post(
        "/api/v1/evaluar",
        json={"conversacion": conversacion_test}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "score_total" in data
    assert "nivel" in data
    assert 0 <= data["score_total"] <= 100

def test_evaluar_conversacion_invalida():
    """Test con conversación inválida"""
    response = client.post(
        "/api/v1/evaluar",
        json={"conversacion": "Hola"}  # Muy corta
    )
    
    assert response.status_code == 422

def test_metricas_endpoint():
    """Test endpoint de métricas"""
    response = client.get("/api/v1/metricas")
    assert response.status_code == 200
    data = response.json()
    assert "total_evaluaciones" in data

def test_batch_evaluation():
    """Test evaluación por lote"""
    batch_data = {
        "conversaciones": [
            {"conversacion": "VENDEDOR: Hola\nLEAD: Me interesa"},
            {"conversacion": "VENDEDOR: Hola\nLEAD: No gracias"}
        ],
        "generar_reporte": False
    }
    
    response = client.post("/api/v1/evaluar/batch", json=batch_data)
    assert response.status_code == 200
    data = response.json()
    assert "total_procesados" in data
    assert "resumen" in data