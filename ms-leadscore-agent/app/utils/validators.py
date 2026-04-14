import re
from typing import Tuple, Optional

# NOTA: Las funciones de este módulo no están siendo importadas por ningún otro módulo del proyecto.
# La validación de formato ya está cubierta por el @field_validator en app/models.py.
# Considerar eliminar este archivo o integrarlo al pipeline de validación si se necesita en el futuro.

def validar_formato_conversacion(conversacion: str) -> Tuple[bool, Optional[str]]:
    """
    Valida el formato de la conversación.
    Retorna (es_valido, mensaje_error)
    """
    if not conversacion or len(conversacion.strip()) < 10:
        return False, "La conversación es demasiado corta"
    
    lineas = conversacion.strip().split('\n')
    tiene_rol = False
    
    for linea in lineas:
        if re.match(r'^(VENDEDOR|LEAD|AGENTE|CLIENTE):', linea.strip(), re.IGNORECASE):
            tiene_rol = True
            break
    
    if not tiene_rol:
        return False, "La conversación debe incluir roles como VENDEDOR: o LEAD:"
    
    return True, None

def extraer_roles(conversacion: str) -> dict:
    """Extrae estadísticas de roles en la conversación"""
    lineas = conversacion.strip().split('\n')
    
    vendedor_count = 0
    lead_count = 0
    
    for linea in lineas:
        if linea.strip().upper().startswith('VENDEDOR'):
            vendedor_count += 1
        elif linea.strip().upper().startswith('LEAD'):
            lead_count += 1
    
    return {
        "mensajes_vendedor": vendedor_count,
        "mensajes_lead": lead_count,
        "total_mensajes": vendedor_count + lead_count
    }