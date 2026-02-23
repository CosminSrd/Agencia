"""
Configuración de Redis para caché distribuida
"""

import redis
import json
import logging
from datetime import timedelta
from functools import wraps
import pickle
import hashlib

logger = logging.getLogger(__name__)


class RedisCache:
    """ Gestiona caché distribuida con Redis"""
    
    def __init__(self, host='localhost', port=6379, db=0, password=None, decode_responses=False):
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=decode_responses,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"✅ Redis conectado: {host}:{port}")
            self.available = True
            
        except Exception as e:
            logger.warning(f"⚠️ Redis no disponible: {e}. Usando fallback.")
            self.redis_client = None
            self.available = False
    
    def get(self, key):
        """Obtiene valor de caché"""
        if not self.available:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                logger.debug(f"🎯 Cache HIT: {key}")
                return pickle.loads(value)
            else:
                logger.debug(f"❌ Cache MISS: {key}")
                return None
        except Exception as e:
            logger.error(f"Error obteniendo de cache: {e}")
            return None
    
    def set(self, key, value, ttl=300):
        """Guarda valor en caché
        
        Args:
            key: Clave del cache
            value: Valor a guardar (cualquier tipo serializable)
            ttl: Tiempo de vida en segundos (default 5 minutos)
        """
        if not self.available:
            return False
        
        try:
            serialized = pickle.dumps(value)
            self.redis_client.setex(key, ttl, serialized)
            logger.debug(f"💾 Cache SET: {key} (TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Error guardando en cache: {e}")
            return False
    
    def delete(self, key):
        """Elimina valor de caché"""
        if not self.available:
            return False
        
        try:
            self.redis_client.delete(key)
            logger.debug(f"🗑️ Cache DEL: {key}")
            return True
        except Exception as e:
            logger.error(f"Error eliminando de cache: {e}")
            return False
    
    def delete_pattern(self, pattern):
        """Elimina todas las claves que coinciden con un patrón"""
        if not self.available:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                count = self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cache DEL pattern '{pattern}': {count} keys")
                return count
            return 0
        except Exception as e:
            logger.error(f"Error eliminando pattern de cache: {e}")
            return 0
    
    def exists(self, key):
        """Verifica si existe una clave"""
        if not self.available:
            return False
        
        try:
            return self.redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Error verificando existencia: {e}")
            return False
    
    def clear_all(self):
        """Limpia toda la caché (¡usar con precaución!)"""
        if not self.available:
            return False
        
        try:
            self.redis_client.flushdb()
            logger.warning("⚠️ Cache completamente limpiada (FLUSHDB)")
            return True
        except Exception as e:
            logger.error(f"Error limpiando cache: {e}")
            return False
    
    def get_stats(self):
        """Obtiene estadísticas de Redis"""
        if not self.available:
            return {'available': False}
        
        try:
            info = self.redis_client.info()
            return {
                'available': True,
                'used_memory_human': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'total_commands_processed': info.get('total_commands_processed'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'hit_rate': self._calculate_hit_rate(info)
            }
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
            return {'available': False, 'error': str(e)}
    
    def _calculate_hit_rate(self, info):
        """Calcula el hit rate del caché"""
        hits = info.get('keyspace_hits', 0)
        misses = info.get('keyspace_misses', 0)
        total = hits + misses
        
        if total == 0:
            return 0.0
        
        return round((hits / total) * 100, 2)


def cache_key_generator(*args, **kwargs):
    """Genera una clave única para caché basada en argumentos"""
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_string = ":".join(key_parts)
    
    # Hash para claves largas
    if len(key_string) > 200:
        key_string = hashlib.md5(key_string.encode()).hexdigest()
    
    return key_string


def cached(ttl=300, prefix='cache'):
    """Decorador para cachear resultados de funciones
    
    Usage:
        @cached(ttl=600, prefix='vuelos')
        def buscar_vuelos(origen, destino):
            # ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de caché
            cache_key = f"{prefix}:{func.__name__}:{cache_key_generator(*args, **kwargs)}"
            
            # Intentar obtener de caché
            cached_value = redis_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Ejecutar función
            result = func(*args, **kwargs)
            
            # Guardar en caché
            redis_cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    return decorator


# ==========================================
# FUNCIONES ESPECÍFICAS PARA LA APLICACIÓN
# ==========================================

def cache_flight_search(origen, destino, fecha, adultos, ninos, bebes, clase, results, ttl=300):
    """Cachea resultados de búsqueda de vuelos"""
    key = f"vuelos:{origen}:{destino}:{fecha}:{adultos}:{ninos}:{bebes}:{clase}"
    redis_cache.set(key, results, ttl)


def get_cached_flight_search(origen, destino, fecha, adultos, ninos, bebes, clase):
    """Obtiene resultados cacheados de búsqueda de vuelos"""
    key = f"vuelos:{origen}:{destino}:{fecha}:{adultos}:{ninos}:{bebes}:{clase}"
    return redis_cache.get(key)


def cache_airport_suggestions(query, suggestions, ttl=3600):
    """Cachea sugerencias de aeropuertos (TTL largo, datos estáticos)"""
    key = f"airports:{query.lower()}"
    redis_cache.set(key, suggestions, ttl)


def get_cached_airport_suggestions(query):
    """Obtiene sugerencias cacheadas de aeropuertos"""
    key = f"airports:{query.lower()}"
    return redis_cache.get(key)


def clear_flight_cache():
    """Limpia toda la caché de vuelos"""
    return redis_cache.delete_pattern("vuelos:*")


def clear_airport_cache():
    """Limpia caché de aeropuertos"""
    return redis_cache.delete_pattern("airports:*")


# ==========================================
# INICIALIZACIÓN
# ==========================================

import os

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

redis_cache = RedisCache(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD
)
