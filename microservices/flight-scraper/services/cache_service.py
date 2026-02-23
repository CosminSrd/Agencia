"""
Cache Service
Servicio de caché con Redis
"""

import redis
import json
import logging
import hashlib
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheService:
    """Servicio de caché con Redis"""
    
    def __init__(self, redis_url: str):
        """
        Inicializa el servicio de caché
        
        Args:
            redis_url: URL de conexión a Redis
        """
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            self.redis_client.ping()
            logger.info("Cache service connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def generate_key(self, prefix: str, data: dict) -> str:
        """
        Genera una clave única para caché
        
        Args:
            prefix: Prefijo de la clave
            data: Datos para generar hash
        
        Returns:
            Clave de caché
        """
        # Serializar datos y generar hash
        data_str = json.dumps(data, sort_keys=True)
        hash_value = hashlib.md5(data_str.encode()).hexdigest()
        
        return f"flight-scraper:{prefix}:{hash_value}"
    
    def get(self, key: str) -> Optional[Any]:
        """
        Obtiene un valor de caché
        
        Args:
            key: Clave de caché
        
        Returns:
            Valor deserializado o None si no existe
        """
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Guarda un valor en caché
        
        Args:
            key: Clave de caché
            value: Valor a guardar
            ttl: Tiempo de vida en segundos (default: 5 minutos)
        
        Returns:
            True si se guardó correctamente
        """
        try:
            serialized = json.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Elimina una clave de caché
        
        Args:
            key: Clave a eliminar
        
        Returns:
            True si se eliminó
        """
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """
        Elimina todas las claves que coincidan con un patrón
        
        Args:
            pattern: Patrón de búsqueda (ej: "flight-scraper:search:*")
        
        Returns:
            Número de claves eliminadas
        """
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")
            return 0
    
    def health_check(self) -> bool:
        """
        Verifica que Redis esté disponible
        
        Returns:
            True si Redis responde
        """
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def get_stats(self) -> dict:
        """
        Obtiene estadísticas de caché
        
        Returns:
            Dict con estadísticas
        """
        try:
            info = self.redis_client.info('stats')
            return {
                'cache_hits': info.get('keyspace_hits', 0),
                'cache_misses': info.get('keyspace_misses', 0),
                'total_keys': self.redis_client.dbsize()
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
