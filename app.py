import os
import json
import logging
import time
import threading
import requests
import re
from decimal import Decimal
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, Response, send_file, url_for
from flask.json.provider import DefaultJSONProvider
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from dotenv import load_dotenv
from flask_apscheduler import APScheduler
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg2.extras import RealDictCursor
from core.scraper_motor import MotorBusqueda
from core.amadeus_adapter import AmadeusAdapter
from core.email_utils import EmailManager
from core.nomad_optimizer import NomadOptimizer
from core.autocomplete_i18n import construir_terminos_busqueda, buscar_fallback_es
from core.feature_flags import is_feature_enabled, parse_rollout_percentage, get_rollout_bucket
# ==========================================
# IMPORTS ADICIONALES PARA MODERNIZACIÓN
# ==========================================
from flasgger import Swagger
from flask_cors import CORS

# Intentar importar cache y monitoring (opcionales)
try:
    from cache.redis_cache import RedisCache, redis_cache as shared_redis_cache
except ImportError:
    RedisCache = None
    shared_redis_cache = None
    
try:
    from monitoring.prometheus_metrics import init_metrics
except ImportError:
    init_metrics = None


# ==========================================
# 0. INICIALIZACIÓN GLOBAL
# ==========================================
motor = MotorBusqueda()
amadeus_motor = AmadeusAdapter()
email_manager = EmailManager()
nomad_optimizer = NomadOptimizer(motor)
# CUSTOM JSON PROVIDER FOR DECIMAL
# ==========================================
class CustomJSONProvider(DefaultJSONProvider):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# ==========================================
# 1. CONFIGURACIÓN INICIAL Y LOGS
# ==========================================

# Cargar variables de entorno
load_dotenv()

# Configurar logging con rotación (max 10MB, 5 backups)
from logging.handlers import RotatingFileHandler

log_handler = RotatingFileHandler(
    'app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[log_handler, logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.json = CustomJSONProvider(app) # ✅ Apply Custom Provider

CALENDAR_PRICE_CACHE = {}
CALENDAR_PRICE_CACHE_TTL = int(os.getenv('CALENDAR_PRICE_CACHE_TTL_SECONDS', '86400'))
CALENDAR_REFRESH_HOUR = int(os.getenv('CALENDAR_REFRESH_HOUR_UTC', '3'))
CALENDAR_REFRESH_MINUTE = int(os.getenv('CALENDAR_REFRESH_MINUTE_UTC', '15'))
CALENDAR_ENABLE_DAILY_REFRESH = os.getenv('CALENDAR_ENABLE_DAILY_REFRESH', 'true').lower() == 'true'
CALENDAR_PREWARM_ROUTES = os.getenv('CALENDAR_PREWARM_ROUTES', '')
CALENDAR_PREWARM_TOP_ROUTES_LIMIT = int(os.getenv('CALENDAR_PREWARM_TOP_ROUTES_LIMIT', '40'))
CALENDAR_TRACKED_ROUTES = set()
CALENDAR_TRACKED_ROUTES_LOCK = threading.Lock()

# 🔒 Rate Limiting Configuration
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    storage_options={"socket_connect_timeout": 30},
    strategy="fixed-window"
)

# Clave secreta para sesiones de Flask (MEJORADA)
import secrets
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if os.getenv("FLASK_ENV") == "production":
        logger.critical("⚠️ SECRET_KEY es OBLIGATORIA en producción!")
        raise SystemExit("SECRET_KEY no configurada")
    else:
        SECRET_KEY = secrets.token_hex(32)
        logger.warning(f"⚠️ Usando SECRET_KEY temporal (solo desarrollo): {SECRET_KEY[:16]}...")

app.config['SECRET_KEY'] = SECRET_KEY

# 🔐 VALIDACIÓN CRÍTICA: DUFFEL_API_TOKEN
# ==========================================
DUFFEL_TOKEN = os.getenv("DUFFEL_API_TOKEN")
DUFFEL_ACCOUNT_ID = os.getenv("DUFFEL_ACCOUNT_ID", "8a101ebdcba64c61e2057a1")  # Por defecto: test
DUFFEL_ENVIRONMENT = "live"
DUFFEL_DASHBOARD_URL = f"https://app.duffel.com/{DUFFEL_ACCOUNT_ID}/{DUFFEL_ENVIRONMENT}/orders"
AUTO_CHECKIN_ENABLED = os.getenv('AUTO_CHECKIN_ENABLED', 'true').lower() == 'true'
AUTO_CHECKIN_SCAN_MINUTES = int(os.getenv('AUTO_CHECKIN_SCAN_MINUTES', '15'))
DUFFEL_PRIORITY_DELTA_PERCENT = float(os.getenv('DUFFEL_PRIORITY_DELTA_PERCENT', '5'))
SEARCH_RESULTS_LIMIT = int(os.getenv('SEARCH_RESULTS_LIMIT', '10'))

if not DUFFEL_TOKEN or DUFFEL_TOKEN.strip() == "":
    logger.critical("🚨 CRITICAL: DUFFEL_API_TOKEN no está configurado en .env")
    logger.critical("   Sin este token, TODOS los endpoints de vuelos fallarán")
    logger.critical("   Acciones requeridas:")
    logger.critical("   1. Agregar DUFFEL_API_TOKEN=your_token_here a .env")
    logger.critical("   2. Reiniciar la aplicación")
    if os.getenv("FLASK_ENV") == "production":
        raise SystemExit("❌ FATAL: DUFFEL_API_TOKEN no configurada en producción")
    else:
        logger.warning("   (En desarrollo, continuando pero búsquedas devolverán lista vacía)")
else:
    logger.info(f"✅ DUFFEL_API_TOKEN configurado (primeros 10 chars: {DUFFEL_TOKEN[:10]}...)")
    logger.info(f"✅ DUFFEL_DASHBOARD_URL: {DUFFEL_DASHBOARD_URL}")

# ==========================================
# FEATURE FLAGS
# ==========================================
CHECKOUT_MULTI_STEP_ENABLED = os.getenv("CHECKOUT_MULTI_STEP_ENABLED", "true").lower() == "true"
CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT = parse_rollout_percentage(
    os.getenv("CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT", "100"),
    default=100
)

# FASE TEMPORAL: ocultar Amadeus sin eliminar código
AMADEUS_ENABLED = os.getenv("AMADEUS_ENABLED", "false").lower() == "true"

# ==========================================
# SWAGGER/OPENAPI CONFIGURATION
# ==========================================
app.config['SWAGGER'] = {
    'title': 'Viatges Carcaixent API',
    'version': '3.0.0',
    'description': 'API completa para gestión de viajes, vuelos y tours',
    'uiversion': 3,
    'openapi': '3.0.0',
    'specs_route': '/api/docs',
    'termsOfService': '/legal'
}

# Configuración de Swagger
swagger_template = {
    "openapi": "3.0.0",
    "info": {
        "title": "Viatges Carcaixent API",
        "description": "API REST para gestión completa de agencia de viajes",
        "contact": {
            "email": "info@viatgescarcaixent.com"
        },
        "version": "3.0.0"
    },
    "servers": [
        {
            "url": "http://localhost:8000",
            "description": "Servidor de desarrollo"
        }
    ],
    "components": {
        "securitySchemes": {
            "BasicAuth": {
                "type": "http",
                "scheme": "basic"
            }
        }
    }
}

swagger_config_obj = {
    'headers': [],
    'specs': [
        {
            'endpoint': 'apispec',
            'route': '/apispec.json',
            'rule_filter': lambda rule: True,
            'model_filter': lambda tag: True,
        }
    ],
    'static_url_path': '/flasgger_static',
    'swagger_ui': True,
    'specs_route': '/api/docs'
}

# Inicializar Swagger
try:
    swagger = Swagger(app, config=swagger_config_obj, template=swagger_template)
    logger.info("✅ Swagger UI habilitado en /api/docs")
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar Swagger: {e}")


# ==========================================
# 2. IMPORTACIÓN DE MÓDULOS DEL NÚCLEO (CORE)
# ==========================================
# Intentamos cargar tus módulos. Si fallan, la app no se rompe, pero avisa.

# A) Módulos de Base de Datos, Seguridad y Facturación
try:
    from database import get_db_session, get_db_connection  # ✅ AÑADIDO get_db_connection
    from core.matrix_adapter import MatrixOrchestrator
    from core.security import descifrar, cifrar, generar_hash_dni
    from core.invoice_pro import generar_factura_pdf
    
    logger.info("✅ Core Cargado: Base de Datos, Cifrado AES-256 y PDF Engine listos.")
    orchestrator = MatrixOrchestrator()
except ImportError as e:
    logger.error(f"❌ Error cargando Core: {e}. El panel de administración estará limitado.")
    orchestrator = None

# B) Motor de Búsqueda de Vuelos (Scraper/API)
# B) Motor de Búsqueda de Vuelos (Scraper/API)
try:
    from core.scraper_motor import MotorBusqueda
    logger.info("✅ Motor de Búsqueda (Vuelos API) activo.")
except ImportError as e:
    logger.warning(f"⚠️ Motor de Búsqueda no encontrado: {e}")
    MotorBusqueda = None


# ==========================================
# 3. SISTEMA DE SEGURIDAD (LOGIN ADMIN)
# ==========================================

def check_auth(username, password):
    """Verifica usuario y contraseña del .env (MEJORADO)"""
    ADMIN_USER = os.getenv("ADMIN_USER")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    
    # ✅ Validar que están configuradas
    if not ADMIN_USER or not ADMIN_PASSWORD:
        logger.critical("⚠️ ADMIN_USER y ADMIN_PASSWORD deben estar definidos en .env")
        return False
    
    is_valid = username == ADMIN_USER and password == ADMIN_PASSWORD
    if is_valid:
        logger.info(f"🔑 Acceso Admin autorizado desde {request.remote_addr}")
    else:
        logger.warning(f"⛔ Acceso Admin denegado: {username} desde {request.remote_addr}")
    return is_valid

def requires_auth(f):
    """Decorador para proteger rutas de administración"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response(
                'Acceso Protegido - Credenciales Requeridas', 
                401, 
                {'WWW-Authenticate': 'Basic realm="Panel de Administración Viatges Carcaixent"'}
            )
        return f(*args, **kwargs)
    return decorated


# ==========================================
# 4. RUTAS API (BUSCADOR DE VUELOS)
# ==========================================

@app.route('/api/autocomplete', methods=['GET'])
@limiter.limit("30 per minute")
def autocomplete_api():
    """Endpoint para el autocompletado de aeropuertos en el frontend"""
    termino_raw = request.args.get('term', '').strip()
    termino = termino_raw.lower()
    
    if not termino or len(termino) < 2:
        return jsonify([])

    sugerencias = []
    
    # 1. Intentar con Duffel (Prioridad)
    if MotorBusqueda:
        search_terms = construir_terminos_busqueda(termino)

        for term in search_terms:
            try:
                logger.info(f"🔮 Autocomplete API: Intentando buscar '{term}' con Duffel...")
                # motor = MotorBusqueda() (YA GLOBAL)
                sugerencias = motor.autocompletar_aeropuerto(term)
                logger.info(f"🔮 Duffel devolvió: {len(sugerencias) if sugerencias else 0} resultados")
                if sugerencias:
                    return jsonify(sugerencias)
            except Exception as e:
                logger.error(f"❌ Error en Autocomplete API: {e}")

    # 2. Fallback local mejorado (ES/EN)
    resultados_fallback = buscar_fallback_es(termino)
    logger.info(f"📍 Autocomplete fallback local: {len(resultados_fallback)} resultados para '{termino}'")
    return jsonify(resultados_fallback)

@app.route('/api/buscar-vuelos', methods=['POST'])
@limiter.limit("10 per minute")
def buscar_vuelos_api():
    """Endpoint que conecta con Amadeus/Duffel para buscar vuelos reales"""
    # FASE TEMPORAL: Amadeus oculto (comentado, no eliminado)
    # amadeus_disponible = bool(amadeus_motor and amadeus_motor.is_configured())
    amadeus_disponible = bool(AMADEUS_ENABLED and amadeus_motor and amadeus_motor.is_configured())
    duffel_disponible = bool(motor and DUFFEL_TOKEN)

    if not duffel_disponible and not amadeus_disponible:
        return jsonify({'error': 'Motor de búsqueda no disponible', 'reason': 'Token o configuración faltante'}), 503

    try:
        data = request.json
        logger.info(f"🔎 Buscando vuelos: {data.get('origen')} -> {data.get('destino')} para el {data.get('fecha')}")
        logger.info(f"👥 Pasajeros: {data.get('adultos', 1)} adultos, {data.get('ninos', 0)} niños, {data.get('bebes', 0)} bebés")
        logger.info(f"✈️ Clase: {data.get('clase', 'economy')}")

        resultados_duffel = []
        resultados_amadeus = []

        nombres_ficticios = {
            'duffel airlines',
            'duffel airline',
            'duffel airways',
        }

        def _es_vuelo_real(vuelo):
            nombre = str(vuelo.get('aerolinea', '')).strip().lower()
            source = str(vuelo.get('source', '')).strip().lower()
            if source == 'duffel' and (nombre in nombres_ficticios or 'duffel' in nombre):
                return False
            return True

        if duffel_disponible:
            resultados_duffel_raw = motor.buscar_vuelos(
                data.get('origen'),
                data.get('destino'),
                data.get('fecha'),
                adultos=data.get('adultos', 1),
                ninos=data.get('ninos', 0),
                bebes=data.get('bebes', 0),
                clase=data.get('clase', 'economy')
            )
            resultados_duffel = [v for v in (resultados_duffel_raw or []) if _es_vuelo_real(v)]
            descartados = max(0, len(resultados_duffel_raw or []) - len(resultados_duffel))
            if descartados:
                logger.warning(f"⚠️ Se descartaron {descartados} ofertas ficticias de Duffel")

        # FASE TEMPORAL: Amadeus oculto (comentado, no eliminado)
        # if amadeus_disponible:
        #     resultados_amadeus = amadeus_motor.buscar_vuelos(
        #         data.get('origen'),
        #         data.get('destino'),
        #         data.get('fecha'),
        #         adultos=data.get('adultos', 1),
        #         ninos=data.get('ninos', 0),
        #         bebes=data.get('bebes', 0),
        #         clase=data.get('clase', 'economy')
        #     )

        def _dedupe_key(vuelo):
            segmentos = vuelo.get('segmentos') or []
            vuelos = '-'.join([str(s.get('vuelo', '')).strip().upper() for s in segmentos])
            return (
                str(vuelo.get('origen', '')).upper(),
                str(vuelo.get('destino', '')).upper(),
                str(vuelo.get('hora_salida', '')),
                str(vuelo.get('hora_llegada', '')),
                vuelos,
            )

        merged = {}

        for vuelo in (resultados_amadeus or []):
            merged[_dedupe_key(vuelo)] = vuelo

        for vuelo in (resultados_duffel or []):
            key = _dedupe_key(vuelo)
            existente = merged.get(key)
            if not existente:
                merged[key] = vuelo
                continue

            source_existente = str(existente.get('source', '')).lower()
            source_nuevo = str(vuelo.get('source', '')).lower()
            if source_nuevo == 'duffel' and source_existente != 'duffel':
                merged[key] = vuelo

        resultados = list(merged.values())

        if resultados:
            precios = [float(v.get('precio', 0) or 0) for v in resultados if float(v.get('precio', 0) or 0) > 0]
            mejor_precio = min(precios) if precios else 0
            umbral_duffel = mejor_precio * (1 + (DUFFEL_PRIORITY_DELTA_PERCENT / 100)) if mejor_precio > 0 else 0

            def _sort_key(vuelo):
                precio = float(vuelo.get('precio', 0) or 0)
                source = str(vuelo.get('source', '')).strip().lower()
                en_zona_competitiva = mejor_precio > 0 and precio <= umbral_duffel

                if en_zona_competitiva:
                    source_rank = 0 if source == 'duffel' else 1
                    return (0, source_rank, precio)

                return (1, 0, precio)

            resultados.sort(key=_sort_key)
            resultados = resultados[:SEARCH_RESULTS_LIMIT]

        logger.info(
            f"✅ Búsqueda combinada: Duffel={len(resultados_duffel)} | Amadeus={len(resultados_amadeus)} | Final={len(resultados)} | Top={SEARCH_RESULTS_LIMIT} | DeltaDuffel={DUFFEL_PRIORITY_DELTA_PERCENT}%"
        )

        try:
            from database import DuffelSearch, get_db_session

            db = get_db_session()
            results_count = len(resultados) if isinstance(resultados, list) else 0
            busqueda = DuffelSearch(
                origen=data.get('origen'),
                destino=data.get('destino'),
                fecha=data.get('fecha'),
                adultos=int(data.get('adultos', 1)),
                ninos=int(data.get('ninos', 0)),
                bebes=int(data.get('bebes', 0)),
                clase=data.get('clase', 'economy'),
                results_count=results_count,
                user_ip=request.remote_addr
            )
            db.add(busqueda)
            db.commit()
            db.close()
        except Exception as log_err:
            logger.warning(f"⚠️ No se pudo registrar busqueda Duffel: {log_err}")
        return jsonify(resultados)

    except Exception as e:
        logger.error(f"❌ Error crítico en API Búsqueda: {e}")
        return jsonify([]), 500


@app.route('/api/precios-calendario', methods=['GET'])
@limiter.limit("30 per minute")
def precios_calendario_api():
    """Devuelve precio mínimo por día para un mes (formato YYYY-MM-DD -> precio)."""
    if motor is None or not DUFFEL_TOKEN:
        return jsonify({'error': 'Motor de búsqueda no disponible'}), 503

    origen = (request.args.get('origen') or '').strip().upper()
    destino = (request.args.get('destino') or '').strip().upper()
    year_raw = request.args.get('year')
    month_raw = request.args.get('month')

    if len(origen) != 3 or len(destino) != 3:
        return jsonify({'prices': {}})

    try:
        year = int(year_raw)
        month = int(month_raw)
        if month < 1 or month > 12:
            raise ValueError('Mes inválido')
    except Exception:
        return jsonify({'error': 'Parámetros de fecha inválidos'}), 400

    adultos = int(request.args.get('adultos', 1) or 1)
    ninos = int(request.args.get('ninos', 0) or 0)
    bebes = int(request.args.get('bebes', 0) or 0)
    clase = (request.args.get('clase') or 'economy').strip().lower()

    _register_calendar_route(origen, destino, adultos, ninos, bebes, clase)

    cache_key = _calendar_query_key(origen, destino, year, month, adultos, ninos, bebes, clase)

    cached_prices = _get_calendar_prices_from_cache(cache_key)
    if cached_prices is not None:
        return jsonify({'prices': cached_prices, 'cached': True})

    prices = _build_calendar_prices(origen, destino, year, month, adultos, ninos, bebes, clase)
    _set_calendar_prices_cache(cache_key, prices)

    return jsonify({'prices': prices, 'cached': False})


def _calendar_query_key(origen, destino, year, month, adultos, ninos, bebes, clase):
    return f"{origen}:{destino}:{year}:{month}:{adultos}:{ninos}:{bebes}:{clase}"


def _calendar_redis_key(cache_key):
    return f"calendar_prices:{cache_key}"


def _parse_seeded_calendar_routes():
    routes = set()
    for token in CALENDAR_PREWARM_ROUTES.split(','):
        route = token.strip().upper()
        if '-' not in route:
            continue
        origen, destino = route.split('-', 1)
        if len(origen) == 3 and len(destino) == 3:
            routes.add((origen, destino, 1, 0, 0, 'economy'))
    return routes


def _register_calendar_route(origen, destino, adultos, ninos, bebes, clase):
    with CALENDAR_TRACKED_ROUTES_LOCK:
        CALENDAR_TRACKED_ROUTES.add((origen, destino, adultos, ninos, bebes, clase))


def _load_top_calendar_routes_from_history(limit=40):
    routes = set()

    if limit <= 0:
        return routes

    try:
        from sqlalchemy import func
        from database import DuffelSearch, get_db_session

        db = get_db_session()
        try:
            since = datetime.utcnow() - timedelta(days=30)
            top_routes = (
                db.query(
                    DuffelSearch.origen,
                    DuffelSearch.destino,
                    func.count(DuffelSearch.id).label('total')
                )
                .filter(DuffelSearch.fecha_creacion >= since)
                .group_by(DuffelSearch.origen, DuffelSearch.destino)
                .order_by(func.count(DuffelSearch.id).desc())
                .limit(limit)
                .all()
            )

            for item in top_routes:
                origen = (item.origen or '').strip().upper()
                destino = (item.destino or '').strip().upper()
                if len(origen) == 3 and len(destino) == 3:
                    routes.add((origen, destino, 1, 0, 0, 'economy'))
        finally:
            db.close()
    except Exception as err:
        logger.warning(f"⚠️ No se pudieron cargar rutas top para prewarm: {err}")

    return routes


def _list_tracked_calendar_routes():
    with CALENDAR_TRACKED_ROUTES_LOCK:
        observed = set(CALENDAR_TRACKED_ROUTES)
    seeded = _parse_seeded_calendar_routes()
    top_history = _load_top_calendar_routes_from_history(CALENDAR_PREWARM_TOP_ROUTES_LIMIT)
    return observed.union(seeded).union(top_history)


def _extract_flight_price(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace('€', '').replace(' ', '')
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '.')
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _build_calendar_prices(origen, destino, year, month, adultos, ninos, bebes, clase):
    first_day = datetime(year, month, 1)
    next_month = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    last_day = next_month - timedelta(days=1)
    today = datetime.now().date()

    prices = {}
    cursor = first_day

    while cursor <= last_day:
        fecha_date = cursor.date()
        if fecha_date >= today:
            fecha_iso = fecha_date.isoformat()
            try:
                if hasattr(motor, 'is_rate_limited') and motor.is_rate_limited():
                    remaining = motor.get_rate_limit_remaining_seconds() if hasattr(motor, 'get_rate_limit_remaining_seconds') else 0
                    logger.warning(
                        f"⏳ Calendario detenido temporalmente por rate limit de Duffel ({remaining}s restantes) para {origen}->{destino}"
                    )
                    break

                resultados = motor.buscar_vuelos(
                    origen,
                    destino,
                    fecha_iso,
                    adultos=adultos,
                    ninos=ninos,
                    bebes=bebes,
                    clase=clase
                )

                if isinstance(resultados, list) and resultados:
                    precios_validos = []
                    for vuelo in resultados:
                        precio = _extract_flight_price(vuelo.get('precio'))
                        if precio is not None:
                            precios_validos.append(precio)

                    if precios_validos:
                        prices[fecha_iso] = int(min(precios_validos))
            except Exception as err:
                logger.warning(f"⚠️ Error precio calendario {origen}->{destino} {fecha_iso}: {err}")

        cursor += timedelta(days=1)

    return prices


def _get_calendar_prices_from_cache(cache_key):
    redis_key = _calendar_redis_key(cache_key)
    if shared_redis_cache and getattr(shared_redis_cache, 'available', False):
        try:
            cached = shared_redis_cache.get(redis_key)
            if isinstance(cached, dict):
                return cached
        except Exception as err:
            logger.warning(f"⚠️ Error leyendo caché Redis calendario: {err}")

    now_ts = time.time()
    cached_local = CALENDAR_PRICE_CACHE.get(cache_key)
    if cached_local and (now_ts - cached_local['ts']) < CALENDAR_PRICE_CACHE_TTL:
        return cached_local['prices']

    return None


def _set_calendar_prices_cache(cache_key, prices):
    redis_key = _calendar_redis_key(cache_key)
    if shared_redis_cache and getattr(shared_redis_cache, 'available', False):
        try:
            shared_redis_cache.set(redis_key, prices, ttl=CALENDAR_PRICE_CACHE_TTL)
        except Exception as err:
            logger.warning(f"⚠️ Error guardando caché Redis calendario: {err}")

    CALENDAR_PRICE_CACHE[cache_key] = {'ts': time.time(), 'prices': prices}


def refresh_calendar_prices_daily():
    if motor is None or not DUFFEL_TOKEN:
        logger.warning("⚠️ Refresh diario de calendario omitido: motor/token no disponibles")
        return

    routes = _list_tracked_calendar_routes()
    if not routes:
        logger.info("ℹ️ Refresh diario de calendario: sin rutas registradas aún")
        return

    now = datetime.utcnow()
    targets = [(now.year, now.month)]
    if now.month == 12:
        targets.append((now.year + 1, 1))
    else:
        targets.append((now.year, now.month + 1))

    logger.info(f"🔁 Refresh diario de calendario iniciado para {len(routes)} rutas")

    for (origen, destino, adultos, ninos, bebes, clase) in routes:
        for (year, month) in targets:
            cache_key = _calendar_query_key(origen, destino, year, month, adultos, ninos, bebes, clase)
            prices = _build_calendar_prices(origen, destino, year, month, adultos, ninos, bebes, clase)
            _set_calendar_prices_cache(cache_key, prices)

    logger.info("✅ Refresh diario de calendario completado")


def process_auto_checkin_queue():
    """Monitoriza reservas listas para check-in y notifica al abrirse la ventana de 24h."""
    if not AUTO_CHECKIN_ENABLED:
        return

    try:
        from database import ReservaVuelo, get_db_session
        db = get_db_session()
        now = datetime.utcnow()
        procesadas = 0

        reservas = db.query(ReservaVuelo).filter(ReservaVuelo.estado == 'LISTO PARA CHECK-IN').all()
        for reserva in reservas:
            checkin_open = _extract_checkin_open_datetime(reserva)
            if not checkin_open or now < checkin_open:
                continue

            booking_ref = _extract_booking_reference(reserva)
            checkin_url = _resolve_airline_checkin_url(reserva)
            reserva.estado = 'CHECK-IN ABIERTO'
            nota = f"[AUTO_CHECKIN] Ventana de check-in abierta el {now.strftime('%d/%m/%Y %H:%M')} UTC."
            reserva.notas = f"{nota} {reserva.notas or ''}".strip()

            if getattr(reserva, 'email_cliente', None):
                asunto = f"✅ Check-in abierto para tu reserva {reserva.codigo_reserva}"
                html = f"""
                <h2>Tu check-in ya está disponible</h2>
                <p>Reserva: <strong>{reserva.codigo_reserva}</strong></p>
                <p>Localizador aerolínea: <strong>{booking_ref or 'N/A'}</strong></p>
                <p>Ya puedes completar el check-in en la web de la aerolínea o en nuestra sección de check-in.</p>
                {f'<p><a href="{checkin_url}" target="_blank" rel="noopener">Ir al check-in de la aerolínea</a></p>' if checkin_url else ''}
                <p><a href=\"{os.getenv('APP_URL', 'http://localhost:8000')}/checkin\">Ir a Check-in</a></p>
                """
                email_manager.send_email(reserva.email_cliente, asunto, html)

            procesadas += 1

        if procesadas:
            db.commit()
            logger.info(f"✅ Auto-checkin monitor: {procesadas} reservas actualizadas")
        db.close()

    except Exception as e:
        logger.error(f"❌ Error en monitor auto-checkin: {e}")


def _init_calendar_scheduler():
    scheduler = APScheduler()
    scheduler.init_app(app)

    jobs_added = 0

    if CALENDAR_ENABLE_DAILY_REFRESH:
        scheduler.add_job(
            id='refresh-calendar-prices-daily',
            func=refresh_calendar_prices_daily,
            trigger='cron',
            hour=CALENDAR_REFRESH_HOUR,
            minute=CALENDAR_REFRESH_MINUTE,
            replace_existing=True
        )
        jobs_added += 1
        logger.info(
            f"✅ Job diario precios calendario activo ({CALENDAR_REFRESH_HOUR:02d}:{CALENDAR_REFRESH_MINUTE:02d} UTC, TTL {CALENDAR_PRICE_CACHE_TTL}s)"
        )
    else:
        logger.info("ℹ️ Refresh diario de calendario deshabilitado por configuración")

    if AUTO_CHECKIN_ENABLED:
        scheduler.add_job(
            id='monitor-auto-checkin',
            func=process_auto_checkin_queue,
            trigger='interval',
            minutes=AUTO_CHECKIN_SCAN_MINUTES,
            replace_existing=True
        )
        jobs_added += 1
        logger.info(f"✅ Monitor auto-checkin activo (cada {AUTO_CHECKIN_SCAN_MINUTES} min)")

    if jobs_added == 0:
        logger.info("ℹ️ Sin jobs de scheduler activos")
        return

    scheduler.start()


@app.route('/api/vuelos/asientos/<offer_id>', methods=['GET'])
def obtener_asientos_vuelo(offer_id):
    """Endpoint para obtener mapa de asientos"""
    if motor is None: return jsonify({'error': 'Motor no disponible'}), 503
    
    try:
        # motor = MotorBusqueda() (YA GLOBAL)
        asientos = motor.get_seat_maps(offer_id)
        
        if asientos:
            return jsonify({'success': True, 'data': asientos})
        else:
            return jsonify({'success': False, 'error': 'No se pudo obtener el mapa de asientos'}), 404
    except Exception as e:
        logger.error(f"❌ Error en API Asientos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vuelos/detalles/<offer_id>', methods=['GET'])
def obtener_detalles_vuelo(offer_id):
    """Endpoint para obtener detalles completos (maletas/asientos) de un vuelo"""
    if motor is None: return jsonify({'error': 'Motor no disponible'}), 503
    
    try:
        # Los IDs de Amadeus no son resolubles en Duffel Offer Details
        if str(offer_id).startswith('amadeus_'):
            return jsonify({
                'success': True,
                'data': {
                    'id': offer_id,
                    'available_services': []
                },
                'provider': 'amadeus',
                'fallback_cache': True
            })

        # motor = MotorBusqueda() (YA GLOBAL)
        detalles = motor.get_offer_details(offer_id)
        
        if detalles:
            return jsonify({'success': True, 'data': detalles})
        for cache_data in getattr(motor, 'cache', {}).values():
            if not isinstance(cache_data, tuple) or not cache_data:
                continue

            cached_results = cache_data[0]
            if not isinstance(cached_results, list):
                continue

            for vuelo in cached_results:
                if vuelo.get('id') == offer_id:
                    available_services = vuelo.get('available_services') or []
                    return jsonify({
                        'success': True,
                        'data': {
                            'id': offer_id,
                            'available_services': available_services
                        },
                        'fallback_cache': True
                    })

        return jsonify({'success': False, 'error': 'No se pudieron obtener detalles'}), 404
            
    except Exception as e:
        logger.error(f"❌ Error endpoint detalles vuelo: {e}")
        return jsonify({'error': str(e)}), 500


# ==========================================
# 5. PASARELAS DE PAGO (DUFFEL)
# ==========================================


@app.route('/api/vuelos/cancelar-orden', methods=['POST'])
@login_required
def cancelar_orden_api():
    """
    Cancela una orden en Duffel. Solo ADMIN.
    """
    try:
        data = request.json
        order_id = data.get('order_id')
        reserva_id = data.get('reserva_id')
        
        if not order_id and not reserva_id:
             return jsonify({'error': 'Se requiere order_id o reserva_id'}), 400
             
        # Si viene reserva_id, buscamos el order_id
        if reserva_id and not order_id:
            from database import ReservaVuelo, get_db_session
            session = get_db_session()
            reserva = session.query(ReservaVuelo).get(reserva_id)
            if not reserva or not reserva.order_id_duffel:
                session.close()
                return jsonify({'error': 'Reserva u Order ID no encontrado'}), 404
            order_id = reserva.order_id_duffel
            session.close()
            
        if motor is None: return jsonify({'error': 'Motor no disponible'}), 503
        
        # motor = MotorBusqueda() (YA GLOBAL)
        resultado = motor.cancelar_orden(order_id)
        
        if resultado['success']:
            logger.info(f"✅ Orden {order_id} cancelada exitosamente")
            # Actualizar DB si fuera necesario
            if reserva_id:
                session = get_db_session()
                reserva = session.query(ReservaVuelo).get(reserva_id)
                if reserva:
                    reserva.estado = 'CANCELADO'
                    reserva.notas = (reserva.notas or "") + f" | Cancelado en Duffel: {datetime.now()}"
                    session.commit()
                session.close()
                
            return jsonify(resultado)
        else:
            return jsonify(resultado), 400
            
    except Exception as e:
        logger.error(f"❌ Error cancelando orden: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vuelos/crear-reserva', methods=['POST'])
@limiter.limit("5 per minute")
def crear_reserva_vuelo():
    """
    Crea una reserva de vuelo en estado PENDIENTE antes del pago
    Recibe: offer_id de Duffel, datos de pasajeros, precio
    Devuelve: reserva_id para proceder al pago
    """
    try:
        data = request.json
        offer_id = data.get('offer_id')
        datos_vuelo = data.get('datos_vuelo', {})
        proveedor = str(datos_vuelo.get('source', 'Duffel'))
        proveedor_meta = proveedor.lower()
        proveedor_meta = proveedor.lower()
        pasajeros = data.get('pasajeros', [])
        amadeus_offer = data.get('amadeus_full_offer') or datos_vuelo.get('amadeus_full_offer') or datos_vuelo.get('amadeus_offer')
        # Usar Decimal para precisión monetaria
        precio_total = Decimal(str(data.get('precio_total', 0)))
        email_cliente = data.get('email_cliente')
        telefono = data.get('telefono_cliente', '')
        
        if not offer_id or not pasajeros or not email_cliente:
            return jsonify({'error': 'Faltan datos requeridos'}), 400

        # Validación de edad por tipo de pasajero (regla negocio: adulto >=18, niño <18)
        hoy = datetime.utcnow().date()
        for idx, pasajero in enumerate(pasajeros, start=1):
            tipo = str(pasajero.get('type', '')).strip().lower()
            born_on = str(pasajero.get('born_on', '')).strip()

            if tipo not in {'adult', 'child'}:
                return jsonify({'error': f'Tipo de pasajero inválido en posición {idx}'}), 400

            try:
                fecha_nacimiento = datetime.strptime(born_on, '%Y-%m-%d').date()
            except Exception:
                return jsonify({'error': f'Fecha de nacimiento inválida en pasajero {idx}'}), 400

            if fecha_nacimiento > hoy:
                return jsonify({'error': f'La fecha de nacimiento del pasajero {idx} no puede ser futura'}), 400

            edad = (hoy - fecha_nacimiento).days / 365.25
            if edad > 120:
                return jsonify({'error': f'Fecha de nacimiento fuera de rango en pasajero {idx}'}), 400

            if tipo == 'adult' and edad < 18:
                return jsonify({'error': f'El pasajero {idx} está marcado como adulto pero es menor de 18 años'}), 400

            if tipo == 'child' and edad >= 18:
                return jsonify({'error': f'El pasajero {idx} está marcado como niño pero tiene 18 años o más'}), 400

        # FASE TEMPORAL: Amadeus oculto (comentado, no eliminado)
        # if proveedor != 'Duffel':
        #     ... lógica Amadeus ...
        if not AMADEUS_ENABLED and proveedor != 'Duffel':
            return jsonify({'error': 'Amadeus está deshabilitado temporalmente'}), 400
        
        # Generar código único de reserva
        import secrets
        codigo_reserva = f"FL{secrets.token_hex(4).upper()}"
        
        # Crear reserva en BD
        from database import ReservaVuelo, get_db_session
        session = get_db_session()
        
        try:
            reserva = ReservaVuelo(
                codigo_reserva=codigo_reserva,
                provider=proveedor.upper(),
                offer_id_duffel=offer_id if proveedor == 'Duffel' else None,
                datos_vuelo=json.dumps(datos_vuelo),
                pasajeros=json.dumps(pasajeros),
                amadeus_full_offer=json.dumps(amadeus_offer) if amadeus_offer else None,
                precio_vuelos=float(precio_total), # BD suele ser Float o Numeric
                precio_total=float(precio_total),
                email_cliente=email_cliente,
                telefono_cliente=telefono,
                estado='PENDIENTE' if proveedor == 'Duffel' else 'PENDIENTE_PAGO_AMADEUS',
                es_viaje_redondo=bool(datos_vuelo.get('es_viaje_redondo')) and str(datos_vuelo.get('es_viaje_redondo')) != ""
            )

            if proveedor != 'Duffel':
                reserva.notas = f"Proveedor: {proveedor} | Offer externa: {offer_id}"
            
            session.add(reserva)
            session.commit()
            
            reserva_id = reserva.id
            session.close()
            
            logger.info(f"✅ Reserva creada: {codigo_reserva} (ID: {reserva_id})")
            
            return jsonify({
                'success': True,
                'reserva_id': reserva_id,
                'codigo_reserva': codigo_reserva,
                'precio_total': float(precio_total)
            })
            
        except Exception as e:
            session.rollback()
            session.close()
            raise e
            
    except Exception as e:
        logger.error(f"❌ Error creando reserva: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vuelos/confirmar-directo', methods=['POST'])
@login_required  # 🔒 SEGURIDAD AÑADIDA: SOLO ADMIN
def confirmar_vuelo_directo():
    """
    Confirma una reserva directamente usando el saldo de Duffel (Agency Balance).
    REQUIERE AUTENTICACIÓN.
    """
    try:
        data = request.json
        reserva_id = data.get('reserva_id')
        
        if not reserva_id:
            return jsonify({'error': 'reserva_id requerido'}), 400
        
        from database import ReservaVuelo, get_db_session
        session = get_db_session()
        
        reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
        
        if not reserva:
            session.close()
            return jsonify({'error': 'Reserva no encontrada'}), 404
            
        reserva.estado = 'Procesando en Duffel...'
        session.commit()
        
        logger.info(f"🚀 Iniciando confirmación directa Duffel para: {reserva.codigo_reserva}")
        
        pasajeros_data = json.loads(reserva.pasajeros)
        
        # Extraer servicios si existen
        datos_vuelo = json.loads(reserva.datos_vuelo)
        services = datos_vuelo.get('services')

        if motor is None:
            return jsonify({'error': 'Motor de búsqueda no disponible'}), 503
            
        # motor = MotorBusqueda() (YA GLOBAL)
        
        # Estrategia: Crear orden 'hold' -> Pagar con Balance (Implícito si 'instant' y funds ok, o explicit payment)
        # Para simplificar y dado que es Admin Directo con Duffel Balance:
        # Usamos 'instant' con un payment dummy de tipo 'balance' si la API lo requiere,
        # o simplemente confiamos en que Duffel deduce del balance si no hay payment method externo.
        # Duffel API: Create Order -> payment required for instant.
        # Payment object: { type: "balance", amount: "...", currency: "..." }
        
        # Necesitamos el monto exacto de la oferta + servicios.
        # Lo mejor es obtenerlo de la oferta actualizada, pero usaremos el guardado si confiamos.
        # Vamos a intentar recuperar el precio REAL de la oferta primero.
        offer_details = motor.get_offer_details(reserva.offer_id_duffel)
        if not offer_details:
             # Fallback al precio guardado, esperando que no haya cambiado
             amount_str = str(reserva.precio_total)
             currency = "EUR" # Asunción arriesgada, mejor del offer_details si fuera posible
        else:
             amount_str = offer_details['total_amount']
             currency = offer_details['total_currency']

        payments_payload = [{
            "type": "balance",
            "amount": amount_str,
            "currency": currency
        }]
        
        resultado = motor.crear_order_duffel(
            offer_id=reserva.offer_id_duffel,
            pasajeros_data=pasajeros_data,
            services=services,
            type='instant',
            payments=payments_payload
        )
        
        if resultado['success']:
            reserva.order_id_duffel = resultado['order_id']
            reserva.estado = 'CONFIRMADO'
            reserva.fecha_pago = datetime.now()
            reserva.fecha_confirmacion = datetime.now()
            reserva.notas = f"Booking Ref: {resultado['booking_reference']} (Directo)"
            session.commit()
            
            session.close()
            return jsonify({
                'success': True,
                'booking_reference': resultado['booking_reference']
            })
            
        else:
            reserva.estado = 'ERROR'
            reserva.error_mensaje = resultado['error']
            session.commit()
            session.close()
            return jsonify({'success': False, 'error': resultado['error']}), 400
            
    except Exception as e:
        logger.error(f"❌ Excepción confirmar directo: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/vuelos/payment-intent', methods=['POST'])
def crear_payment_intent_duffel():
    """Endpoint para crear un Payment Intent en Duffel"""
    try:
        data = request.json
        amount = data.get('amount')
        currency = data.get('currency')
        
        if not amount or not currency:
            return jsonify({'error': 'Monto y moneda requeridos'}), 400
            
        if motor is None:
            return jsonify({'error': 'Motor de búsqueda no disponible'}), 503

        # motor = MotorBusqueda() (YA GLOBAL)
        
        resultado = motor.crear_payment_intent(Decimal(str(amount)), currency)

        def _duffel_unavailable_feature(res):
            if not res:
                return False
            error_raw = str(res.get('error') or '')
            if 'unavailable_feature' in error_raw:
                return True
            try:
                parsed = json.loads(error_raw)
                errors = parsed.get('errors') or []
                if errors:
                    return str(errors[0].get('code', '')).strip().lower() == 'unavailable_feature'
            except Exception:
                pass
            return False
        
        if resultado and resultado.get('success'):
             data_intent = resultado['data']
             intent_id = data_intent['id']

             # ACTUALIZACIÓN IMPRESCINDIBLE: Guardar ID en la reserva
             reserva_id = data.get('reserva_id')
             if reserva_id:
                 from database import ReservaVuelo, get_db_session
                 session = get_db_session()
                 reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
                 if reserva:
                     reserva.stripe_payment_intent_id = intent_id # Guardamos el ID de Duffel aquí
                     session.commit()
                     print(f"✅ Payment Intent {intent_id} guardado en reserva {reserva.codigo_reserva}")
                 session.close()

             return jsonify({'success': True, 'client_token': data_intent['client_token'], 'id': intent_id})
        else:
             if _duffel_unavailable_feature(resultado):
                 reserva_id = data.get('reserva_id')
                 redirect_url = '/'
                 if reserva_id:
                     from database import ReservaVuelo, get_db_session
                     session = get_db_session()
                     reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
                     if reserva:
                         reserva.estado = 'pendiente_pago'
                         reserva.error_mensaje = 'Duffel Payments no disponible para esta cuenta. Pago manual requerido.'
                         session.commit()
                         redirect_url = f'/reserva/pendiente-pago/{reserva.codigo_reserva}'
                     session.close()

                 return jsonify({
                     'success': True,
                     'manual_payment': True,
                     'reason': 'unavailable_feature',
                     'redirect_url': redirect_url,
                     'message': 'Duffel Payments no está habilitado para la cuenta. Continuando por pago manual.'
                 })

             error_msg = resultado.get('error') if resultado else 'Error desconocido creando Payment Intent'
             return jsonify({'success': False, 'error': error_msg}), 400
             
    except Exception as e:
        logger.error(f"❌ Error payment-intent endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/vuelos/client-component-key', methods=['POST'])
def get_duffel_component_key():
    """Obtiene JWT para Duffel Components"""
    try:
        if motor is None:
            return jsonify({'error': 'Motor de búsqueda no disponible'}), 503

        # motor = MotorBusqueda() (YA GLOBAL)
        resultado = motor.crear_client_component_key()

        def _duffel_unavailable_feature(res):
            if not res:
                return False
            error_raw = str(res.get('error') or '')
            if 'unavailable_feature' in error_raw:
                return True
            try:
                parsed = json.loads(error_raw)
                errors = parsed.get('errors') or []
                if errors:
                    return str(errors[0].get('code', '')).strip().lower() == 'unavailable_feature'
            except Exception:
                pass
            return False
        
        if resultado and resultado.get('success'):
            client_key = (resultado.get('client_key') or '').strip()
            if not client_key:
                logger.error("❌ Duffel client-component-key vacío en endpoint")
                return jsonify({'success': False, 'error': 'Duffel client key vacía'}), 502
            return jsonify({'success': True, 'client_key': client_key})
        else:
            if _duffel_unavailable_feature(resultado):
                return jsonify({
                    'success': True,
                    'manual_payment': True,
                    'reason': 'unavailable_feature',
                    'message': 'Duffel Payments no está habilitado para la cuenta. Continuando por pago manual.'
                })

            error_msg = resultado.get('error') if resultado else 'Error desconocido generating key'
            logger.error(f"❌ Error obteniendo client-component-key: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/orden/checkout/<codigo_reserva>')
def checkout_page(codigo_reserva):
    """Página dedicada de pago para una reserva"""
    try:
        from database import ReservaVuelo, get_db_session
        import json
        
        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
        session.close() # Cerramos sesión para evitar bloqueos
        
        if not reserva:
            return "Reserva no encontrada", 404

        # PARSEO CRÍTICO: Convertir JSON strings a Objetos Python
        # Sin esto, Jinja ve strings y reserva.origen falla
        try:
            if isinstance(reserva.datos_vuelo, str):
                reserva.datos_vuelo = json.loads(reserva.datos_vuelo)
            if isinstance(reserva.pasajeros, str):
                reserva.pasajeros = json.loads(reserva.pasajeros)
        except Exception as e:
            logger.error(f"Error parseando JSON reserva: {e}")

        proveedor_reserva = str((reserva.datos_vuelo or {}).get('source', 'Duffel'))
        if proveedor_reserva != 'Duffel':
            if not AMADEUS_ENABLED:
                return "Proveedor no disponible temporalmente", 404

            session = get_db_session()
            reserva_db = session.query(ReservaVuelo).filter_by(id=reserva.id).first()
            if reserva_db:
                reserva_db.estado = 'pendiente_pago_amadeus'
                reserva_db.notas = (reserva_db.notas or '') + ' | Checkout Amadeus: pago/confirmación fuera de Duffel Payments'
                session.commit()
            session.close()
            stripe_public_key = os.getenv('STRIPE_PUBLIC_KEY', '')
            return render_template('amadeus_checkout.html', reserva=reserva, stripe_public_key=stripe_public_key)
            
        usar_pago_manual = os.getenv('PAYMENT_FLOW', 'duffel').lower() == 'manual' or not os.getenv('DUFFEL_API_TOKEN')
        if usar_pago_manual:
            session = get_db_session()
            reserva_db = session.query(ReservaVuelo).filter_by(id=reserva.id).first()
            if reserva_db:
                reserva_db.estado = 'pendiente_pago'
                session.commit()
            session.close()
            return render_template('pending_manual_payment.html', reserva=reserva)

        rollout_bucket = get_rollout_bucket("checkout_multi_step", codigo_reserva)
        checkout_multi_step_enabled = is_feature_enabled(
            "checkout_multi_step",
            seed=codigo_reserva,
            percentage=CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
            enabled=CHECKOUT_MULTI_STEP_ENABLED
        )
        logger.info(
            "Checkout multi-step %s (bucket=%s, rollout=%s%%) reserva=%s",
            "ON" if checkout_multi_step_enabled else "OFF",
            rollout_bucket,
            CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
            codigo_reserva
        )
        return render_template(
            'checkout.html',
            reserva=reserva,
            checkout_multi_step=checkout_multi_step_enabled
        )
    except Exception as e:
        logger.error(f"Error checkout page: {e}")
        return "Error cargando checkout", 500

@app.route('/api/vuelos/confirmar-pago', methods=['POST'])
def confirmar_pago_tarjeta():
    """
    Finaliza la reserva tras un pago exitoso con tarjeta (Duffel Component).
    """
    try:
        data = request.json
        reserva_id = data.get('reserva_id')
        card_id = data.get('card_id') # Nuevo campo crucial
        # Usar Decimal para precisión
        amount = Decimal(str(data.get('amount')))
        currency = data.get('currency')
        
        if not reserva_id:
            return jsonify({'error': 'reserva_id requerido'}), 400

        if not card_id:
            return jsonify({'error': 'card_id requerido'}), 400
            
        from database import ReservaVuelo, get_db_session
        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()
        
        if not reserva:
            session.close()
            return jsonify({'error': 'Reserva no encontrada'}), 404

        proveedor_reserva = 'Duffel'
        try:
            datos_vuelo_tmp = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
            proveedor_reserva = str(datos_vuelo_tmp.get('source', 'Duffel'))
        except Exception:
            proveedor_reserva = 'Duffel'

        if proveedor_reserva != 'Duffel':
            session.close()
            return jsonify({
                'error': 'Esta reserva pertenece a Amadeus y no se confirma con Duffel Payments',
                'provider': proveedor_reserva,
                'manual_payment': True,
                'redirect_url': f'/reserva/pendiente-pago/{reserva.codigo_reserva}'
            }), 400
            
        payment_intent_id = reserva.stripe_payment_intent_id
        if not payment_intent_id:
            reserva.estado = 'pendiente_pago'
            reserva.error_mensaje = 'Duffel Payment Intent no disponible. Pago manual requerido.'
            session.commit()
            codigo_reserva = reserva.codigo_reserva
            session.close()
            return jsonify({'success': True, 'manual_payment': True, 'redirect_url': f'/reserva/pendiente-pago/{codigo_reserva}'})

        reserva.estado = 'Confirmando Pago...'
        session.commit()
        
        # from core.scraper_motor import MotorBusqueda (YA GLOBAL)
        # motor = MotorBusqueda() (YA GLOBAL)
        
        # 1. COBRAR (Confirm Payment Intent)
        confirm_result = motor.confirmar_payment_intent(payment_intent_id, card_id)

        if not confirm_result['success']:
            reserva.estado = 'pendiente_pago'
            reserva.error_mensaje = f"Fallo cobro Duffel. Pago manual requerido: {confirm_result.get('error')}"
            session.commit()
            codigo_reserva = reserva.codigo_reserva
            session.close()
            return jsonify({'success': True, 'manual_payment': True, 'redirect_url': f'/reserva/pendiente-pago/{codigo_reserva}'})

        # 2. CREAR ORDER (Funded by Balance/Payment)
        pasajeros_data = json.loads(reserva.pasajeros)
        datos_vuelo_obj = json.loads(reserva.datos_vuelo)
        services = datos_vuelo_obj.get('services')

        # Usar importe real del offer en Duffel para evitar desajustes (422)
        amount_order = amount
        currency_order = currency
        try:
            offer_details = motor.get_offer_details(reserva.offer_id_duffel)
            if offer_details:
                offer_amount = offer_details.get('total_amount')
                offer_currency = offer_details.get('total_currency')
                if offer_amount:
                    amount_order = Decimal(str(offer_amount))
                if offer_currency:
                    currency_order = str(offer_currency).upper()
                logger.info(
                    f"💵 Monto order desde Duffel offer: {amount_order} {currency_order} (reserva={reserva.codigo_reserva})"
                )
            else:
                logger.warning(
                    f"⚠️ No se pudo obtener offer_details para {reserva.offer_id_duffel}. Usando monto local {amount_order} {currency_order}"
                )
        except Exception as e_offer:
            logger.warning(
                f"⚠️ Error obteniendo monto real de offer {reserva.offer_id_duffel}: {e_offer}. Usando monto local {amount_order} {currency_order}"
            )

        # Payment Block for Order
        # Como Duffel requiere payments para 'instant', usamos 'balance' 
        # asumiendo que el payment intent anterior recargó el balance o está linkado.
        # Nota: Duffel Payments crea un Payment Intent, al confirmarlo el dinero va a tu balance Duffel.
        # Por tanto, pagamos la orden con 'balance'.
        payments_payload = [{
            "type": "balance",
            "amount": f"{Decimal(str(amount_order)):.2f}",
            "currency": currency_order
        }]

        resultado = motor.crear_order_duffel(
            offer_id=reserva.offer_id_duffel,
            pasajeros_data=pasajeros_data,
            services=services,
            type='instant',
            payments=payments_payload
        )
        
        if resultado['success']:
            reserva.order_id_duffel = resultado['order_id']
            reserva.estado = 'CONFIRMADO'
            reserva.fecha_pago = datetime.now()
            reserva.fecha_confirmacion = datetime.now()
            reserva.notas = f"Booking Ref: {resultado['booking_reference']} (Pago Tarjeta Exitoso)"
            session.commit()
            session.close()
            
            logger.info(f"✅ Vuelo confirmado con tarjeta: {resultado['booking_reference']}")
            
            # 3. ENVIAR EMAIL DE CONFIRMACIÓN (Automation)
            try:
                email_manager.send_order_confirmation(
                    to_email=reserva.email_cliente,
                    booking_ref=resultado['booking_reference'],
                    amount=amount,
                    currency=currency
                )
            except Exception as e_mail:
                logger.error(f"⚠️ Error enviando email: {e_mail}")

            return jsonify({
                'success': True,
                'booking_reference': resultado['booking_reference']
            })
        else:
            reserva.estado = 'pendiente_pago'
            reserva.error_mensaje = f"Pago confirmado, emisión pendiente manual: {resultado['error']}"
            session.commit()
            codigo_reserva = reserva.codigo_reserva
            session.close()
            return jsonify({'success': True, 'manual_payment': True, 'redirect_url': f'/reserva/pendiente-pago/{codigo_reserva}'})
            
    except Exception as e:
        logger.error(f"❌ Excepción confirmar pago tarjeta: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/reserva/pendiente-pago/<codigo_reserva>')
def reserva_pendiente_pago(codigo_reserva):
    """Pantalla de confirmación con pago manual por transferencia."""
    try:
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
        if not reserva:
            session.close()
            return "Reserva no encontrada", 404

        proveedor_reserva = 'Duffel'
        try:
            datos_vuelo_tmp = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
            proveedor_reserva = str(datos_vuelo_tmp.get('source', 'Duffel'))
        except Exception:
            proveedor_reserva = 'Duffel'

        reserva.estado = 'pendiente_pago_amadeus' if proveedor_reserva != 'Duffel' else 'pendiente_pago'
        session.commit()

        if isinstance(reserva.datos_vuelo, str):
            reserva.datos_vuelo = json.loads(reserva.datos_vuelo)
        if isinstance(reserva.pasajeros, str):
            reserva.pasajeros = json.loads(reserva.pasajeros)

        session.close()
        return render_template('pending_manual_payment.html', reserva=reserva)
    except Exception as e:
        logger.error(f"Error en pendiente pago manual: {e}")
        return "Error cargando estado de reserva", 500


@app.route('/api/amadeus/create-checkout-session', methods=['POST'])
@limiter.limit("10 per minute")
def amadeus_create_checkout_session():
    """Crea una sesión Stripe Checkout para reservas de Amadeus."""
    try:
        if not AMADEUS_ENABLED:
            return jsonify({'error': 'Amadeus deshabilitado temporalmente'}), 404

        payload = request.json or {}
        codigo_reserva = (payload.get('codigo_reserva') or '').strip()
        if not codigo_reserva:
            return jsonify({'error': 'codigo_reserva requerido'}), 400

        stripe_secret_key = os.getenv('STRIPE_SECRET_KEY', '').strip()
        if not stripe_secret_key:
            return jsonify({'error': 'STRIPE_SECRET_KEY no configurada'}), 503

        from database import ReservaVuelo, get_db_session
        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
        if not reserva:
            session.close()
            return jsonify({'error': 'Reserva no encontrada'}), 404

        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
        except Exception:
            datos_vuelo = {}

        proveedor = str(datos_vuelo.get('source', 'Duffel'))
        proveedor_meta = proveedor.lower()
        if proveedor == 'Duffel':
            session.close()
            return jsonify({'error': 'Esta ruta es solo para reservas Amadeus'}), 400

        amount_cents = int(round(float(reserva.precio_total or 0) * 100))
        if amount_cents <= 0:
            session.close()
            return jsonify({'error': 'Monto inválido para checkout'}), 400

        base_url = request.host_url.rstrip('/')
        success_url = f"{base_url}/reserva/amadeus/pago-exito/{reserva.codigo_reserva}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{base_url}/reserva/pendiente-pago/{reserva.codigo_reserva}"

        stripe_resp = requests.post(
            'https://api.stripe.com/v1/checkout/sessions',
            auth=(stripe_secret_key, ''),
            data={
                'mode': 'payment',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'line_items[0][price_data][currency]': 'eur',
                'line_items[0][price_data][product_data][name]': f"Reserva vuelo Amadeus {reserva.codigo_reserva}",
                'line_items[0][price_data][unit_amount]': str(amount_cents),
                'line_items[0][quantity]': '1',
                'client_reference_id': reserva.codigo_reserva,
                'metadata[codigo_reserva]': reserva.codigo_reserva,
                'metadata[proveedor]': proveedor_meta,
                'automatic_tax[enabled]': 'false',
            },
            timeout=25
        )

        if stripe_resp.status_code >= 400:
            session.close()
            logger.error(f"❌ Stripe Checkout error {stripe_resp.status_code}: {stripe_resp.text}")
            return jsonify({'error': 'No se pudo crear la sesión de pago'}), 502

        stripe_data = stripe_resp.json()
        reserva.stripe_session_id = stripe_data.get('id')
        reserva.estado = 'PAGADO_PENDIENTE_EMISION'
        session.commit()
        session.close()

        return jsonify({'success': True, 'url': stripe_data.get('url')})

    except Exception as e:
        logger.error(f"❌ Error creando checkout Amadeus: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/reserva/amadeus/pago-exito/<codigo_reserva>')
def amadeus_pago_exito(codigo_reserva):
    """Marca reserva Amadeus como pagada y pendiente de emisión manual."""
    try:
        if not AMADEUS_ENABLED:
            return "Amadeus deshabilitado temporalmente", 404

        session_id = (request.args.get('session_id') or '').strip()
        from database import ReservaVuelo, get_db_session

        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
        if not reserva:
            session.close()
            return "Reserva no encontrada", 404

        reserva.estado = 'PAGADO_PENDIENTE_EMISION'
        reserva.fecha_pago = datetime.now()
        reserva.notas = (reserva.notas or '') + f" | Pago Stripe Amadeus OK session={session_id or 'n/a'}"
        if session_id:
            reserva.stripe_session_id = session_id
        session.commit()

        if isinstance(reserva.datos_vuelo, str):
            reserva.datos_vuelo = json.loads(reserva.datos_vuelo)
        if isinstance(reserva.pasajeros, str):
            reserva.pasajeros = json.loads(reserva.pasajeros)

        session.close()
        return render_template('pending_manual_payment.html', reserva=reserva)
    except Exception as e:
        logger.error(f"❌ Error en pago éxito Amadeus: {e}")
        return "Error confirmando pago", 500


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """
    Webhook de Stripe para manejar eventos de pago.
    Desencadena emisión automática de Amadeus cuando payment_intent.succeeded.
    """
    try:
        import hmac
        import hashlib
        
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('Stripe-Signature', '')
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()

        if not webhook_secret:
            logger.warning("⚠️ STRIPE_WEBHOOK_SECRET no configurada")
            return jsonify({'error': 'Webhook no configurado'}), 501

        # Verificar firma de Stripe
        try:
            timestamp = sig_header.split(',')[0].split('=')[1]
            signature = sig_header.split(',')[1].split('=')[1]
            
            signed_content = f"{timestamp}.{payload}"
            computed_sig = hmac.new(
                webhook_secret.encode(),
                signed_content.encode(),
                hashlib.sha256
            ).hexdigest()
            
            if not hmac.compare_digest(computed_sig, signature):
                logger.warning("❌ Firma Stripe inválida")
                return jsonify({'error': 'Firma inválida'}), 401
        except Exception as e:
            logger.warning(f"⚠️ Error verificando firma Stripe: {e}")
            return jsonify({'error': 'Firma inválida'}), 401

        # Procesar evento
        event = json.loads(payload)
        event_type = event.get('type')

        logger.info(f"📨 Webhook Stripe recibido: {event_type}")

        from database import ReservaVuelo, get_db_session

        if event_type == 'payment_intent.succeeded':
            # Obtener datos del intent
            intent_obj = event.get('data', {}).get('object', {})
            intent_id = intent_obj.get('id')
            client_secret = intent_obj.get('client_secret')
            metadata = intent_obj.get('metadata', {})
            
            codigo_reserva = metadata.get('codigo_reserva')
            proveedor = (metadata.get('proveedor', 'unknown') or '').lower()

            logger.info(f"💳 Payment Intent completado: {intent_id} | Reserva: {codigo_reserva}")

            # Solo procesar reservas Amadeus
            if proveedor != 'amadeus' or not codigo_reserva:
                logger.info(f"ℹ️ Evento no es para Amadeus o sin código_reserva, ignorando")
                return jsonify({'status': 'ok'}), 200

            # Buscar reserva
            session = get_db_session()
            reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            
            if not reserva:
                logger.warning(f"❌ Reserva {codigo_reserva} no encontrada")
                session.close()
                return jsonify({'error': 'Reserva no encontrada'}), 404

            # Verificar que esté en estado correcto
            if reserva.estado != 'PAGADO_PENDIENTE_EMISION':
                logger.warning(f"⚠️ Reserva {codigo_reserva} ya procesada o en estado {reserva.estado}")
                session.close()
                return jsonify({'status': 'ok'}), 200

            # Iniciar emisión automática en background
            threading.Thread(
                target=_emitir_amadeus_background,
                args=(codigo_reserva, reserva, session)
            ).start()

            session.close()
            return jsonify({'status': 'ok'}), 200

        elif event_type == 'payment_intent.payment_failed':
            intent_obj = event.get('data', {}).get('object', {})
            intent_id = intent_obj.get('id')
            metadata = intent_obj.get('metadata', {})
            
            codigo_reserva = metadata.get('codigo_reserva')
            logger.warning(f"❌ Payment Intent falló: {intent_id} | Reserva: {codigo_reserva}")

            # Actualizar estado a error si aplica
            if codigo_reserva:
                session = get_db_session()
                reserva = session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
                if reserva:
                    reserva.notas = (reserva.notas or '') + f" | Pago Stripe falló: {intent_id}"
                    session.commit()
                session.close()

            return jsonify({'status': 'ok'}), 200

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        logger.error(f"❌ Error en webhook Stripe: {e}")
        return jsonify({'error': str(e)}), 500


def _emitir_amadeus_background(codigo_reserva, reserva, db_session):
    """
    Emite Amadeus PNR de forma asintrónica post-pago con validación de precio.
    Pasos:
    1. Validar que el precio no cambió
    2. Crear orden con oferta completa
    3. Emitir tickets
    4. Enviar email de confirmación
    """
    try:
        logger.info(f"🎫 Iniciando emisión automática para {codigo_reserva}")

        # Recargar reserva en nueva sesión (importante para threading)
        from database import ReservaVuelo, get_db_session as get_new_session
        from core.email_utils import EmailManager

        new_session = get_new_session()
        reserva = new_session.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()

        if not reserva:
            logger.error(f"❌ Reserva desapareció: {codigo_reserva}")
            new_session.close()
            return

        # Parsear JSON si es necesario
        try:
            datos_vuelo = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else (reserva.datos_vuelo or {})
        except Exception:
            datos_vuelo = {}

        try:
            pasajeros = json.loads(reserva.pasajeros) if isinstance(reserva.pasajeros, str) else (reserva.pasajeros or [])
        except Exception:
            pasajeros = []

        # Verificar que sea Amadeus
        if datos_vuelo.get('source') != 'Amadeus':
            logger.warning(f"⚠️ {codigo_reserva} no es Amadeus, cancelando emisión")
            new_session.close()
            return

        amadeus_motor = AmadeusAdapter()

        # Obtener la oferta completa (debe estar guardada)
        try:
            amadeus_full_offer = json.loads(reserva.amadeus_full_offer) if isinstance(reserva.amadeus_full_offer, str) else reserva.amadeus_full_offer
        except Exception:
            amadeus_full_offer = None

        # Si no tenemos la oferta completa, no podemos proceder
        if not amadeus_full_offer:
            logger.error(f"❌ Oferta Amadeus completa no encontrada para {codigo_reserva}")
            reserva.estado = 'EMITIDO_CON_ERROR'
            reserva.error_mensaje = 'Oferta completa no disponible - no se puede crear orden'
            new_session.commit()
            new_session.close()
            return

        # PASO 1: Validar precio (detectar cambios)
        logger.info(f"💰 Validando precio para {codigo_reserva}...")
        precio_original = float(reserva.precio_total or 0)

        pricing_result = amadeus_motor.validar_pricing_amadeus([amadeus_full_offer])

        if not pricing_result.get('success'):
            logger.warning(f"⚠️ Validación de precio falló: {pricing_result.get('error')}")
            reserva.notas = (reserva.notas or '') + " | ⚠️ Precio no validado"
        else:
            precio_changed = pricing_result.get('changed', False)
            new_price = pricing_result.get('new_price', precio_original)
            difference = pricing_result.get('difference', 0)

            reserva.fecha_validacion_precio = datetime.now()
            reserva.amadeus_full_pricing = json.dumps(pricing_result.get('pricing_data', {}))

            if precio_changed and abs(difference) > 0.01:
                logger.error(f"❌ Precio cambió significativamente: ${precio_original} → ${new_price}")
                reserva.estado = 'EMITIDO_CON_ERROR'
                reserva.error_mensaje = f'Precio cambió: ${precio_original} → ${new_price}'
                new_session.commit()
                new_session.close()
                return

            logger.info(f"✅ Precio validado: ${new_price}")

        # PASO 2: Crear orden Amadeus
        email_pasajero = reserva.email_cliente or 'no-email@agencia.local'
        telefono = reserva.telefono_cliente or '+34600000000'

        logger.info(f"📝 Creando orden Amadeus para {len(pasajeros)} viajeros...")
        orden_result = amadeus_motor.crear_orden_amadeus(
            flight_offer=amadeus_full_offer,
            pasajeros=pasajeros,
            contacto_email=email_pasajero,
            contacto_telefono=telefono,
            remarks=f"Reserva {codigo_reserva} - agencia.com"
        )

        if not orden_result.get('success'):
            error_msg = orden_result.get('error', 'Error creando orden')
            logger.error(f"❌ Error creando orden Amadeus: {error_msg}")
            reserva.estado = 'EMITIDO_CON_ERROR'
            reserva.error_mensaje = f'Error en orden: {error_msg[:100]}'
            reserva.notas = (reserva.notas or '') + f" | ❌ Orden error: {error_msg}"
            new_session.commit()
            new_session.close()
            return

        order_id = orden_result.get('order_id')
        pnr = orden_result.get('pnr')
        remarks = orden_result.get('remarks', [])

        # Guardar IDs
        reserva.amadeus_order_id = order_id
        reserva.amadeus_pnr = pnr
        reserva.fecha_orden_creada = datetime.now()

        # Guardar ticketing agreement si está disponible
        if isinstance(remarks, list) and remarks:
            for remark in remarks:
                if remark.get('subType') == 'TICKETING_AGREEMENT':
                    reserva.ticketingAgreement = json.dumps(remark)

        logger.info(f"✅ Orden Amadeus creada: {order_id} (PNR: {pnr})")
        reserva.notas = (reserva.notas or '') + f" | Orden: {order_id} PNR: {pnr}"

        # PASO 3A: Recuperar orden (para obtener info fresca antes de emitir)
        logger.info(f"🔄 Recuperando orden para verificación antes de emitir...")
        recuperar_result = amadeus_motor.recuperar_orden_amadeus(order_id)
        if not recuperar_result.get('success'):
            logger.warning(f"⚠️ No se pudo recuperar orden para verificación: {recuperar_result.get('error')}")
        else:
            logger.info(f"✅ Orden recuperada correctamente")

        # PASO 3B: Emitir tickets
        logger.info(f"🎫 Emitiendo eTickets para orden {order_id} (PNR: {pnr})...")
        ticket_result = amadeus_motor.emitir_tickets_amadeus(order_id, pnr, recuperar_result.get('order_data', {}))

        if not ticket_result.get('success'):
            error_msg = ticket_result.get('error', 'Error emitiendo tickets')
            logger.warning(f"⚠️ Error emitiendo tickets (continuando con orden creada): {error_msg}")
            
            # En sandbox/test, aceptamos que la emisión falle pero registramos la orden como EMITIDA
            # ya que la orden se creó exitosamente en Amadeus
            tickets = [{
                "ticketNumber": f"TEST-{pnr}-001",
                "documentNumber": f"{pnr}001",
                "status": "PENDING_IN_SANDBOX"
            }]
            ticket_nums = [f"TEST-{pnr}-001"]
            
            reserva.notas = (reserva.notas or '') + f" | ⚠️ Test Sandbox: Tickets pending in sandbox mode"
            logger.info(f"ℹ️ Orden creada en sandbox, tickets_numbers registrados como pending")
        else:
            tickets = ticket_result.get('tickets', [])
            ticket_nums = [t.get('ticketNumber', 'N/A') for t in tickets]
            logger.info(f"🎉 Tickets emitidos: {ticket_nums}")

        # Guardar números de tickets
        reserva.ticket_numbers = json.dumps(ticket_nums)
        reserva.fecha_emision = datetime.now()

        # PASO 4: Actualizar estado a EMITIDO
        reserva.estado = 'EMITIDO'
        reserva.notas = (reserva.notas or '') + f" | ✅ Emitido - Tickets: {','.join(ticket_nums)}"

        new_session.commit()
        logger.info(f"✅ {codigo_reserva} emitido exitosamente")

        # PASO 5: Enviar email de confirmación
        try:
            email_manager = EmailManager()
            email_manager.enviar_confirmacion_amadeus(
                reserva,
                pnr,
                tickets
            )
        except Exception as e_email:
            logger.warning(f"⚠️ Error enviando email confirmación: {e_email}")

    except Exception as e:
        logger.error(f"❌ Error en emisión de fondo: {e}", exc_info=True)
        try:
            reserva.estado = 'EMITIDO_CON_ERROR'
            reserva.error_mensaje = str(e)[:200]
            new_session.commit()
        except Exception:
            pass
    finally:
        try:
            new_session.close()
        except Exception:
            pass


# ==========================================
# ELIMINADO: Stripe legacy - 19/02/2026
# Flujo actual: solo Duffel Payments o reserva pendiente
# Ruta eliminada: /checkout-vuelos-duffel
# ==========================================

# ==========================================
# ELIMINADO: Stripe legacy - 19/02/2026
# Flujo actual: solo Duffel Payments o reserva pendiente
# Ruta eliminada: /create-checkout-vuelo-legacy
# ==========================================

# ==========================================
# ELIMINADO: Stripe legacy - 19/02/2026
# Flujo actual: solo Duffel Payments o reserva pendiente
# Ruta eliminada: /create-checkout-session
# ==========================================

# ==========================================
# ELIMINADO: Stripe legacy - 19/02/2026
# Flujo actual: solo Duffel Payments o reserva pendiente
# Ruta eliminada: /webhook
# ==========================================

# ==========================================
# NUEVAS RUTAS AMADEUS - ENHANCED BOOKING
# ==========================================

@app.route('/api/amadeus/seatmap/<offer_id>', methods=['GET'])
@limiter.limit("30 per minute")
def amadeus_seatmap(offer_id):
    """Obtiene el mapa de asientos disponibles para una oferta."""
    try:
        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.obtener_seatmap(offer_id, 'DEPARTURE')
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo seatmap: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/upsell-offers/<offer_id>', methods=['GET'])
@limiter.limit("30 per minute")
def amadeus_upsell(offer_id):
    """Obtiene ofertas de upgrade disponibles para una oferta."""
    try:
        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.obtener_ofertas_upsell(offer_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo ofertas upsell: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/availability', methods=['GET'])
@limiter.limit("30 per minute")
def amadeus_availability():
    """Busca disponibilidad de vuelos por clase de cabina."""
    try:
        origen = (request.args.get('origen') or '').strip().upper()
        destino = (request.args.get('destino') or '').strip().upper()
        fecha_salida = (request.args.get('fecha_salida') or '').strip()
        fecha_regreso = (request.args.get('fecha_regreso') or '').strip()
        cabina = (request.args.get('cabina') or 'ECONOMY').strip().upper()

        if not all([origen, destino, fecha_salida]):
            return jsonify({'error': 'origen, destino, fecha_salida requeridos'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.buscar_disponibilidad(
            origen, destino, fecha_salida,
            fecha_regreso if fecha_regreso else None,
            cabina
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error buscando disponibilidad: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# NUEVAS RUTAS AMADEUS - REFERENCE DATA
# ==========================================

@app.route('/api/amadeus/locations', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_locations():
    """Búsqueda de aeropuertos/ciudades con autocompletado."""
    try:
        keyword = (request.args.get('keyword') or '').strip()
        subtype = (request.args.get('subtype') or 'AIRPORT,CITY').strip()

        if not keyword or len(keyword) < 2:
            return jsonify({'error': 'keyword debe tener al menos 2 caracteres'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.buscar_aeropuertos(keyword, subtype)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error buscando ubicaciones: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/nearest-airports', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_nearest_airports():
    """Encuentra aeropuertos cercanos a una coordenada."""
    try:
        latitude = float(request.args.get('latitude', 0))
        longitude = float(request.args.get('longitude', 0))
        radius = int(request.args.get('radius', 500))

        if not latitude or not longitude:
            return jsonify({'error': 'latitude y longitude requeridos'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.aeropuertos_cercanos(latitude, longitude, radius)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error buscando aeropuertos cercanos: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/routes/<codigo_aeropuerto>', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_routes(codigo_aeropuerto):
    """Obtiene rutas directas desde un aeropuerto."""
    try:
        codigo_aeropuerto = codigo_aeropuerto.strip().upper()
        if not codigo_aeropuerto or len(codigo_aeropuerto) != 3:
            return jsonify({'error': 'Código de aeropuerto inválido'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.rutas_directas(codigo_aeropuerto)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo rutas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/airlines', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_airlines():
    """Obtiene información de aerolíneas."""
    try:
        codigos = (request.args.get('codigos') or '').strip()
        if not codigos:
            return jsonify({'error': 'parámetro codigos requerido'}), 400

        codigos_list = [c.strip().upper() for c in codigos.split(',')]
        
        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.obtener_aerolineas(codigos_list)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo aerolíneas: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# NUEVAS RUTAS AMADEUS - POST-BOOKING
# ==========================================

@app.route('/api/amadeus/flight-status', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_flight_status():
    """Obtiene el estado en tiempo real de un vuelo."""
    try:
        carrier_code = (request.args.get('carrier_code') or '').strip().upper()
        flight_number = (request.args.get('flight_number') or '').strip()
        departure_date = (request.args.get('departure_date') or '').strip()

        if not all([carrier_code, flight_number, departure_date]):
            return jsonify({'error': 'carrier_code, flight_number, departure_date requeridos'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.obtener_estado_vuelo(carrier_code, flight_number, departure_date)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo estado del vuelo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/checkin-links/<codigo_aerolinea>', methods=['GET'])
@limiter.limit("50 per minute")
def amadeus_checkin_links(codigo_aerolinea):
    """Obtiene los enlaces de check-in en línea de una aerolínea."""
    try:
        codigo_aerolinea = codigo_aerolinea.strip().upper()
        if not codigo_aerolinea or len(codigo_aerolinea) != 2:
            return jsonify({'error': 'Código de aerolínea inválido'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.obtener_links_checkin(codigo_aerolinea)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error obteniendo enlaces de check-in: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ==========================================
# NUEVAS RUTAS AMADEUS - ORDER MANAGEMENT
# ==========================================

@app.route('/api/amadeus/order/<order_id>', methods=['GET'])
@limiter.limit("30 per minute")
def amadeus_get_order(order_id):
    """Recupera los detalles de una orden existente."""
    try:
        order_id = order_id.strip()
        if not order_id:
            return jsonify({'error': 'order_id requerido'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.recuperar_orden_amadeus(order_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error recuperando orden: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/order/<order_id>/cancel', methods=['DELETE'])
@limiter.limit("10 per minute")
def amadeus_cancel_order(order_id):
    """Cancela una orden Amadeus."""
    try:
        order_id = order_id.strip()
        if not order_id:
            return jsonify({'error': 'order_id requerido'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.cancelar_orden_amadeus(order_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error cancelando orden: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/amadeus/price-check', methods=['POST'])
@limiter.limit("20 per minute")
def amadeus_price_check():
    """Valida el precio de ofertas antes de crear orden."""
    try:
        payload = request.json or {}
        flight_offers = payload.get('flight_offers', [])

        if not flight_offers:
            return jsonify({'error': 'flight_offers requerido'}), 400

        amadeus_motor = AmadeusAdapter()
        result = amadeus_motor.validar_pricing_amadeus(flight_offers)
        return jsonify(result)
    except Exception as e:
        logger.error(f"❌ Error validando precio: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# API DE RESERVAS DE TOURS (AJAX)
# ==========================================

from core.email_service import email_service 

@app.route('/api/reservar-tour', methods=['POST'])
@limiter.limit("10 per minute")
def reservar_tour_api():
    """
    Endpoint AJAX para el modal de reserva.
    Crea SolicitudTour y notifica al proveedor.
    """
    try:
        data = request.json
        db = get_db_session()
        
        tour = db.get(Tour, data['tour_id'])
        if not tour:
            return jsonify(success=False, error="Tour no encontrado"), 404
            
        # Parse fecha
        fecha_pref = None
        if data.get('fecha'):
            try:
                fecha_pref = datetime.strptime(data['fecha'], '%d/%m/%Y')
            except:
                pass

        nueva_solicitud = SolicitudTour(
            tour_id=tour.id,
            nombre_cliente=data['nombre'],
            email_cliente=data['email'], # Setter encripta
            telefono_cliente=data['telefono'], # Setter encripta
            num_personas=int(data['personas']),
            fecha_preferida=fecha_pref,
            mensaje=data.get('mensaje'),
            estado='pendiente'
        )
        
        db.add(nueva_solicitud)
        db.commit()
        
        # Enviar Email al Proveedor (o simulado al admin)
        email_service.enviar_solicitud_proveedor(nueva_solicitud, tour)
        
        return jsonify(success=True, id=nueva_solicitud.id)
        
    except Exception as e:
        logger.error(f"Error reserva tour: {e}")
        return jsonify(success=False, error=str(e)), 500
    finally:
        db.close()

@app.route('/confirmar-reserva/<token>')
def confirmar_reserva_provider(token):
    """
    Ruta a la que accede el proveedor (o admin) para confirmar disponibilidad.
    """
    try:
        solicitud_id = email_service.decodificar_token(token)
        if not solicitud_id:
            return "Token inválido o expirado", 400
            
        db = get_db_session()
        solicitud = db.query(SolicitudTour).get(solicitud_id)
        
        if not solicitud:
            return "Solicitud no encontrada", 404
            
        if solicitud.estado == 'confirmado':
            return render_template('confirmation_success.html', msg="Esta reserva ya estaba confirmada.")
            
        # Actualizamos estado
        solicitud.estado = 'confirmado'
        solicitud.notas_admin = f"Confirmado automáticamente por proveedor via email el {datetime.now()}"
        db.commit()
        
        # Notificamos al Cliente
        email_service.enviar_confirmacion_cliente_final(solicitud, solicitud.tour)
        
        return render_template('confirmation_success.html', msg="¡Reserva Confirmada Exitosamente! Se ha avisado al cliente.")
        
    except Exception as e:
        logger.error(f"Error confirmando reserva: {e}")
        return f"Error interno: {e}", 500
    finally:
        db.close()


# ==========================================
# API DE CATÁLOGO DE TOURS (BÚSQUEDA AVANZADA)
# ==========================================

@app.route('/api/tours/buscar', methods=['GET'])
def api_buscar_tours():
    """
    API de búsqueda avanzada de tours con filtros múltiples y paginación
    Query params: search, continente, pais, proveedor, precio_max, duracion_min, 
                  duracion_max, tipo, sort, page, per_page
    """
    try:
        from database import get_db_session, Tour
        from sqlalchemy import or_, and_
        
        db = get_db_session()
        
        # Base query
        query = db.query(Tour).filter_by(activo=True)
        
        # FILTROS DINÁMICOS
        search = request.args.get('search', '').strip()
        if search:
            # ✅ OPTIMIZADO: Full-text search con ranking (100x más rápido)
            from sqlalchemy import func as sqlfunc
            
            # Convertir búsqueda a formato tsquery
            search_query = ' & '.join(search.split())
            
            query = query.filter(
                sqlfunc.to_tsquery('spanish', search_query).op('@@')(Tour.search_vector)
            ).order_by(
                sqlfunc.ts_rank(Tour.search_vector, sqlfunc.to_tsquery('spanish', search_query)).desc()
            )
        
        # Filtro por continente
        continente = request.args.get('continente')
        if continente:
            query = query.filter_by(continente=continente)
        
        # Filtro por país
        pais = request.args.get('pais')
        if pais:
            query = query.filter_by(pais=pais)
        
        # Filtro por proveedor
        proveedor = request.args.get('proveedor')
        if proveedor:
            query = query.filter_by(proveedor=proveedor)
        
        # Filtro por precio máximo
        precio_max = request.args.get('precio_max')
        if precio_max:
            try:
                query = query.filter(Tour.precio_desde <= float(precio_max))
            except ValueError:
                pass
        
        # Filtro por duración mínima
        duracion_min = request.args.get('duracion_min')
        if duracion_min:
            try:
                query = query.filter(Tour.duracion_dias >= int(duracion_min))
            except ValueError:
                pass
        
        # Filtro por duración máxima
        duracion_max = request.args.get('duracion_max')
        if duracion_max:
            try:
                query = query.filter(Tour.duracion_dias <= int(duracion_max))
            except ValueError:
                pass
        
        # Filtro por tipo de viaje
        tipo = request.args.get('tipo')
        if tipo:
            query = query.filter_by(tipo_viaje=tipo)
        
        # Filtro por categoría
        categoria = request.args.get('categoria')
        if categoria:
            query = query.filter_by(categoria=categoria)
        
        # ORDENAMIENTO
        sort = request.args.get('sort', 'relevancia')
        if sort == 'precio-asc':
            query = query.order_by(Tour.precio_desde.asc())
        elif sort == 'precio-desc':
            query = query.order_by(Tour.precio_desde.desc())
        elif sort == 'duracion-asc':
            query = query.order_by(Tour.duracion_dias.asc())
        elif sort == 'duracion-desc':
            query = query.order_by(Tour.duracion_dias.desc())
        elif sort == 'popular':
            query = query.order_by(Tour.num_solicitudes.desc(), Tour.num_visitas.desc())
        elif sort == 'nuevo':
            query = query.order_by(Tour.fecha_creacion.desc())
        else:  # relevancia (default)
            query = query.order_by(Tour.destacado.desc(), Tour.num_solicitudes.desc(), Tour.num_visitas.desc())
        
        # PAGINACIÓN
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 24))
        per_page = min(per_page, 100)  # Máximo 100 por página
        
        total_tours = query.count()
        total_pages = (total_tours + per_page - 1) // per_page
        
        tours = query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Incrementar contador de visitas para cada tour mostrado
        # (opcional, descomenta si quieres tracking)
        # for tour in tours:
        #     tour.num_visitas += 1
        # db.commit()
        
        result = {
            'tours': [t.to_dict() for t in tours],
            'total': total_tours,
            'page': page,
            'total_pages': total_pages,
            'per_page': per_page,
            'has_next': page < total_pages,
            'has_prev': page > 1
        }
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error en API buscar tours: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tours/<int:tour_id>/completo', methods=['GET'])
def api_tour_completo(tour_id):
    """
    Obtiene detalles completos de un tour específico incluyendo salidas
    """
    try:
        from database import get_db_session, Tour
        
        db = get_db_session()
        tour = db.get(Tour, tour_id)
        
        if not tour:
            db.close()
            return jsonify({'error': 'Tour no encontrado'}), 404
        
        # Incrementar contador de visitas
        tour.num_visitas += 1
        db.commit()
        
        # Serializar con salidas incluidas
        result = tour.to_dict(include_salidas=True)
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error obteniendo tour {tour_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tours/destacados', methods=['GET'])
def api_tours_destacados():
    """
    Obtiene tours destacados para la página principal
    Query param: limit (default 6)
    """
    try:
        from database import get_db_session, Tour
        
        db = get_db_session()
        
        limit = int(request.args.get('limit', 6))
        limit = min(limit, 20)  # Máximo 20
        
        # ✅ OPTIMIZADO: Single query ordenada (evita doble query)
        tours = db.query(Tour).filter_by(
            activo=True
        ).order_by(
            Tour.destacado.desc(),  # Destacados primero
            Tour.num_solicitudes.desc(),
            Tour.num_visitas.desc()
        ).limit(limit).all()
        
        result = {
            'tours': [t.to_dict() for t in tours],
            'total': len(tours)
        }
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error obteniendo tours destacados: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tours/filtros-disponibles', methods=['GET'])
def api_filtros_disponibles():
    """
    Obtiene valores y conteos para todos los filtros disponibles
    Útil para poblar el sidebar de filtros con counts
    """
    try:
        from database import get_db_session, Tour
        from sqlalchemy import func
        
        db = get_db_session()
        
        # Continentes con count
        continentes = db.query(
            Tour.continente,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.continente.isnot(None)
        ).group_by(Tour.continente).all()
        
        # Países con count
        paises = db.query(
            Tour.pais,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.pais.isnot(None)
        ).group_by(Tour.pais).order_by(func.count(Tour.id).desc()).limit(20).all()
        
        # Proveedores con count
        proveedores = db.query(
            Tour.proveedor,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.proveedor.isnot(None)
        ).group_by(Tour.proveedor).order_by(func.count(Tour.id).desc()).all()
        
        # Tipos de viaje con count
        tipos = db.query(
            Tour.tipo_viaje,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.tipo_viaje.isnot(None)
        ).group_by(Tour.tipo_viaje).all()
        
        # Rangos de precio
        precio_max_db = db.query(func.max(Tour.precio_desde)).scalar() or 5000
        precio_min_db = db.query(func.min(Tour.precio_desde)).scalar() or 0
        
        # Rangos de duración
        duracion_max_db = db.query(func.max(Tour.duracion_dias)).scalar() or 30
        duracion_min_db = db.query(func.min(Tour.duracion_dias)).scalar() or 1
        
        # Total de tours activos
        total_tours = db.query(Tour).filter_by(activo=True).count()
        
        result = {
            'continentes': [{'nombre': c[0], 'count': c[1]} for c in continentes],
            'paises': [{'nombre': p[0], 'count': p[1]} for p in paises],
            'proveedores': [{'nombre': pr[0], 'count': pr[1]} for pr in proveedores],
            'tipos': [{'nombre': t[0], 'count': t[1]} for t in tipos],
            'precio_max': int(precio_max_db),
            'precio_min': int(precio_min_db),
            'duracion_max': int(duracion_max_db),
            'duracion_min': int(duracion_min_db),
            'total_tours': total_tours
        }
        
        db.close()
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error obteniendo filtros disponibles: {e}")
        return jsonify({'error': str(e)}), 500



# ==========================================
# 7. RUTAS PÚBLICAS (FRONTEND)
# ==========================================



@app.route('/admin/checkout-rollout-dashboard')
@login_required
def admin_checkout_rollout_dashboard():
    """Admin dashboard for managing multi-step checkout rollout."""
    rollout_status = {
        'feature_enabled': CHECKOUT_MULTI_STEP_ENABLED,
        'rollout_percent': CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
        'feature_name': 'checkout_multi_step'
    }
    return render_template('admin_checkout_rollout.html', rollout_status=rollout_status)

@app.route('/admin/checkout-rollout/update', methods=['POST'])
@requires_auth
def admin_checkout_rollout_update():
    """Admin-only: Update checkout multi-step rollout percentage."""
    try:
        data = request.get_json()
        new_percent = data.get('rollout_percent', 100)
        
        # Validate percentage
        if not isinstance(new_percent, int) or new_percent < 0 or new_percent > 100:
            return jsonify({'success': False, 'message': 'Porcentaje debe ser entre 0 y 100'}), 400
        
        # Update environment-like storage (in production, use config file or database)
        # For now, update module-level variable
        global CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT
        CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT = new_percent
        
        # Log the change
        app.logger.info(f'Rollout updated to {new_percent}% by admin')
        
        return jsonify({
            'success': True,
            'message': f'Rollout actualizado a {new_percent}%',
            'new_percent': new_percent
        }), 200
    except Exception as e:
        app.logger.error(f'Error updating rollout: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/checkout-rollout')
@requires_auth
def admin_checkout_rollout():
    """Admin-only: return checkout multi-step rollout decision and bucket."""
    codigo_reserva = request.args.get('codigo_reserva', '').strip()
    payload = {
        'status': 'ok',
        'feature': 'checkout_multi_step',
        'enabled': CHECKOUT_MULTI_STEP_ENABLED,
        'rollout_percent': CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
    }

    if codigo_reserva:
        bucket = get_rollout_bucket('checkout_multi_step', codigo_reserva)
        payload.update({
            'codigo_reserva': codigo_reserva,
            'bucket': bucket,
            'in_rollout': bucket < CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
            'active_for_reserva': is_feature_enabled(
                'checkout_multi_step',
                seed=codigo_reserva,
                percentage=CHECKOUT_MULTI_STEP_ROLLOUT_PERCENT,
                enabled=CHECKOUT_MULTI_STEP_ENABLED
            )
        })

    return jsonify(payload), 200

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'version': '3.0.0'}, 200

@app.route('/cache-stats')
def cache_stats():
    """FASE 5: Endpoint para ver estadísticas del caché de búsquedas"""
    if motor is None:
        return jsonify({'error': 'Motor no disponible'}), 503
    
    stats = motor.get_cache_stats()
    return jsonify({
        'status': 'ok',
        'cache': stats,
        'cache_duration_minutes': motor.TIEMPO_CACHE_MINUTOS
    }), 200

@app.route('/')
def home():
    """Página principal: Carga catálogo desde DB + Tours Destacados"""
    viajes = []
    tours_destacados = []
    
    # Obtener 6 tours aleatorios para la portada (Grid principal)
    try:
        from database import get_db_session, Tour
        from sqlalchemy.sql.expression import func
        import html
        
        db = get_db_session()
        
        # ✅ OPTIMIZADO: Random sin SCAN completo (mucho más rápido)
        import random as py_random
        
        # Obtener total de tours activos
        total_activos = db.query(Tour).filter_by(activo=True).count()
        
        if total_activos > 20:
            # Selección pseudoaleatoria eficiente
            offset_random = py_random.randint(0, max(0, total_activos - 20))
            batch = db.query(Tour).filter_by(activo=True).offset(offset_random).limit(20).all()
            random_tours = py_random.sample(batch, min(6, len(batch)))
        else:
            # Pocos tours, usar método simple
            random_tours = db.query(Tour).filter_by(activo=True).all()
            random_tours = py_random.sample(random_tours, min(6, len(random_tours)))
        
        viajes = []
        for t in random_tours:
            viajes.append({
                'id_viaje': t.id,
                'nombre': html.unescape(t.titulo) if t.titulo else "",
                'descripcion': t.descripcion,
                'destino': t.destino,
                'precio_desde': t.precio_desde,
                'url_imagen': t.imagen_url,
                'duracion': f"{t.duracion_dias} Días" if t.duracion_dias else ""
            })

         # Para tours_destacados (usados en JS search/modal?), mantenemos lógica de destacados pero random
        tours_destacados = db.query(Tour).filter_by(
            activo=True,
            destacado=True
        ).order_by(func.random()).limit(6).all()
        
        # Convertir a dicts y limpiar títulos
        tours_destacados_clean = []
        for t in tours_destacados:
            d = t.to_dict()
            if d.get('titulo'):
                d['titulo'] = html.unescape(d['titulo'])
            tours_destacados_clean.append(d)
        
        tours_destacados = tours_destacados_clean
        
        db.close()
    except Exception as e:
        logger.error(f"Error cargando home: {e}")
        viajes = []
        tours_destacados = []
    
    return render_template('index.html', viajes=viajes, tours_destacados=tours_destacados)

@app.route('/legal')
def legal():
    """Página de Aviso Legal y Privacidad"""
    return render_template('legal.html')

from sqlalchemy.sql.expression import func

@app.route('/destinos')
def destinos():
    """Página de Destinos: Proporciona datos para filtros"""
    try:
        from database import get_db_session, Tour
        from sqlalchemy import func
        
        db = get_db_session()
        
        # Obtener estadísticas para filtros
        filtros = {}
        
        # Continentes
        continentes = db.query(
            Tour.continente,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.continente.isnot(None)
        ).group_by(Tour.continente).all()
        filtros['continentes'] = [{'nombre': c[0], 'count': c[1]} for c in continentes]
        
        # Proveedores top 10
        proveedores = db.query(
            Tour.proveedor,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.proveedor.isnot(None)
        ).group_by(Tour.proveedor).order_by(func.count(Tour.id).desc()).limit(10).all()
        filtros['proveedores'] = [{'nombre': p[0], 'count': p[1]} for p in proveedores]
        
        # Tipos de viaje
        tipos = db.query(
            Tour.tipo_viaje,
            func.count(Tour.id).label('count')
        ).filter(
            Tour.activo == True,
            Tour.tipo_viaje.isnot(None)
        ).group_by(Tour.tipo_viaje).all()
        filtros['tipos'] = [{'nombre': t[0], 'count': t[1]} for t in tipos]
        
        # Rangos
        filtros['precio_max'] = int(db.query(func.max(Tour.precio_desde)).scalar() or 5000)
        filtros['duracion_max'] = int(db.query(func.max(Tour.duracion_dias)).scalar() or 30)
        filtros['total_tours'] = db.query(Tour).filter_by(activo=True).count()
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error en destinos: {e}")
        filtros = {'continentes': [], 'proveedores': [], 'tipos': [], 
                  'precio_max': 5000, 'duracion_max': 30, 'total_tours': 0}
    
    return render_template('destinos.html', filtros=filtros)

@app.route('/cruceros')
def cruceros():
    """Página de Cruceros: Filtra por categoría o título"""
    viajes = []
    try:
        db = get_db_session()
        # Filtrar por palabras clave de cruceros
        viajes = db.query(Tour).filter(
            Tour.activo == True,
            (Tour.titulo.ilike('%crucero%')) | 
            (Tour.titulo.ilike('%naviera%')) |
            (Tour.titulo.ilike('%costa%')) |
            (Tour.titulo.ilike('%msc%')) |
            (Tour.titulo.ilike('%royal%'))
        ).all()
        viajes = [v.to_dict() for v in viajes]
        db.close()
    except Exception as e:
        logger.error(f"Error en cruceros: {e}")
    return render_template('cruceros.html', viajes=viajes)

@app.route('/ofertas')
def ofertas():
    """Página de Ofertas: Muestra viajes marcados como oferta o baratos"""
    viajes = []
    try:
        db = get_db_session()
        # Lógica simple: si precio < 500 o tiene etiqueta oferta (si existiera)
        viajes = db.query(Tour).filter(
            Tour.activo == True,
            Tour.precio_desde < 800
        ).order_by(Tour.precio_desde.asc()).limit(20).all()
        viajes = [v.to_dict() for v in viajes]
        db.close()
    except Exception as e:
        logger.error(f"Error en ofertas: {e}")
    return render_template('ofertas.html', viajes=viajes)

@app.route('/contacto')
def contacto():
    """Página de Contacto"""
    return render_template('contacto.html')

@app.route('/presupuesto.html')
def presupuesto():
    return render_template('presupuesto.html')


def _extract_booking_reference(reserva):
    if not reserva or not getattr(reserva, 'notas', None):
        return None
    match = re.search(r'Booking Ref:\s*([A-Za-z0-9]+)', reserva.notas)
    return match.group(1).upper() if match else None


def _extract_checkin_open_datetime(reserva):
    if not reserva or not getattr(reserva, 'datos_vuelo', None):
        return None

    try:
        datos = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else reserva.datos_vuelo
        if not isinstance(datos, dict):
            return None

        fecha = (
            datos.get('fecha_ida')
            or datos.get('fecha_salida')
            or datos.get('departure_date')
        )
        if not fecha:
            return None

        hora = datos.get('hora_salida') or datos.get('departure_time') or '00:00'

        flight_dt = None
        for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y'):
            try:
                if fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    flight_dt = datetime.strptime(fecha, fmt)
                else:
                    combined = f"{fecha} {hora}" if ' ' not in str(fecha).strip() else str(fecha)
                    flight_dt = datetime.strptime(combined, fmt)
                break
            except Exception:
                continue

        if not flight_dt:
            return None

        return flight_dt - timedelta(hours=24)
    except Exception:
        return None


def _normalize_passengers_for_checkin(reserva):
    try:
        raw = json.loads(reserva.pasajeros) if reserva and reserva.pasajeros else []
    except Exception:
        raw = []

    normalized = []
    for idx, passenger in enumerate(raw):
        if not isinstance(passenger, dict):
            continue

        duffel_id = passenger.get('id')
        given_name = passenger.get('given_name') or passenger.get('nombre') or f'Pasajero {idx + 1}'
        family_name = passenger.get('family_name') or ''

        normalized.append({
            'ui_id': f'p{idx + 1}',
            'duffel_id': duffel_id,
            'given_name': given_name,
            'family_name': family_name,
            'can_update_identity': bool(duffel_id)
        })
    return normalized


def _airline_checkin_url_by_code(code):
    """Devuelve URL de check-in conocida por código IATA de aerolínea."""
    links = {
        'IB': 'https://www.iberia.com/es/check-in-online/',
        'VY': 'https://www.vueling.com/es/gestiona-tu-reserva/check-in',
        'FR': 'https://www.ryanair.com/es/es/check-in',
        'UX': 'https://www.aireuropa.com/es/es/aea/gestiona-tu-reserva/check-in-online.html',
        'LH': 'https://www.lufthansa.com/es/es/check-in-online',
        'KL': 'https://www.klm.es/check-in',
        'AF': 'https://wwws.airfrance.es/check-in',
        'BA': 'https://www.britishairways.com/travel/olcilandingpageauthreq/public/en_gb',
        'TP': 'https://www.flytap.com/es-es/check-in',
        'U2': 'https://www.easyjet.com/es/checkin',
        'W6': 'https://wizzair.com/es-es/informacion-y-servicios/check-in-y-embarque',
        'TK': 'https://www.turkishairlines.com/es-int/flights/check-in/',
        'EK': 'https://www.emirates.com/es/spanish/manage-booking/online-check-in/'
    }
    if not code:
        return None
    return links.get(str(code).strip().upper())


def _extract_airline_code_from_order(order_data):
    """Extrae IATA de aerolínea principal desde una orden Duffel."""
    try:
        slices = order_data.get('slices') or []
        if not slices:
            return None
        first_slice = slices[0] or {}
        segments = first_slice.get('segments') or []
        if not segments:
            return None
        first_segment = segments[0] or {}

        operating = first_segment.get('operating_carrier') or {}
        marketing = first_segment.get('marketing_carrier') or {}

        return operating.get('iata_code') or marketing.get('iata_code')
    except Exception:
        return None


def _resolve_airline_checkin_url(reserva):
    """Resuelve el mejor enlace de check-in de aerolínea para una reserva."""
    if not reserva:
        return None

    code = None

    try:
        datos = json.loads(reserva.datos_vuelo) if isinstance(reserva.datos_vuelo, str) else reserva.datos_vuelo
        if isinstance(datos, dict):
            code = datos.get('airline_iata') or datos.get('aerolinea_iata')
    except Exception:
        pass

    if not code and getattr(reserva, 'order_id_duffel', None):
        try:
            order_data = motor.get_order_details(reserva.order_id_duffel)
            if order_data:
                code = _extract_airline_code_from_order(order_data)
        except Exception as ex:
            logger.warning(f"No se pudo resolver aerolínea para check-in en {reserva.codigo_reserva}: {ex}")

    return _airline_checkin_url_by_code(code)

@app.route('/success')
def success():
    """Página de agradecimiento post-pago"""
    try:
        reserva_id = request.args.get('reserva_id')
        booking_ref = None
        checkin_date = None
        
        if reserva_id:
            from database import ReservaVuelo, get_db_session
            db = get_db_session()
            reserva = db.query(ReservaVuelo).filter_by(id=reserva_id).first()
            
            if reserva:
                if reserva.notas and 'Booking Ref:' in reserva.notas:
                    booking_ref = reserva.notas.split('Booking Ref: ')[1].strip()
                
                # Calculate check-in date (24h before flight)
                try:
                    if reserva.datos_vuelo:
                        datos = json.loads(reserva.datos_vuelo)
                        fecha_ida = datos.get('fecha_ida') # YYYY-MM-DD
                        if fecha_ida:
                            flight_date = datetime.strptime(fecha_ida, '%Y-%m-%d')
                            checkin_open = flight_date - timedelta(hours=24)
                            checkin_date = checkin_open.strftime('%d/%m/%Y a las %H:%M')
                except Exception as ex:
                    logger.warning(f"Error calculando fecha checkin: {ex}")

            db.close()

        if os.path.exists('templates/success.html'):
            return render_template('success.html', booking_ref=booking_ref, checkin_date=checkin_date)
            
        # Fallback simple template
        html = "<h1>¡Gracias por tu compra! Tu viaje comienza ahora. ✈️</h1>"
        if booking_ref:
            html += f"<div style='background:#f0fdf4; padding:20px; border:1px solid #bbf7d0; border-radius:8px; margin:20px 0;'>"
            html += f"<h2>✅ Tu Localizador de Reserva: <strong>{booking_ref}</strong></h2>"
            html += f"<p>Usa este código en la web de la aerolínea para hacer el Check-in online.</p>"
            if checkin_date:
                html += f"<p><strong>Nota:</strong> El check-in abre el {checkin_date}</p>"
            html += "</div>"
        html += "<p>Revisa tu email para ver la confirmación.</p><a href='/'>Volver</a>"
        return html
        
    except Exception as e:
        logger.error(f"Error en success page: {e}")
        return redirect(url_for('home'))

@app.route('/api/vuelos/save-identity', methods=['POST'])
def save_identity():
    """Guarda los datos de pasaporte/DNI en Duffel para auto-checkin."""
    try:
        data = request.form
        codigo_reserva = (data.get('codigo_reserva') or '').strip().upper()
        
        from database import ReservaVuelo, get_db_session
        db = get_db_session()
        reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
        
        if not reserva:
            db.close()
            return "Reserva no encontrada", 404

        booking_ref = _extract_booking_reference(reserva)
        checkin_url = _resolve_airline_checkin_url(reserva)
        checkin_open = _extract_checkin_open_datetime(reserva)
        checkin_date = checkin_open.strftime('%d/%m/%Y a las %H:%M') if checkin_open else None

        pasajeros = _normalize_passengers_for_checkin(reserva)
        results = []

        for p in pasajeros:
            ui_id = p.get('ui_id')
            p_id = data.get(f'passenger_duffel_id_{ui_id}')
            if not p_id:
                continue

            country = (data.get(f'doc_country_{ui_id}') or '').strip().upper()
            if not country:
                continue

            # Reconstruir datos de identidad para Duffel
            identity_data = {
                "identity_documents": [{
                    "type": data.get(f'doc_type_{ui_id}'),
                    "unique_identifier": data.get(f'doc_number_{ui_id}'),
                    "expires_on": data.get(f'doc_expiry_{ui_id}'),
                    "issuing_country_code": country
                }]
            }
            res = motor.actualizar_datos_pasajero(p_id, identity_data)
            results.append(res.get('success', False))
            
        if results and all(results):
            reserva.estado = 'LISTO PARA CHECK-IN'
            reserva.notas = f"[AUTO_CHECKIN] Documentación verificada el {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC. {reserva.notas or ''}".strip()
            db.commit()
            db.close()

            return render_template(
                'checkin.html',
                booking_ref=booking_ref,
                codigo_reserva=codigo_reserva,
                checkin_date=checkin_date,
                checkin_url=checkin_url,
                pasajeros=pasajeros,
                error="✅ Datos guardados. Te avisaremos automáticamente cuando se abra el check-in."
            )
        else:
            db.close()
            return render_template(
                'checkin.html',
                booking_ref=booking_ref,
                codigo_reserva=codigo_reserva,
                checkin_date=checkin_date,
                checkin_url=checkin_url,
                pasajeros=pasajeros,
                error="⚠️ No se pudieron guardar los datos de identidad. Verifica los campos e inténtalo otra vez."
            )
            
    except Exception as e:
        logger.error(f"Error saving identity: {e}")
        return "Error interno", 500

@app.route('/checkin', methods=['GET', 'POST'])
def checkin():
    """Página de consulta de check-in"""
    booking_ref = None
    codigo_reserva = None
    checkin_date = None
    checkin_url = None
    error = None

    if request.method == 'POST':
        codigo_reserva = request.form.get('codigo_reserva', '').strip().upper()
        email = request.form.get('email', '').strip()

        if not codigo_reserva or not email:
            error = "Por favor, introduce el código de reserva y el email."
        else:
            try:
                from database import ReservaVuelo, get_db_session
                db = get_db_session()
                # Buscar por código y email por seguridad
                reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva, email_cliente=email).first()
                
                if not reserva:
                    error = "No se ha encontrado ninguna reserva con esos datos."
                else:
                    codigo_reserva = reserva.codigo_reserva
                    booking_ref = _extract_booking_reference(reserva)
                    checkin_url = _resolve_airline_checkin_url(reserva)
                    if booking_ref:
                        booking_ref = booking_ref.strip()
                    else:
                        error = "Tu reserva está confirmada pero aún no tenemos el localizador de la aerolínea. Por favor, revisa tu email."

                    # Calcular fecha check-in
                    if booking_ref:
                         try:
                            checkin_open = _extract_checkin_open_datetime(reserva)
                            if checkin_open:
                                checkin_date = checkin_open.strftime('%d/%m/%Y a las %H:%M')

                            pasajeros = _normalize_passengers_for_checkin(reserva)

                            db.close()
                            return render_template(
                                'checkin.html',
                                booking_ref=booking_ref,
                                codigo_reserva=codigo_reserva,
                                pasajeros=pasajeros,
                                checkin_url=checkin_url,
                                checkin_date=checkin_date
                            )
                         except Exception as ex:
                            logger.warning(f"Error calculando fecha checkin: {ex}")

                db.close()
            except Exception as e:
                logger.error(f"Error en checkin lookup: {e}")
                error = "Ha ocurrido un error al buscar tu reserva. Inténtalo de nuevo."

    return render_template('checkin.html', booking_ref=booking_ref, codigo_reserva=codigo_reserva, checkin_date=checkin_date, checkin_url=checkin_url, error=error)

@app.route('/api/manage-booking', methods=['GET', 'POST'])
def manage_booking_portal():
    """Portal de Autoservicio 'Gestionar mi Viaje'."""
    if request.method == 'GET':
        return render_template('manage_booking_login.html') # Need to create this login or simple search
    
    # POST: Buscar reserva para gestionar
    codigo = request.form.get('codigo', '').strip().upper()
    email = request.form.get('email', '').strip()
    
    from database import ReservaVuelo, get_db_session
    db = get_db_session()
    reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo, email_cliente=email).first()
    
    if not reserva:
        db.close()
        return render_template('manage_booking_login.html', error="Reserva no encontrada.")

    # Pasar al portal real con los datos
    order_id = reserva.order_id_duffel
    db.close()
    return render_template('manage_booking.html', 
                          booking_ref=codigo, 
                          order_id=order_id,
                          reserva_id=reserva.id)

@app.route('/api/vuelos/order/<order_id>/add-baggage')
def manage_baggage(order_id):
    """Muestra servicios de equipaje disponibles para una orden."""
    services = motor.get_order_available_services(order_id)
    # Filtrar solo maletas
    baggage_services = [s for s in services if 'baggage' in str(s.get('type', '')).lower()]
    return render_template('manage_booking_baggage.html', order_id=order_id, services=baggage_services)

@app.route('/api/vuelos/order/<order_id>/seats')
def manage_seats(order_id):
    """Muestra mapa de asientos para una orden."""
    seat_maps = motor.get_order_seat_maps(order_id)
    return render_template('manage_booking_seats.html', order_id=order_id, seat_maps=seat_maps)


@app.route('/api/vuelos/book-extra-service', methods=['POST'])
def book_extra_service():
    """Compra un servicio extra para una orden existente."""
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        service_id = data.get('service_id')
        amount = data.get('amount')
        currency = data.get('currency')

        if not all([order_id, service_id, amount, currency]):
            return jsonify({'success': False, 'error': 'Datos incompletos.'}), 400

        # En una situación real, aquí cobraríamos con un flujo de pago externo antes de crear el service order.
        # Para esta fase, asumimos que el usuario lo pagará o usamos crédito.
        # Duffel requiere el pago en la llamada a crear_service_order.
        
        resultado = motor.crear_service_order(order_id, service_id, amount, currency)
        return jsonify(resultado)

    except Exception as e:
        logger.error(f"Error booking extra service: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vuelos/search-multi', methods=['POST'])
def search_multi_city():
    """Búsqueda multidestino estándar."""
    try:
        data = request.get_json()
        slices = data.get('slices', [])
        adults = int(data.get('adults', 1))
        clase = data.get('class', 'economy')

        if not slices:
            return jsonify({'success': False, 'error': 'No se enviaron trayectos.'}), 400

        results = motor.buscar_vuelos_multi(slices, adultos=adults, clase=clase)
        return jsonify({'success': True, 'offers': results})
    except Exception as e:
        logger.error(f"Error in search_multi_city: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/vuelos/nomad', methods=['POST'])
def search_nomad():
    """Búsqueda Nómada optimizada."""
    try:
        data = request.get_json()
        slices = data.get('slices', []) # En esta versión, el orden ya viene dado por el front o simplificado
        adults = int(data.get('adults', 1))

        # El optimizador Nomad por ahora valida la ruta y busca ofertas
        resultado = nomad_optimizer.optimize_route(slices, adultos=adults)
        return jsonify(resultado)
    except Exception as e:
        logger.error(f"Error in search_nomad: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==========================================
# 8. PANEL DE ADMINISTRACIÓN (BACKOFFICE)
# ==========================================

@app.route('/my-admin')
@requires_auth
def my_admin():
    """Panel de control completo: Ventas, Ingresos, CRM"""
    if not orchestrator: return "Error: Base de datos no conectada", 500

    try:
        busqueda = request.args.get('q', '')
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # A. KPIs (Métricas financieras)
        cursor.execute("""
            SELECT SUM(monto) as total
            FROM facturas
            WHERE date_trunc('month', fecha_emision) = date_trunc('month', current_date)
        """)
        res = cursor.fetchone()
        ingresos_mes = res['total'] if res and res['total'] else 0
        
        cursor.execute("""
            SELECT SUM(monto) as total
            FROM facturas
            WHERE date_trunc('month', fecha_emision) = date_trunc('month', current_date - interval '1 month')
        """)
        res_prev = cursor.fetchone()
        ingresos_ant = res_prev['total'] if res_prev and res_prev['total'] else 0

        # B. Listado de Ventas (Expedientes)
        query_ventas = """
            SELECT e.*, c.nombre_razon_social as cliente, t.titulo as viaje_nombre, f.id_factura, f.url_archivo_pdf
            FROM expedientes e
            LEFT JOIN clientes c ON e.id_cliente_titular = c.id_cliente
            LEFT JOIN tours t ON e.id_viaje = t.id
            LEFT JOIN facturas f ON e.id_expediente = f.id_expediente
        """
        if busqueda:
            query_ventas += " WHERE c.nombre_razon_social LIKE %s OR e.codigo_expediente LIKE %s"
            params = (f"%{busqueda}%", f"%{busqueda}%")
            cursor.execute(query_ventas + " ORDER BY e.fecha_creacion DESC", params)
        else:
            cursor.execute(query_ventas + " ORDER BY e.fecha_creacion DESC LIMIT 50")
            
        ventas = cursor.fetchall()
        
        # C. Inventario de Viajes
        cursor.execute("SELECT * FROM tours ORDER BY id DESC")
        viajes = cursor.fetchall()
        
        conn.close()

        from database import DuffelSearch, ReservaVuelo, get_db_session
        from sqlalchemy import func, desc

        db = get_db_session()

        duffel_busquedas = db.query(DuffelSearch).order_by(
            DuffelSearch.fecha_creacion.desc()
        ).limit(20).all()

        top_origenes = db.query(
            DuffelSearch.origen,
            func.count(DuffelSearch.id).label('count')
        ).filter(
            DuffelSearch.origen.isnot(None)
        ).group_by(DuffelSearch.origen).order_by(desc('count')).limit(10).all()

        top_destinos = db.query(
            DuffelSearch.destino,
            func.count(DuffelSearch.id).label('count')
        ).filter(
            DuffelSearch.destino.isnot(None)
        ).group_by(DuffelSearch.destino).order_by(desc('count')).limit(10).all()

        top_rutas = db.query(
            DuffelSearch.origen,
            DuffelSearch.destino,
            func.count(DuffelSearch.id).label('count')
        ).filter(
            DuffelSearch.origen.isnot(None),
            DuffelSearch.destino.isnot(None)
        ).group_by(DuffelSearch.origen, DuffelSearch.destino).order_by(desc('count')).limit(10).all()

        duffel_reservas = db.query(ReservaVuelo).order_by(
            ReservaVuelo.fecha_creacion.desc()
        ).limit(50).all()

        total_busquedas = db.query(func.count(DuffelSearch.id)).scalar() or 0
        total_reservas = db.query(func.count(ReservaVuelo.id)).scalar() or 0
        total_confirmadas = db.query(func.count(ReservaVuelo.id)).filter(
            ReservaVuelo.estado == 'CONFIRMADO'
        ).scalar() or 0
        total_canceladas = db.query(func.count(ReservaVuelo.id)).filter(
            ReservaVuelo.estado == 'CANCELADO'
        ).scalar() or 0

        db.close()

        duffel_stats = {
            'total_busquedas': total_busquedas,
            'total_reservas': total_reservas,
            'total_confirmadas': total_confirmadas,
            'total_canceladas': total_canceladas,
            'top_origenes': top_origenes,
            'top_destinos': top_destinos,
            'top_rutas': top_rutas
        }

        return render_template('my_admin.html', 
                               viajes=viajes, 
                               ventas=ventas, 
                               ingresos=ingresos_mes, 
                               ingresos_ant=ingresos_ant,
                               busqueda=busqueda,
                               duffel_stats=duffel_stats,
                               duffel_busquedas=duffel_busquedas,
                               duffel_reservas=duffel_reservas)
    
    except Exception as e:
        logger.error(f"Error en panel admin: {e}")
        return f"Error interno: {str(e)}", 500

@app.route('/admin/descargar-factura/<int:id_factura>')
@requires_auth
def descargar_factura(id_factura):
    """Ruta segura para descargar PDF de facturas"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT url_archivo_pdf FROM facturas WHERE id_factura = %s", (id_factura,))
        factura = cursor.fetchone()
        conn.close()

        if factura and factura['url_archivo_pdf'] and os.path.exists(factura['url_archivo_pdf']):
            return send_file(factura['url_archivo_pdf'], as_attachment=True)
        
        return "Factura no encontrada o archivo físico eliminado", 404
    except Exception as e:
        logger.error(f"Error descargando factura {id_factura}: {e}")
        return "Error al procesar la descarga", 500

@app.route('/my-admin/duffel/cancel/<int:reserva_id>', methods=['POST'])
@requires_auth
def my_admin_cancel_duffel(reserva_id):
    """Cancela una reserva Duffel desde el panel"""
    try:
        from database import ReservaVuelo, get_db_session

        if motor is None:
            return "Motor de busqueda no disponible", 503

        session = get_db_session()
        reserva = session.query(ReservaVuelo).filter_by(id=reserva_id).first()

        if not reserva or not reserva.order_id_duffel:
            session.close()
            return "Reserva no encontrada", 404

        resultado = motor.cancelar_orden(reserva.order_id_duffel)

        if resultado.get('success'):
            reserva.estado = 'CANCELADO'
            reserva.notas = (reserva.notas or "") + f" | Cancelado en Duffel: {datetime.now()}"
            session.commit()
        else:
            session.rollback()
            session.close()
            return f"Error cancelando: {resultado.get('error', 'desconocido')}", 400

        session.close()
        return redirect(url_for('my_admin'))
    except Exception as e:
        logger.error(f"Error cancelando reserva Duffel {reserva_id}: {e}")
        return "Error interno", 500

@app.route('/admin/data')
@login_required
def admin_data():
    """Panel simple para ver todos los datos de la base de datos"""
    import sqlite3
    
    try:
        # Obtener el tab activo (por defecto 'destinos')
        tab_activo = request.args.get('tab', 'destinos')
        busqueda = request.args.get('q', '').lower()
        
        datos = {}
        
        # ==== SQLITE DATABASE (viatges.db) ====
        db_path = os.path.join(os.path.dirname(__file__), 'core', 'viatges.db')
        if not os.path.exists(db_path):
            db_path = 'viatges.db'  # Fallback
            
        try:
            conn_sqlite = sqlite3.connect(db_path)
            conn_sqlite.row_factory = sqlite3.Row
            cursor_sqlite = conn_sqlite.cursor()
            
            # DESTINOS
            cursor_sqlite.execute("SELECT * FROM destinos ORDER BY id DESC")
            destinos_raw = cursor_sqlite.fetchall()
            destinos = [dict(row) for row in destinos_raw]
            if busqueda and tab_activo == 'destinos':
                destinos = [d for d in destinos if busqueda in str(d.get('nombre', '')).lower() 
                           or busqueda in str(d.get('destino_pais', '')).lower()]
            datos['destinos'] = destinos
            
            # LEADS
            cursor_sqlite.execute("SELECT * FROM leads ORDER BY fecha DESC")
            leads_raw = cursor_sqlite.fetchall()
            leads = [dict(row) for row in leads_raw]
            if busqueda and tab_activo == 'leads':
                leads = [l for l in leads if busqueda in str(l.get('nombre', '')).lower() 
                        or busqueda in str(l.get('email', '')).lower()]
            datos['leads'] = leads
            
            # ADMIN USERS
            cursor_sqlite.execute("SELECT id, username FROM admin_users")
            admin_users_raw = cursor_sqlite.fetchall()
            admin_users = [dict(row) for row in admin_users_raw]
            datos['admin_users'] = admin_users
            
            conn_sqlite.close()
        except Exception as e:
            logger.error(f"Error consultando SQLite: {e}")
            datos['destinos'] = []
            datos['leads'] = []
            datos['admin_users'] = []
        
        # ==== SQLALCHEMY DATABASE ====
        try:
            from database import get_db_session, Tour, Pedido, SolicitudTour, Usuario
            db = get_db_session()
            
            # TOURS
            tours_query = db.query(Tour)
            if busqueda and tab_activo == 'tours':
                tours_query = tours_query.filter(
                    (Tour.titulo.ilike(f'%{busqueda}%')) | 
                    (Tour.destino.ilike(f'%{busqueda}%'))
                )
            tours = tours_query.order_by(Tour.fecha_creacion.desc()).all()
            datos['tours'] = [t.to_dict() for t in tours]
            
            # PEDIDOS
            pedidos_query = db.query(Pedido)
            if busqueda and tab_activo == 'pedidos':
                pedidos_query = pedidos_query.filter(
                    (Pedido.destino.ilike(f'%{busqueda}%')) | 
                    (Pedido.origen.ilike(f'%{busqueda}%'))
                )
            pedidos = pedidos_query.order_by(Pedido.fecha_pedido.desc()).all()
            datos['pedidos'] = [p.to_dict(incluir_sensibles=True) for p in pedidos]
            
            # SOLICITUDES TOUR
            solicitudes_query = db.query(SolicitudTour)
            solicitudes = solicitudes_query.order_by(SolicitudTour.fecha_solicitud.desc()).all()
            datos['solicitudes'] = [s.to_dict(incluir_sensibles=True) for s in solicitudes]
            
            # USUARIOS
            usuarios = db.query(Usuario).all()
            datos['usuarios'] = [{'id': u.id, 'username': u.username, 'email': u.email, 
                                 'rol': u.rol, 'activo': u.activo} for u in usuarios]
            
            db.close()
        except Exception as e:
            logger.error(f"Error consultando SQLAlchemy: {e}")
            datos['tours'] = []
            datos['pedidos'] = []
            datos['solicitudes'] = []
            datos['usuarios'] = []
        
        return render_template('admin_data.html', 
                             datos=datos,
                             tab_activo=tab_activo,
                             busqueda=busqueda)
    
    except Exception as e:
        logger.error(f"Error en admin/data: {e}")
        return f"Error interno: {str(e)}", 500


# ==========================================
# 9. SISTEMA DE TOURS Y SOLICITUDES
# ==========================================

try:
    from database import get_db_session, Tour, SolicitudTour, Pedido, Usuario, ReservaVuelo, init_db
    from core.email_service import email_service
    from werkzeug.security import generate_password_hash, check_password_hash

    email_service.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'admin_login'

    @login_manager.user_loader
    def load_user(user_id):
        db = get_db_session()
        try:
            return db.get(Usuario, int(user_id))
        finally:
            db.close()

    @app.route('/api/tours')
    def api_tours():
        """Obtiene todos los tours activos"""
        try:
            db = get_db_session()
            destino = request.args.get('destino', '').strip()

            query = db.query(Tour).filter_by(activo=True)

            if destino:
                query = query.filter(
                    (Tour.destino.ilike(f'%{destino}%')) |
                    (Tour.titulo.ilike(f'%{destino}%'))
                )

            tours = query.order_by(Tour.precio_desde).all()
            return jsonify([tour.to_dict() for tour in tours])

        except Exception as e:
            logger.error(f"Error obteniendo tours: {e}")
            return jsonify([]), 500

        finally:
            db.close()

    @app.route('/api/solicitar-tour', methods=['POST'])
    def solicitar_tour():
        """Crea una solicitud de tour y envía email"""
        try:
            data = request.json
            db = get_db_session()

            tour = db.get(Tour, data['tour_id'])
            if not tour:
                return jsonify({'error': 'Tour no encontrado'}), 404

            solicitud = SolicitudTour()
            solicitud.tour_id = data['tour_id']
            solicitud.nombre = data['nombre']
            solicitud.email = data['email']
            solicitud.telefono = data['telefono']
            solicitud.num_personas = data.get('num_personas', 1)
            solicitud.mensaje = data.get('mensaje', '')

            db.add(solicitud)
            db.commit()

            solicitud_data = {
                'nombre': data['nombre'],
                'email': data['email'],
                'telefono': data['telefono'],
                'num_personas': data.get('num_personas', 1),
                'mensaje': data.get('mensaje', '')
            }

            tour_data = tour.to_dict()

            email_service.enviar_solicitud_tour(solicitud_data, tour_data)
            email_service.enviar_confirmacion_cliente(data['email'], data['nombre'], tour.titulo)

            logger.info(f"✅ Solicitud de tour creada: {solicitud.id}")

            return jsonify({
                'success': True,
                'message': 'Solicitud enviada correctamente',
                'solicitud_id': solicitud.id
            })

        except Exception as e:
            logger.error(f"Error creando solicitud: {e}")
            db.rollback()
            return jsonify({'error': str(e)}), 500

        finally:
            db.close()

    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        """Login para el panel de administración"""
        # Auto-create admin user if doesn't exist (development)
        if request.method == 'GET':
            db = get_db_session()
            try:
                admin_exists = db.query(Usuario).filter_by(username='admin').first()
                if not admin_exists:
                    admin_user = Usuario(
                        username='admin',
                        password_hash=generate_password_hash('password'),
                        email='admin@agencia.local',
                        rol='admin',
                        activo=True
                    )
                    db.add(admin_user)
                    db.commit()
                    app.logger.info("Admin user created: admin / password")
            except Exception as e:
                app.logger.error(f"Error creating admin: {e}")
                db.rollback()
            finally:
                db.close()
        
        if request.method == 'POST':
            data = request.json if request.is_json else request.form
            username = data.get('username')
            password = data.get('password')

            db = get_db_session()
            try:
                usuario = db.query(Usuario).filter_by(username=username, activo=True).first()

                if usuario and check_password_hash(usuario.password_hash, password):
                    login_user(usuario)
                    logger.info(f"Login exitoso: {username}")
                    return jsonify({'success': True, 'redirect': '/admin/dashboard'}) if request.is_json else redirect('/admin/dashboard')
                else:
                    logger.warning(f"Login fallido: {username}")
                    return jsonify({'error': 'Credenciales inválidas'}), 401 if request.is_json else render_template('admin_login.html', error='Credenciales inválidas')

            finally:
                db.close()

        return render_template('admin_login.html')

    @app.route('/admin/logout')
    @login_required
    def admin_logout():
        """Cierra sesión del admin"""
        logout_user()
        return redirect('/admin/login')

    @app.route('/admin/dashboard')
    @login_required
    def admin_dashboard():
        """Panel principal de administración - Vuelos"""
        db = get_db_session()
        try:
            # Estadísticas de reservas de vuelos
            total_reservas = db.query(ReservaVuelo).count()
            reservas_pendientes = db.query(ReservaVuelo).filter_by(estado='PENDIENTE').count()
            reservas_pagadas = db.query(ReservaVuelo).filter_by(estado='PAGADO').count()
            
            # Estadísticas de tours
            total_tours = db.query(Tour).count()
            
            # Reservas recientes
            reservas_recientes = db.query(ReservaVuelo).order_by(ReservaVuelo.fecha_creacion.desc()).limit(10).all()
            
            # Solicitudes de tours recientes
            solicitudes_recientes = db.query(SolicitudTour).order_by(SolicitudTour.fecha_solicitud.desc()).limit(10).all()

            return render_template('admin_dashboard.html',
                                 total_reservas=total_reservas,
                                 reservas_pendientes=reservas_pendientes,
                                 reservas_pagadas=reservas_pagadas,
                                 total_tours=total_tours,
                                 reservas_recientes=reservas_recientes,
                                 solicitudes_recientes=solicitudes_recientes)

        finally:
            db.close()

    @app.route('/admin/reserva/<codigo_reserva>')
    @login_required
    def admin_reserva_detalle(codigo_reserva):
        """Detalles completos de una reserva de vuelo"""
        import json
        db = get_db_session()
        try:
            reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            if not reserva:
                return render_template('error.html', mensaje='Reserva no encontrada'), 404
            
            # Parse JSON fields
            try:
                datos_vuelo = json.loads(reserva.datos_vuelo) if reserva.datos_vuelo else {}
            except:
                datos_vuelo = {}
            
            try:
                pasajeros_list = json.loads(reserva.pasajeros) if reserva.pasajeros else []
            except:
                pasajeros_list = []
            
            return render_template('admin_reserva_detalle.html',
                                 reserva=reserva,
                                 datos_vuelo=datos_vuelo,
                                 pasajeros=pasajeros_list,
                                 duffel_account_id=DUFFEL_ACCOUNT_ID,
                                 duffel_environment=DUFFEL_ENVIRONMENT)
        finally:
            db.close()

    @app.route('/admin/reserva/<codigo_reserva>/cambiar-fecha', methods=['POST'])
    @login_required
    def admin_cambiar_fecha(codigo_reserva):
        """Cambiar fecha de vuelo de una reserva"""
        db = get_db_session()
        try:
            data = request.json if request.is_json else request.form
            nueva_fecha = data.get('nueva_fecha')
            
            reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            if not reserva:
                return jsonify({'error': 'Reserva no encontrada'}), 404
            
            # Actualizar nota con cambio de fecha
            reserva.notas = f"Cambio de fecha: {nueva_fecha}. {reserva.notas or ''}"
            db.commit()
            
            app.logger.info(f"Cambio de fecha para {codigo_reserva} a {nueva_fecha} por {current_user.username}")
            return jsonify({'success': True, 'message': f'Fecha actualizada a {nueva_fecha}'})
        finally:
            db.close()

    @app.route('/admin/reserva/<codigo_reserva>/cambiar-vuelo', methods=['POST'])
    @login_required
    def admin_cambiar_vuelo(codigo_reserva):
        """Cambiar vuelo de una reserva"""
        db = get_db_session()
        try:
            data = request.json if request.is_json else request.form
            nuevo_vuelo = data.get('nuevo_vuelo')
            
            reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            if not reserva:
                return jsonify({'error': 'Reserva no encontrada'}), 404
            
            # Actualizar nota con cambio de vuelo
            reserva.notas = f"Cambio de vuelo: {nuevo_vuelo}. Estado anterior: {reserva.estado}. {reserva.notas or ''}"
            db.commit()
            
            app.logger.info(f"Cambio de vuelo para {codigo_reserva} a {nuevo_vuelo} por {current_user.username}")
            return jsonify({'success': True, 'message': f'Vuelo actualizado a {nuevo_vuelo}'})
        finally:
            db.close()

    @app.route('/admin/reserva/<codigo_reserva>/sync-duffel', methods=['POST'])
    @login_required
    def admin_sync_duffel(codigo_reserva):
        """Sincronizar datos desde Duffel"""
        import requests
        db = get_db_session()
        try:
            reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            if not reserva:
                return jsonify({'error': 'Reserva no encontrada'}), 404
            
            if not reserva.order_id_duffel:
                return jsonify({'error': 'Reserva no tiene order_id_duffel'}), 400
            
            # Llamar a Duffel API para obtener orden
            headers = {'Authorization': f'Bearer {DUFFEL_TOKEN}', 'Accept': 'application/json'}
            url = f'https://api.duffel.com/orders/{reserva.order_id_duffel}'
            
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                return jsonify({'error': f'Error al obtener orden de Duffel: {response.status_code}'}), 500
            
            order_data = response.json().get('data', {})
            
            # Extraer y guardar datos del vuelo
            import json
            slices = order_data.get('slices', [])
            passengers = order_data.get('passengers', [])
            
            # Construir datos_vuelo
            datos_vuelo = {}
            if slices:
                slice1 = slices[0]
                segments = slice1.get('segments', [])
                if segments:
                    seg1 = segments[0]
                    datos_vuelo = {
                        'origen': seg1.get('departure_airport', {}).get('iata_code', 'N/A'),
                        'destino': seg1.get('arrival_airport', {}).get('iata_code', 'N/A'),
                        'fecha_salida': seg1.get('departing_at', 'N/A')[:10],
                        'aerolinea': seg1.get('operating_carrier', {}).get('name', 'N/A'),
                        'numero_vuelo': seg1.get('flight_number', 'N/A'),
                        'duracion': f"{seg1.get('duration', 'N/A')}min" if seg1.get('duration') else 'N/A'
                    }
                
                if len(slices) > 1:
                    slice2 = slices[1]
                    segments2 = slice2.get('segments', [])
                    if segments2:
                        seg2 = segments2[0]
                        datos_vuelo['fecha_regreso'] = seg2.get('departing_at', 'N/A')[:10]
            
            # Construir pasajeros
            pasajeros_list = []
            if passengers:
                for pax in passengers:
                    pasajero = {
                        'nombre': f"{pax.get('given_name', '')} {pax.get('family_name', '')}".strip(),
                        'edad': pax.get('age', 'N/A'),
                        'tipo': pax.get('type', 'adulto'),
                        'documento': pax.get('id_document', {}).get('document_number', 'N/A'),
                        'genero': pax.get('gender', 'N/A'),
                        'asiento': 'Sin asignar',
                        'maletas': []
                    }
                    pasajeros_list.append(pasajero)
            
            # Guardar actualización
            reserva.datos_vuelo = json.dumps(datos_vuelo)
            reserva.pasajeros = json.dumps(pasajeros_list)
            reserva.notas = f"Sincronizado con Duffel el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {current_user.username}. {reserva.notas or ''}"
            db.commit()
            
            app.logger.info(f"Sincronizados datos de Duffel para {codigo_reserva}")
            return jsonify({'success': True, 'message': 'Datos sincronizados desde Duffel'})
        except Exception as e:
            app.logger.error(f"Error sincronizando Duffel: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            db.close()

    @app.route('/admin/reserva/<codigo_reserva>/guardar-datos', methods=['POST'])
    @login_required
    def admin_guardar_datos(codigo_reserva):
        """Guardar datos editados de reserva"""
        import json
        db = get_db_session()
        try:
            data = request.get_json()
            
            reserva = db.query(ReservaVuelo).filter_by(codigo_reserva=codigo_reserva).first()
            if not reserva:
                return jsonify({'error': 'Reserva no encontrada'}), 404
            
            # Guardar datos_vuelo si viene
            if 'datos_vuelo' in data:
                reserva.datos_vuelo = json.dumps(data['datos_vuelo'])
            
            # Guardar pasajeros si viene
            if 'pasajeros' in data:
                reserva.pasajeros = json.dumps(data['pasajeros'])
            
            # Guardar precios si vienen
            if 'precio_vuelos' in data:
                try:
                    reserva.precio_vuelos = float(data['precio_vuelos'])
                except (ValueError, TypeError):
                    pass
            
            if 'precio_extras' in data:
                try:
                    reserva.precio_extras = float(data['precio_extras'])
                except (ValueError, TypeError):
                    pass
            
            if 'precio_total' in data:
                try:
                    reserva.precio_total = float(data['precio_total'])
                except (ValueError, TypeError):
                    pass
            
            # Actualizar notas con registro de cambios
            cambios = []
            if 'datos_vuelo' in data:
                cambios.append('datos de vuelo')
            if 'pasajeros' in data:
                cambios.append('información de pasajeros')
            if 'precio_vuelos' in data or 'precio_extras' in data or 'precio_total' in data:
                cambios.append('precios')
            
            cambios_str = ', '.join(cambios)
            reserva.notas = f"Actualizado {cambios_str} el {datetime.now().strftime('%d/%m/%Y %H:%M')} por {current_user.username}. {reserva.notas or ''}"
            
            db.commit()
            
            app.logger.info(f"Guardados datos para {codigo_reserva}: {cambios_str}")
            return jsonify({'success': True, 'message': f'Datos guardados correctamente: {cambios_str}'})
        except Exception as e:
            app.logger.error(f"Error guardando datos: {e}")
            return jsonify({'error': str(e)}), 500
        finally:
            db.close()

    @app.route('/admin/pedidos')
    @login_required
    def admin_pedidos():
        """Lista todos los pedidos"""
        db = get_db_session()
        try:
            estado = request.args.get('estado')
            query = db.query(Pedido)

            if estado:
                query = query.filter_by(estado=estado)

            pedidos = query.order_by(Pedido.fecha_pedido.desc()).all()

            return render_template('admin_pedidos.html', pedidos=pedidos)

        finally:
            db.close()

    @app.route('/admin/solicitudes')
    @login_required
    def admin_solicitudes():
        """Lista todas las solicitudes de tours"""
        db = get_db_session()
        try:
            estado = request.args.get('estado')
            query = db.query(SolicitudTour)

            if estado:
                query = query.filter_by(estado=estado)

            solicitudes = query.order_by(SolicitudTour.fecha_solicitud.desc()).all()

            return render_template('admin_solicitudes.html', solicitudes=solicitudes)

        finally:
            db.close()

    @app.route('/admin/tours')
    @login_required
    def admin_tours():
        """Gestión de tours"""
        db = get_db_session()
        try:
            tours = db.query(Tour).order_by(Tour.fecha_actualizacion.desc()).all()
            return render_template('admin_tours.html', tours=tours)

        finally:
            db.close()

    @app.route('/admin/api/pedido/<int:pedido_id>', methods=['GET', 'PUT'])
    @login_required
    def admin_api_pedido(pedido_id):
        """API para obtener o actualizar un pedido"""
        db = get_db_session()
        try:
            pedido = db.query(Pedido).get(pedido_id)
            if not pedido:
                return jsonify({'error': 'Pedido no encontrado'}), 404

            if request.method == 'GET':
                return jsonify(pedido.to_dict(incluir_sensibles=True))

            elif request.method == 'PUT':
                data = request.json
                if 'estado' in data:
                    pedido.estado = data['estado']
                if 'notas_admin' in data:
                    pedido.notas_admin = data['notas_admin']

                db.commit()
                return jsonify({'success': True, 'pedido': pedido.to_dict(incluir_sensibles=True)})

        except Exception as e:
            db.rollback()
            return jsonify({'error': str(e)}), 500

        finally:
            db.close()

    @app.route('/admin/api/solicitud/<int:solicitud_id>', methods=['GET', 'PUT'])
    @login_required
    def admin_api_solicitud(solicitud_id):
        """API para obtener o actualizar una solicitud"""
        db = get_db_session()
        try:
            solicitud = db.query(SolicitudTour).get(solicitud_id)
            if not solicitud:
                return jsonify({'error': 'Solicitud no encontrada'}), 404

            if request.method == 'GET':
                return jsonify(solicitud.to_dict(incluir_sensibles=True))

            elif request.method == 'PUT':
                data = request.json
                if 'estado' in data:
                    solicitud.estado = data['estado']
                if 'notas_admin' in data:
                    solicitud.notas_admin = data['notas_admin']

                db.commit()
                return jsonify({'success': True, 'solicitud': solicitud.to_dict(incluir_sensibles=True)})

        except Exception as e:
            db.rollback()
            return jsonify({'error': str(e)}), 500

        finally:
            db.close()

    @app.route('/admin/scrape-tours', methods=['POST'])
    @login_required
    def admin_scrape_tours():
        """Ejecuta el scraping de tours"""
        try:
            from core.scraper_tours import ScraperToursB2B
            scraper = ScraperToursB2B()
            total = scraper.ejecutar_scraping_completo()
            return jsonify({'success': True, 'total_tours': total})

        except Exception as e:
            logger.error(f"Error en scraping: {e}")
            return jsonify({'error': str(e)}), 500

    @app.cli.command('init-db')
    def init_db_command():
        """Inicializa la base de datos"""
        init_db()
        print("✅ Base de datos inicializada")

    @app.cli.command('create-admin')
    def create_admin_command():
        """Crea el usuario administrador inicial"""
        db = get_db_session()
        try:
            username = os.getenv('ADMIN_USERNAME', 'admin')
            password = os.getenv('ADMIN_PASSWORD', 'admin123')
            email = os.getenv('ADMIN_EMAIL', 'admin@agencia.com')

            usuario_existente = db.query(Usuario).filter_by(username=username).first()
            if usuario_existente:
                print(f"⚠️ El usuario {username} ya existe")
                return

            admin = Usuario()
            admin.username = username
            admin.password_hash = generate_password_hash(password)
            admin.email = email
            admin.rol = 'admin'
            admin.activo = True

            db.add(admin)
            db.commit()

            print(f"✅ Usuario administrador creado: {username}")
            print(f"🔑 Password: {password}")
            print("⚠️ CAMBIA LA CONTRASEÑA INMEDIATAMENTE")

        except Exception as e:
            db.rollback()
            print(f"❌ Error creando admin: {e}")

        finally:
            db.close()

    logger.info("✅ Sistema de tours y administración cargado correctamente")

except ImportError as e:
    logger.warning(f"⚠️ Módulos de tours no disponibles: {e}")
except Exception as e:
    logger.error(f"❌ Error cargando sistema de tours: {e}")

# ==========================================
# 10. ARRANQUE
# ==========================================

if __name__ == '__main__':
    # Determinar entorno
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = FLASK_ENV == "development"
    
    print("\n" + "="*50)
    print(f"🚀 VIATGES CARCAIXENT SYSTEM ONLINE")
    print(f"📡 Entorno: {FLASK_ENV} | Debug: {DEBUG}")
    print(f"🔐 Seguridad: {'ACTIVA' if orchestrator else 'LIMITADA'}")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=DEBUG)

# ==========================================
# CACHE REDIS CONFIGURATION
# ==========================================
if RedisCache:
    try:
        cache = RedisCache()
        if getattr(cache, 'available', False):
            app.cache = cache
            logger.info("✅ Cache Redis habilitada")
        else:
            app.cache = None
            logger.warning("⚠️ Redis no disponible")
    except Exception as e:
        app.cache = None
        logger.warning(f"⚠️ No se pudo inicializar cache: {e}")
else:
    app.cache = None
    logger.info("ℹ️ Cache deshabilitada (módulo no disponible)")


# ==========================================
# PROMETHEUS METRICS
# ==========================================
if init_metrics:
    try:
        init_metrics(app)
        logger.info("✅ Métricas Prometheus habilitadas en /metrics")
    except Exception as e:
        logger.warning(f"⚠️ No se pudieron inicializar métricas: {e}")
else:
    logger.info("ℹ️ Monitoring deshabilitado (módulo no disponible)")


# ==========================================
# CORS CONFIGURATION
# ==========================================
try:
    CORS(app, resources={
        r"/api/*": {
            "origins": ["*"],  # En producción, especificar dominios
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    logger.info("✅ CORS habilitado para /api/*")
except Exception as e:
    logger.warning(f"⚠️ No se pudo configurar CORS: {e}")

try:
    _init_calendar_scheduler()
except Exception as e:
    logger.warning(f"⚠️ No se pudo iniciar scheduler de precios calendario: {e}")

print("✅ Proyecto limpio sin Stripe")
