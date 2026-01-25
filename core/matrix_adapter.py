import requests
import os
import time
import threading # <--- IMPORTANTE PARA EL SEMÁFORO
from core.database import get_db_connection

class MatrixOrchestrator:
    def __init__(self):
        self.client_id = os.getenv("AMADEUS_CLIENT_ID")
        self.client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
        self.token = None
        
        # --- SISTEMA DE CACHÉ BLINDADO ---
        self.cache_vuelos = []
        self.ultima_actualizacion = 0
        self.TTL_CACHE = 60
        
        # EL SEMÁFORO (LOCK) y CONTADOR
        self.lock_cache = threading.Lock() # Solo deja pasar a uno
        self.usuarios_activos = 0          # Contador de gente dentro
        self.lock_contador = threading.Lock() 

    def _obtener_token(self):
        try:
            url = "https://test.api.amadeus.com/v1/security/oauth2/token"
            data = {'grant_type': 'client_credentials', 'client_id': self.client_id, 'client_secret': self.client_secret}
            res = requests.post(url, data=data, timeout=5)
            if res.status_code == 200:
                self.token = res.json()['access_token']
        except Exception as e:
            print(f"❌ Error Token: {e}")

    def obtener_catalogo_unificado(self):
        # 1. MONITOR DE TRÁFICO (Entra un usuario)
        with self.lock_contador:
            self.usuarios_activos += 1
            total_ahora = self.usuarios_activos
        
        # Imprimimos estado de la cola
        estado_cache = '✅ Fresca' if (time.time() - self.ultima_actualizacion < self.TTL_CACHE) else '⏳ Caducada'
        print(f"👥 [MONITOR] Usuarios procesando: {total_ahora} | Estado Caché: {estado_cache}")

        try:
            catalogo = self._obtener_datos_locales()
            
            # 2. LÓGICA DE CACHÉ CON SEMÁFORO Y CORTOCIRCUITO
            ahora = time.time()
            if (ahora - self.ultima_actualizacion > self.TTL_CACHE) or not self.cache_vuelos:
                
                # Intentamos adquirir el semáforo (blocking=False para no atascar)
                se_ha_ganado_el_turno = self.lock_cache.acquire(blocking=False)
                
                if se_ha_ganado_el_turno:
                    try:
                        print("🛑 [SEMÁFORO] Deteniendo tráfico para actualizar Amadeus (Solo pasa 1)...")
                        nuevos_vuelos = self._fetch_amadeus_flights("MAD", "BCN")
                        
                        if nuevos_vuelos:
                            self.cache_vuelos = nuevos_vuelos
                            print(f"✅ [ÉXITO] Amadeus trajo {len(nuevos_vuelos)} vuelos nuevos.")
                        else:
                            print("⚠️ [WARN] Amadeus no devolvió resultados (o falló).")

                        # --- EL CORTOCIRCUITO ---
                        # Actualizamos la fecha SIEMPRE, haya éxito o fallo.
                        # Esto evita reintentar obsesivamente si la API está caída.
                        self.ultima_actualizacion = time.time()
                        
                    except Exception as e:
                        print(f"❌ [ERROR CRÍTICO] Fallo actualizando caché: {e}")
                        # En caso de error grave, también marcamos como actualizado para esperar 60s
                        self.ultima_actualizacion = time.time()
                    finally:
                        self.lock_cache.release() # Soltamos el semáforo siempre

            if self.cache_vuelos:
                catalogo += self.cache_vuelos
                
            return catalogo

        finally:
            # 3. MONITOR DE TRÁFICO (Sale un usuario)
            with self.lock_contador:
                self.usuarios_activos -= 1

    def _fetch_amadeus_flights(self, origin, destination):
        if not self.client_id: return []
        if not self.token: self._obtener_token()
        
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"originLocationCode": origin, "destinationLocationCode": destination, "departureDate": "2026-05-01", "adults": 1, "max": 5}
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=3)
            if res.status_code == 200:
                return self._mapear_amadeus_a_local(res.json().get('data', []))
        except: return []
        return []

    def _mapear_amadeus_a_local(self, data_api):
        mapeados = []
        for v in data_api:
            try:
                precio = v['price']['total']
                id_vuelo = v['id']
                aerolinea = v['validatingAirlineCodes'][0]
                mapeados.append({
                    'id_viaje': f"AM-{id_vuelo}", 
                    'nombre': f"Vuelo MAD ✈️ BCN ({aerolinea})",
                    'descripcion': "Vuelo directo API",
                    'precio': float(precio),
                    'url_imagen': "https://images.unsplash.com/photo-1436491865332-7a61a109c05a?w=400",
                    'fuente_datos': 'API_AUX',
                    'email_confirmacion_proveedor': 'reservas@amadeus.com'
                })
            except: continue
        return mapeados

    def _obtener_datos_locales(self):
        conn = None
        try:
            conn = get_db_connection()
            if hasattr(conn, 'cursor'):
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM viajes")
                return cursor.fetchall()
        except Exception as e:
            print(f"❌ Error DB: {e}")
            return []
        finally:
            if conn: 
                try: conn.close()
                except: pass
        return []

    def obtener_detalle_viaje(self, id_viaje):
        if str(id_viaje).startswith("AM-"):
            for v in self.cache_vuelos:
                if str(v['id_viaje']) == str(id_viaje): return v
            return None
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM viajes WHERE id_viaje = %s", (id_viaje,))
            return cursor.fetchone()
        except: return None
        finally:
            if conn: 
                try: conn.close() 
                except: pass