"""
Cache package
"""

from .redis_cache import (
    redis_cache,
    RedisCache,
    cached,
    cache_flight_search,
    get_cached_flight_search,
    cache_airport_suggestions,
    get_cached_airport_suggestions,
    clear_flight_cache,
    clear_airport_cache
)

__all__ = [
    'redis_cache',
    'RedisCache',
    'cached',
    'cache_flight_search',
    'get_cached_flight_search',
    'cache_airport_suggestions',
    'get_cached_airport_suggestions',
    'clear_flight_cache',
    'clear_airport_cache'
]
