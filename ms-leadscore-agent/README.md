# Lead Scoring Microservice

Microservicio para calificación automática de leads usando IA con Google ADK y Ollama.

## 🚀 Características

- **Evaluación automática** de conversaciones de ventas
- **API REST** completa con endpoints documentados
- **Procesamiento por lotes** para múltiples conversaciones
- **Caché con Redis** para mejorar rendimiento
- **Métricas Prometheus** para monitoreo
- **Dockerizado** para fácil despliegue
- **Alta disponibilidad** con reintentos automáticos

## 📦 Instalación Rápida

### Con Docker (recomendado)

```bash
# Clonar repositorio
git clone <repo-url>
cd lead-scoring-microservice

# Configurar variables de entorno
cp .env.example .env

# Iniciar servicios
cd docker
docker-compose up -d

# Descargar modelo en Ollama
docker exec -it ollama ollama pull phi3:mini

# Verificar que todo funciona
curl http://localhost:8000/health