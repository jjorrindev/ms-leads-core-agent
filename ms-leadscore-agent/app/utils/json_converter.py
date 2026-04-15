"""
Conversor de formato JSON a texto plano para el agente
Soporta el formato específico con conversacion_id, lead_id, chat_id, etc.
"""
from typing import Dict, List, Union, Optional
from datetime import datetime

class JSONToTextConverter:
    """Convierte conversaciones en formato JSON a texto plano"""
    
    @staticmethod
    def convertir_a_texto(conversacion_json: Union[Dict, List]) -> str:
        """
        Convierte diferentes formatos JSON a texto plano
        
        Args:
            conversacion_json: JSON en diferentes formatos
        
        Returns:
            Texto plano formateado para el agente
        """
        # Si ya es texto, devolver directamente
        if isinstance(conversacion_json, str):
            return conversacion_json
        
        # Detectar formato específico con mensajes
        if "mensajes" in conversacion_json:
            return JSONToTextConverter._convertir_formato_estandar(conversacion_json["mensajes"])
        
        # Si es una lista directa de mensajes
        if isinstance(conversacion_json, list):
            return JSONToTextConverter._convertir_lista_mensajes(conversacion_json)
        
        # Si no se reconoce, intentar convertir como está
        return str(conversacion_json)
    
    @staticmethod
    def _convertir_formato_estandar(mensajes: List[Dict]) -> str:
        """Convierte formato estándar de mensajes"""
        lineas = []
        for msg in sorted(mensajes, key=lambda x: x.get('orden', 0)):
            rol = msg.get('rol', '').upper()
            # Normalizar roles
            if rol in ['AGENTE', 'VENDEDOR', 'ASISTENTE', 'VENDEDOR']:
                rol = 'VENDEDOR'
            elif rol in ['CLIENTE', 'PROSPECTO', 'USUARIO', 'LEAD']:
                rol = 'LEAD'
            
            contenido = msg.get('mensaje', msg.get('texto', ''))
            if rol and contenido:
                lineas.append(f"{rol}: {contenido}")
        
        return "\n".join(lineas)
    
    @staticmethod
    def _convertir_lista_mensajes(mensajes: List[Dict]) -> str:
        """Convierte una lista directa de mensajes"""
        lineas = []
        for msg in mensajes:
            rol = msg.get('rol', msg.get('speaker', '')).upper()
            if rol not in ['VENDEDOR', 'LEAD']:
                rol = 'VENDEDOR' if 'agent' in rol.lower() else 'LEAD'
            
            contenido = msg.get('mensaje', msg.get('texto', msg.get('content', '')))
            if contenido:
                lineas.append(f"{rol}: {contenido}")
        
        return "\n".join(lineas)
    
    @staticmethod
    def extraer_metadata(conversacion_json: Dict) -> Dict:
        """Extrae metadata del JSON incluyendo nuevos campos"""
        metadata = {
            "conversacion_id": conversacion_json.get("conversacion_id"),
            "lead_id": conversacion_json.get("lead_id"),
            "chat_id": conversacion_json.get("chat_id"),
            "canal": conversacion_json.get("canal"),
            "fecha": conversacion_json.get("fecha"),
        }
        
        # Agregar metadata adicional si existe
        if "metadata" in conversacion_json and isinstance(conversacion_json["metadata"], dict):
            metadata.update(conversacion_json["metadata"])
        
        # Filtrar valores None
        return {k: v for k, v in metadata.items() if v is not None}
    
    @staticmethod
    def extraer_identificadores(conversacion_json: Dict) -> Dict:
        """Extrae los identificadores principales del JSON"""
        return {
            "conversacion_id": conversacion_json.get("conversacion_id"),
            "lead_id": conversacion_json.get("lead_id"),
            "chat_id": conversacion_json.get("chat_id")
        }