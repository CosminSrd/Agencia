import logging
import os
from datetime import datetime, timedelta

import requests


logger = logging.getLogger(__name__)


class AmadeusAdapter:
    """Adaptador mínimo de búsqueda de vuelos en Amadeus Self-Service."""

    # Autenticación
    TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
    
    # Búsqueda (TIER 1)
    SEARCH_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"
    PRICING_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers/pricing"
    
    # Booking (TIER 1-2)
    ORDER_URL = "https://test.api.amadeus.com/v1/booking/flight-orders"
    TICKET_URL = "https://test.api.amadeus.com/v1/ticketing/issue-ticket"
    
    # Enhancers (TIER 2-3)
    SEATMAP_URL = "https://test.api.amadeus.com/v1/shopping/seatmaps"
    UPSELL_URL = "https://test.api.amadeus.com/v1/shopping/flight-offers/upselling"
    AVAILABILITY_URL = "https://test.api.amadeus.com/v1/shopping/availability/flight-availabilities"
    
    # Reference Data (TIER 3-4)
    LOCATIONS_URL = "https://test.api.amadeus.com/v1/reference-data/locations"
    NEAREST_AIRPORTS_URL = "https://test.api.amadeus.com/v1/reference-data/locations/airports"
    ROUTES_URL = "https://test.api.amadeus.com/v1/airport/direct-destinations"
    AIRLINES_URL = "https://test.api.amadeus.com/v1/reference-data/airlines"
    
    # Post-Booking (TIER 4)
    FLIGHT_STATUS_URL = "https://test.api.amadeus.com/v2/flights"
    CHECKIN_LINKS_URL = "https://test.api.amadeus.com/v1/reference-data/urls/checkin-links"

    def __init__(self):
        self.api_key = os.getenv("AMADEUS_API_KEY", "").strip()
        self.api_secret = os.getenv("AMADEUS_API_SECRET", "").strip()
        self.currency = os.getenv("AMADEUS_DEFAULT_CURRENCY", "EUR").strip().upper() or "EUR"
        self.max_results = int(os.getenv("AMADEUS_MAX_RESULTS", "40"))

        self._access_token = None
        self._token_expires_at = None

        if self.is_configured():
            logger.info("✅ AmadeusAdapter configurado para fallback secundario")
        else:
            logger.info("ℹ️ AmadeusAdapter no configurado (faltan credenciales), fallback desactivado")

    def is_configured(self):
        return bool(self.api_key and self.api_secret)

    def _get_access_token(self):
        if self._access_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            return self._access_token

        payload = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret,
        }
        response = requests.post(self.TOKEN_URL, data=payload, timeout=15)
        response.raise_for_status()

        body = response.json()
        self._access_token = body.get("access_token")
        expires_in = int(body.get("expires_in", 1200))
        self._token_expires_at = datetime.utcnow() + timedelta(seconds=max(60, expires_in - 30))
        return self._access_token

    def _parse_iso_duration(self, iso_duration):
        if not iso_duration:
            return ""
        try:
            value = iso_duration.replace("P", "").replace("T", "")
            days = hours = minutes = 0

            if "D" in value:
                parts = value.split("D")
                days = int(parts[0])
                value = parts[1] if len(parts) > 1 else ""
            if "H" in value:
                parts = value.split("H")
                hours = int(parts[0])
                value = parts[1] if len(parts) > 1 else ""
            if "M" in value:
                minutes = int(value.replace("M", ""))

            chunks = []
            if days:
                chunks.append(f"{days}d")
            if hours:
                chunks.append(f"{hours}h")
            if minutes:
                chunks.append(f"{minutes}m")
            return " ".join(chunks) if chunks else ""
        except Exception:
            return iso_duration

    def _normalize_date(self, fecha):
        if not fecha:
            return ""
        value = str(fecha).strip()
        try:
            if "/" in value:
                return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except Exception:
            return value

    def _parse_datetime(self, value):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _has_checked_bag(self, offer):
        traveler_pricings = offer.get("travelerPricings") or []
        for pricing in traveler_pricings:
            for detail in (pricing.get("fareDetailsBySegment") or []):
                bag = detail.get("includedCheckedBags") or {}
                quantity = bag.get("quantity")
                weight = bag.get("weight")
                if (isinstance(quantity, int) and quantity > 0) or weight:
                    return True
        return False

    def buscar_vuelos(self, origen, destino, fecha, adultos=1, ninos=0, bebes=0, clase="economy"):
        if not self.is_configured():
            return []

        clase_map = {
            "economy": "ECONOMY",
            "premium": "PREMIUM_ECONOMY",
            "business": "BUSINESS",
            "first": "FIRST",
        }

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            fecha_normalizada = self._normalize_date(fecha)

            adultos_int = max(1, int(adultos or 1))
            ninos_int = max(0, int(ninos or 0))
            bebes_int = max(0, int(bebes or 0))

            params = {
                "originLocationCode": (origen or "").upper(),
                "destinationLocationCode": (destino or "").upper(),
                "departureDate": fecha_normalizada,
                "adults": adultos_int,
                "travelClass": clase_map.get((clase or "economy").lower(), "ECONOMY"),
                "currencyCode": self.currency,
                "max": self.max_results,
            }

            if ninos_int > 0:
                params["children"] = ninos_int
            if bebes_int > 0:
                params["infants"] = bebes_int

            response = requests.get(self.SEARCH_URL, headers=headers, params=params, timeout=20)
            if response.status_code >= 400:
                logger.error(f"❌ Amadeus error {response.status_code}: {response.text}")
            response.raise_for_status()

            offers = (response.json() or {}).get("data") or []
            resultados = []

            for offer in offers:
                itineraries = offer.get("itineraries") or []
                if not itineraries:
                    continue

                itinerary = itineraries[0]
                raw_segments = itinerary.get("segments") or []
                if not raw_segments:
                    continue

                segmentos = []
                for index, segment in enumerate(raw_segments):
                    dep_at = self._parse_datetime((segment.get("departure") or {}).get("at"))
                    arr_at = self._parse_datetime((segment.get("arrival") or {}).get("at"))

                    escala_duracion = None
                    if index < len(raw_segments) - 1 and arr_at:
                        next_dep = self._parse_datetime((raw_segments[index + 1].get("departure") or {}).get("at"))
                        if next_dep and next_dep > arr_at:
                            delta = next_dep - arr_at
                            total_minutes = int(delta.total_seconds() // 60)
                            escala_duracion = f"{total_minutes // 60}h {total_minutes % 60}m"

                    carrier_code = segment.get("carrierCode", "XX")
                    flight_number = segment.get("number", "")
                    full_flight = f"{carrier_code}{flight_number}" if flight_number else carrier_code

                    segmentos.append({
                        "salida": (segment.get("departure") or {}).get("iataCode", ""),
                        "llegada": (segment.get("arrival") or {}).get("iataCode", ""),
                        "ciudad_salida": (segment.get("departure") or {}).get("iataCode", ""),
                        "ciudad_llegada": (segment.get("arrival") or {}).get("iataCode", ""),
                        "hora_salida": dep_at.strftime("%H:%M") if dep_at else "N/A",
                        "hora_llegada": arr_at.strftime("%H:%M") if arr_at else "N/A",
                        "fecha_salida": dep_at.strftime("%d %b") if dep_at else "N/A",
                        "fecha_llegada": arr_at.strftime("%d %b") if arr_at else "N/A",
                        "aerolinea": carrier_code,
                        "vuelo": full_flight,
                        "duracion": self._parse_iso_duration(segment.get("duration")),
                        "avion": (segment.get("aircraft") or {}).get("code", "Avión"),
                        "img_logo": f"https://pics.avs.io/64/64/{carrier_code}.png",
                        "escala_duracion": escala_duracion,
                    })

                first_segment = segmentos[0]
                last_segment = segmentos[-1]
                validating_carrier = ((offer.get("validatingAirlineCodes") or [""])[0] or "XX").upper()
                price_obj = offer.get("price") or {}
                total_amount = float(price_obj.get("grandTotal") or 0)
                currency = price_obj.get("currency") or self.currency
                con_maleta = self._has_checked_bag(offer)

                resultados.append({
                    "id": f"amadeus_{offer.get('id')}",
                    "source": "Amadeus",
                    "amadeus_full_offer": offer,
                    "aerolinea": validating_carrier,
                    "img_logo": f"https://pics.avs.io/200/200/{validating_carrier}.png",
                    "origen": first_segment.get("salida") or (origen or "").upper(),
                    "destino": last_segment.get("llegada") or (destino or "").upper(),
                    "trayectos": [{
                        "origen": first_segment.get("salida") or (origen or "").upper(),
                        "destino": last_segment.get("llegada") or (destino or "").upper(),
                        "duracion": self._parse_iso_duration(itinerary.get("duration")),
                        "segmentos": segmentos,
                    }],
                    "hora_salida": first_segment.get("hora_salida", "N/A"),
                    "hora_llegada": last_segment.get("hora_llegada", "N/A"),
                    "duracion": self._parse_iso_duration(itinerary.get("duration")) or first_segment.get("duracion", "N/A"),
                    "precio_base": total_amount,
                    "precio": total_amount,
                    "currency": currency,
                    "escala": max(0, len(segmentos) - 1),
                    "segmentos": segmentos,
                    "passengers": [],
                    "condiciones": {},
                    "con_maleta": con_maleta,
                    "available_services": [],
                    "familia_tarifaria": "Basic",
                    "reservable": True,
                    "motivo_no_reservable": "",
                })

            resultados.sort(key=lambda x: x.get("precio", 0))
            logger.info(f"✅ Amadeus retornó {len(resultados)} ofertas para fallback {origen}->{destino}")
            return resultados

        except Exception as exc:
            logger.error(f"❌ Error buscando en Amadeus: {exc}")
            return []

    def crear_orden_amadeus(self, flight_offer, pasajeros, contacto_email, 
                           contacto_telefono=None, remarks=None):
        """
        Crea una orden (PNR) en Amadeus con la oferta completa validada.
        
        flight_offer: dict con la estructura COMPLETA de la oferta de Amadeus
                      (resultado de validar_pricing_amadeus o búsqueda original)
        pasajeros: List[dict] con nombre, apellido, tipo (ADULT/CHILD/INFANT),
                   fecha_nacimiento, nacionalidad (ISO 2-letter code)
        contacto_email: email del contacto principal
        contacto_telefono: teléfono de contacto (opcional)
        remarks: Observaciones adicionales (opcional)
        
        Returns: dict con 'success', 'order_id', 'pnr', 'remarks', y 'error'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Construir payload de orden con oferta completa
            order_payload = {
                "data": {
                    "type": "flight-order",
                    "flightOffers": [flight_offer],  # Oferta COMPLETA, no solo ID
                    "travelers": [],
                    "remarks": {
                        "general": [{"subType": "GENERAL_MISCELLANEOUS",
                                   "category": "Z",
                                   "text": remarks or "Booked via agencia.com"}]
                    },
                    "contacts": [{
                        "addresseeName": {"firstName": "CONTACT", "lastName": "AGENT"},
                        "address": {
                            "cityName": "Madrid",
                            "countryCode": "ES",
                            "postalCode": "28001",
                            "lines": ["Via agencia.com"]
                        },
                        "emailAddress": contacto_email,
                        "phones": [{
                            "deviceType": "MOBILE",
                            "countryCallingCode": "34",
                            "number": contacto_telefono or "600000000"
                        }],
                        "purpose": "STANDARD"
                    }]
                }
            }

            # Agregar viajeros con todos los campos requeridos
            for idx, pasajero in enumerate(pasajeros):
                tipo = (pasajero.get('tipo') or 'ADULT').upper()
                if tipo not in ['ADULT', 'CHILD', 'INFANT']:
                    tipo = 'ADULT'

                nombres = (pasajero.get('nombres') or '').strip().split()
                primer_nombre = nombres[0] if nombres else 'PASSENGER'
                resto_nombres = ' '.join(nombres[1:]) if len(nombres) > 1 else ''
                apellidos = pasajero.get('apellidos') or 'SURNAME'

                # Información de documento (Pasaporte por defecto, pero puede ser ID)
                doc_type = pasajero.get('tipo_documento', 'PASSPORT')
                nacionalidad = pasajero.get('nacionalidad', 'ES').upper()

                traveler = {
                    "id": str(idx + 1),
                    "dateOfBirth": pasajero.get('fecha_nacimiento') or "1990-01-01",
                    "name": {
                        "firstName": primer_nombre,
                        "lastName": apellidos
                    },
                    "gender": "MALE" if (pasajero.get('genero') or 'M').upper() == 'M' else "FEMALE",
                    "contact": {
                        "emailAddress": contacto_email,
                        "phones": [{
                            "deviceType": "MOBILE",
                            "countryCallingCode": pasajero.get('country_code', '34'),
                            "number": pasajero.get('telefono') or "600000000"
                        }]
                    },
                    "documents": [{
                        "documentType": doc_type,
                        "birthPlace": pasajero.get('lugar_nacimiento', 'Madrid'),
                        "issuanceLocation": pasajero.get('lugar_emision', 'Madrid'),
                        "issuanceDate": pasajero.get('fecha_emision', '2020-01-01'),
                        "number": pasajero.get('numero_documento') or "00000000A",
                        "expiryDate": pasajero.get('fecha_vencimiento', '2030-01-01'),
                        "issuanceCountry": nacionalidad,
                        "validityCountry": nacionalidad,
                        "nationality": nacionalidad,
                        "holder": True
                    }],
                    "associatedAdultId": None if tipo == 'ADULT' else (
                        pasajero.get('adult_id') or "1"
                    )
                }

                # Agregar lealtad si se proporciona
                if pasajero.get('numero_aerolinea') and pasajero.get('codigo_aerolinea'):
                    traveler["loyaltyPrograms"] = [{
                        "airlineCode": pasajero.get('codigo_aerolinea'),
                        "number": pasajero.get('numero_aerolinea')
                    }]

                # Dirección de emergencia
                if pasajero.get('direccion_emergencia'):
                    traveler["emergencyContact"] = {
                        "name": {
                            "firstName": pasajero.get('nombre_emergencia', 'EMERGENCY'),
                            "lastName": pasajero.get('apellido_emergencia', 'CONTACT')
                        },
                        "address": {
                            "cityName": pasajero.get('ciudad_emergencia', 'Madrid'),
                            "countryCode": nacionalidad,
                            "lines": [pasajero.get('direccion_emergencia')]
                        },
                        "phones": [{
                            "deviceType": "MOBILE",
                            "countryCallingCode": pasajero.get('country_code', '34'),
                            "number": pasajero.get('telefono_emergencia', '600000000')
                        }]
                    }

                order_payload["data"]["travelers"].append(traveler)

            # Enviar crear orden
            logger.info(f"📝 Creando orden Amadeus para {len(pasajeros)} viajeros con oferta validada...")
            response = requests.post(
                self.ORDER_URL,
                json=order_payload,
                headers=headers,
                timeout=30
            )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"❌ Amadeus orden error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Amadeus error: {response.status_code} - {error_text[:200]}"
                }

            order_data = response.json()
            order_dict = order_data.get('data', {})
            order_id = order_dict.get('id')
            pnr = order_dict.get('queuingOfficeId')
            order_remarks = order_dict.get('remarks', [])

            logger.info(f"✅ Orden Amadeus creada: {order_id} (PNR: {pnr})")
            return {
                'success': True,
                'order_id': order_id,
                'pnr': pnr,
                'remarks': order_remarks,
                'order_data': order_data
            }

        except Exception as exc:
            logger.error(f"❌ Error creando orden Amadeus: {exc}")
            return {'success': False, 'error': str(exc)}

    def emitir_tickets_amadeus(self, order_id, pnr, order_data=None):
        """
        Emite eTickets para una orden Amadeus ya creada.
        
        order_id: ID de la orden retornado por crear_orden_amadeus
        pnr: PNR (queuingOfficeId) retornado por crear_orden_amadeus
        order_data: (opcional) datos completos de la orden para referencia
        
        Returns: dict con 'success', 'tickets' (list de dict con ticket_number), y 'error'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Payload para emisión - intentar múltiples variantes
            # Variante 1: Solo queuingOfficeId (PNR)
            ticket_payload = {
                "data": {
                    "queuingOfficeId": pnr
                }
            }

            logger.info(f"🎫 Emitiendo eTickets para orden {order_id} (PNR: {pnr})...")
            response = requests.post(
                self.TICKET_URL,
                json=ticket_payload,
                headers=headers,
                timeout=30
            )

            # Si falla con 404, intentar con order_id en URL
            if response.status_code == 404 and order_data:
                logger.warning(f"⚠️ 404 con queuingOfficeId, intentando con variante alternativa...")
                # Variante 2: incluir información de viajeros y segmentos
                if order_data.get('data', {}).get('associatedRecords'):
                    ticket_payload["data"]["associatedRecords"] = order_data["data"].get("associatedRecords", [])
                
                response = requests.post(
                    self.TICKET_URL,
                    json=ticket_payload,
                    headers=headers,
                    timeout=30
                )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"❌ Amadeus ticketing error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Amadeus ticketing error: {response.status_code}"
                }

            ticket_data = response.json()
            tickets = ticket_data.get('data', [])

            logger.info(f"✅ eTickets emitidos: {len(tickets)} tickets")
            return {
                'success': True,
                'tickets': tickets,
                'ticket_data': ticket_data
            }

        except Exception as exc:
            logger.error(f"❌ Error emitiendo tickets Amadeus: {exc}")
            return {'success': False, 'error': str(exc)}

    # ============================================================================
    # TIER 1-2: PRICING & ORDER MANAGEMENT
    # ============================================================================

    def validar_pricing_amadeus(self, flight_offers):
        """
        Valida el precio de ofertas de vuelo antes de crear la orden.
        Detecta cambios de precio respecto a la búsqueda original.
        
        flight_offers: List[dict] con estructura completa de oferta Amadeus
        
        Returns: dict con 'success', 'pricing' (list con precios validados), 'changed' (bool),
                 'original_price', 'new_price', 'difference'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # Payload de validación
            pricing_payload = {
                "data": {
                    "flightOffers": flight_offers
                }
            }

            logger.info(f"💰 Validando precio para {len(flight_offers)} oferta(s)...")
            response = requests.post(
                self.PRICING_URL,
                json=pricing_payload,
                headers=headers,
                timeout=30
            )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"❌ Amadeus pricing error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Pricing error: {response.status_code}"
                }

            pricing_data = response.json()
            flightOffers = pricing_data.get('data', {}).get('flightOffers', [])
            
            if not flightOffers:
                return {'success': False, 'error': 'No pricing data returned'}

            # Comparar precios
            original_total = sum(float(offer.get('price', {}).get('total', 0)) 
                                for offer in flight_offers)
            new_total = sum(float(offer.get('price', {}).get('total', 0)) 
                           for offer in flightOffers)
            
            price_changed = abs(original_total - new_total) > 0.01
            
            logger.info(f"✅ Precio validado: ${original_total} → ${new_total} "
                       f"(Cambio: {price_changed})")
            
            return {
                'success': True,
                'pricing': flightOffers,
                'changed': price_changed,
                'original_price': original_total,
                'new_price': new_total,
                'difference': new_total - original_total,
                'pricing_data': pricing_data
            }

        except Exception as exc:
            logger.error(f"❌ Error validando pricing: {exc}")
            return {'success': False, 'error': str(exc)}

    def recuperar_orden_amadeus(self, order_id):
        """
        Recupera los detalles de una orden existente.
        
        order_id: ID de la orden
        
        Returns: dict con 'success', 'order', 'order_data'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            logger.info(f"🔍 Recuperando orden {order_id}...")
            response = requests.get(
                f"{self.ORDER_URL}/{order_id}",
                headers=headers,
                timeout=30
            )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"❌ Amadeus order retrieval error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Order not found: {response.status_code}"
                }

            order_data = response.json()
            order = order_data.get('data', {})

            logger.info(f"✅ Orden recuperada: {order.get('id')} (Estado: "
                       f"{order.get('type')})")
            
            return {
                'success': True,
                'order': order,
                'order_data': order_data
            }

        except Exception as exc:
            logger.error(f"❌ Error recuperando orden: {exc}")
            return {'success': False, 'error': str(exc)}

    def cancelar_orden_amadeus(self, order_id):
        """
        Cancela una orden Amadeus.
        
        order_id: ID de la orden
        
        Returns: dict con 'success', 'message'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            logger.info(f"🛑 Cancelando orden {order_id}...")
            response = requests.delete(
                f"{self.ORDER_URL}/{order_id}",
                headers=headers,
                timeout=30
            )

            if response.status_code not in [200, 204]:
                error_text = response.text
                logger.error(f"❌ Amadeus cancellation error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Cancellation failed: {response.status_code}"
                }

            logger.info(f"✅ Orden {order_id} cancelada")
            
            return {
                'success': True,
                'message': f'Order {order_id} cancelled successfully'
            }

        except Exception as exc:
            logger.error(f"❌ Error cancelando orden: {exc}")
            return {'success': False, 'error': str(exc)}

    # ============================================================================
    # TIER 2-3: BOOKING ENHANCEMENTS
    # ============================================================================

    def obtener_seatmap(self, flight_offer_id, tipo_desembarque):
        """
        Obtiene el mapa de asientos disponibles para un vuelo.
        
        flight_offer_id: ID de la oferta
        tipo_desembarque: 'DEPARTURE' o 'ARRIVAL'
        
        Returns: dict con 'success', 'seatmap'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "flightOfferId": flight_offer_id.replace('amadeus_', '')
            }

            logger.info(f"🪑 Obteniendo mapa de asientos para {flight_offer_id}...")
            response = requests.get(
                self.SEATMAP_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"❌ Amadeus seatmap error {response.status_code}: {error_text}")
                return {
                    'success': False,
                    'error': f"Seatmap error: {response.status_code}"
                }

            seatmap_data = response.json()
            seatmaps = seatmap_data.get('data', [])

            logger.info(f"✅ Mapa de asientos obtenido: {len(seatmaps)} segmento(s)")
            
            return {
                'success': True,
                'seatmap': seatmaps,
                'seatmap_data': seatmap_data
            }

        except Exception as exc:
            logger.error(f"❌ Error obteniendo seatmap: {exc}")
            return {'success': False, 'error': str(exc)}

    def obtener_ofertas_upsell(self, flight_offer_id):
        """
        Obtiene ofertas de upgrade (business, premium economy, extra legroom, etc).
        
        flight_offer_id: ID de la oferta
        
        Returns: dict con 'success', 'upsells' (list de ofertas upgrade)
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "flightOfferId": flight_offer_id.replace('amadeus_', '')
            }

            logger.info(f"⬆️ Obteniendo ofertas de upsell para {flight_offer_id}...")
            response = requests.get(
                self.UPSELL_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Amadeus upsell error {response.status_code}")
                return {
                    'success': True,  # No es error crítico
                    'upsells': []
                }

            upsell_data = response.json()
            upsells = upsell_data.get('data', [])

            logger.info(f"✅ Ofertas upsell obtenidas: {len(upsells)} opciones")
            
            return {
                'success': True,
                'upsells': upsells,
                'upsell_data': upsell_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error obteniendo upsells (no crítico): {exc}")
            return {'success': True, 'upsells': []}

    def buscar_disponibilidad(self, origen, destino, fecha_salida, 
                             fecha_regreso=None, cabina='ECONOMY'):
        """
        Busca disponibilidad de vuelos por clase de cabina.
        
        cabina: 'ECONOMY', 'PREMIUM_ECONOMY', 'BUSINESS', 'FIRST'
        
        Returns: dict con 'success', 'availabilities'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            availability_payload = {
                "originLocationCode": origen,
                "destinationLocationCode": destino,
                "departureDate": self._normalize_date(fecha_salida),
                "adultsCount": 1,
                "cabinRestriction": cabina
            }

            if fecha_regreso:
                availability_payload["returnDate"] = self._normalize_date(fecha_regreso)

            logger.info(f"📅 Buscando disponibilidad: {origen}->{destino} "
                       f"en cabina {cabina}...")
            response = requests.post(
                self.AVAILABILITY_URL,
                json=availability_payload,
                headers=headers,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Availability search returned {response.status_code}")
                return {
                    'success': True,  # No es error crítico
                    'availabilities': []
                }

            availability_data = response.json()
            availabilities = availability_data.get('data', [])

            logger.info(f"✅ Disponibilidad: {len(availabilities)} resultado(s)")
            
            return {
                'success': True,
                'availabilities': availabilities,
                'availability_data': availability_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error buscando disponibilidad: {exc}")
            return {'success': True, 'availabilities': []}

    # ============================================================================
    # TIER 3-4: REFERENCE DATA
    # ============================================================================

    def buscar_aeropuertos(self, keyword, subtype='AIRPORT,CITY'):
        """
        Busca aeropuertos/ciudades por nombre (autocompletado).
        
        keyword: Texto a buscar (ej: 'Madrid', 'MAD')
        subtype: 'AIRPORT', 'CITY', o ambos separados por coma
        
        Returns: dict con 'success', 'locations' (list de aeropuertos/ciudades)
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "keyword": keyword,
                "subType": subtype,
                "page": {"limit": 50}
            }

            logger.info(f"🌍 Buscando ubicaciones para '{keyword}'...")
            response = requests.get(
                self.LOCATIONS_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Location search error {response.status_code}")
                return {'success': True, 'locations': []}

            locations_data = response.json()
            locations = locations_data.get('data', [])

            logger.info(f"✅ Ubicaciones encontradas: {len(locations)}")
            
            return {
                'success': True,
                'locations': locations,
                'locations_data': locations_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error buscando ubicaciones: {exc}")
            return {'success': True, 'locations': []}

    def aeropuertos_cercanos(self, latitud, longitud, radio=500):
        """
        Encuentra aeropuertos cercanos a una coordenada geográfica.
        
        latitud, longitud: Coordenadas
        radio: Radio en km
        
        Returns: dict con 'success', 'airports'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "latitude": latitud,
                "longitude": longitud,
                "radius": radio,
                "page": {"limit": 50}
            }

            logger.info(f"📍 Buscando aeropuertos cercanos a ({latitud}, {longitud})...")
            response = requests.get(
                self.NEAREST_AIRPORTS_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Nearest airports error {response.status_code}")
                return {'success': True, 'airports': []}

            airports_data = response.json()
            airports = airports_data.get('data', [])

            logger.info(f"✅ Aeropuertos cercanos: {len(airports)}")
            
            return {
                'success': True,
                'airports': airports,
                'airports_data': airports_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error buscando aeropuertos cercanos: {exc}")
            return {'success': True, 'airports': []}

    def rutas_directas(self, codigo_aeropuerto):
        """
        Obtiene destinos directos disponibles desde un aeropuerto.
        
        codigo_aeropuerto: Código IATA (ej: 'MAD')
        
        Returns: dict con 'success', 'destinations'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            logger.info(f"✈️ Buscando rutas directas desde {codigo_aeropuerto}...")
            response = requests.get(
                f"{self.ROUTES_URL}/{codigo_aeropuerto}",
                headers=headers,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Routes error {response.status_code}")
                return {'success': True, 'destinations': []}

            routes_data = response.json()
            destinations = routes_data.get('data', [])

            logger.info(f"✅ Rutas directas encontradas: {len(destinations)}")
            
            return {
                'success': True,
                'destinations': destinations,
                'routes_data': routes_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error buscando rutas: {exc}")
            return {'success': True, 'destinations': []}

    def obtener_aerolineas(self, codigos_aerolinea):
        """
        Obtiene información de aerolíneas (nombres, logos).
        
        codigos_aerolinea: List[str] o str con códigos IATA (ej: ['IB', 'BA'])
        
        Returns: dict con 'success', 'airlines'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            # Si es string, convertir a list
            if isinstance(codigos_aerolinea, str):
                codigos_aerolinea = [codigos_aerolinea]

            params = {
                "airlineCodes": ",".join(codigos_aerolinea)
            }

            logger.info(f"🚁 Obteniendo info de aerolíneas: {', '.join(codigos_aerolinea)}")
            response = requests.get(
                self.AIRLINES_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Airlines lookup error {response.status_code}")
                return {'success': True, 'airlines': []}

            airlines_data = response.json()
            airlines = airlines_data.get('data', [])

            logger.info(f"✅ Aerolíneas obtenidas: {len(airlines)}")
            
            return {
                'success': True,
                'airlines': airlines,
                'airlines_data': airlines_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error obteniendo aerolíneas: {exc}")
            return {'success': True, 'airlines': []}

    # ============================================================================
    # TIER 4: POST-BOOKING
    # ============================================================================

    def obtener_estado_vuelo(self, codigo_aerolinea, numero_vuelo, fecha_salida):
        """
        Obtiene el estado en tiempo real de un vuelo.
        
        codigo_aerolinea: Código IATA (ej: 'IB')
        numero_vuelo: Número de vuelo (ej: '6840')
        fecha_salida: Fecha en formato YYYY-MM-DD
        
        Returns: dict con 'success', 'flights' (estado actual del vuelo)
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "carrierCode": codigo_aerolinea,
                "flightNumber": numero_vuelo,
                "scheduledDepartureDate": self._normalize_date(fecha_salida)
            }

            logger.info(f"📊 Obteniendo estado de vuelo {codigo_aerolinea}{numero_vuelo} "
                       f"el {fecha_salida}...")
            response = requests.get(
                self.FLIGHT_STATUS_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Flight status error {response.status_code}")
                return {'success': True, 'flights': []}

            status_data = response.json()
            flights = status_data.get('data', [])

            if flights:
                flight = flights[0]
                logger.info(f"✅ Estado del vuelo: {flight.get('operating', {}).get('status', 'N/A')}")
            
            return {
                'success': True,
                'flights': flights,
                'status_data': status_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error obteniendo estado: {exc}")
            return {'success': True, 'flights': []}

    def obtener_links_checkin(self, codigo_aerolinea):
        """
        Obtiene los enlaces de check-in en línea de una aerolínea.
        
        codigo_aerolinea: Código IATA (ej: 'IB')
        
        Returns: dict con 'success', 'checkin_links'
        """
        if not self.is_configured():
            return {'success': False, 'error': 'Amadeus no configurado'}

        try:
            token = self._get_access_token()
            headers = {"Authorization": f"Bearer {token}"}

            params = {
                "airlineCode": codigo_aerolinea
            }

            logger.info(f"🔗 Obteniendo enlaces de check-in para {codigo_aerolinea}...")
            response = requests.get(
                self.CHECKIN_LINKS_URL,
                headers=headers,
                params=params,
                timeout=30
            )

            if response.status_code >= 400:
                logger.warning(f"⚠️ Check-in links error {response.status_code}")
                return {'success': True, 'checkin_links': []}

            checkin_data = response.json()
            checkin_links = checkin_data.get('data', [])

            logger.info(f"✅ Enlaces de check-in obtenidos: {len(checkin_links)}")
            
            return {
                'success': True,
                'checkin_links': checkin_links,
                'checkin_data': checkin_data
            }

        except Exception as exc:
            logger.warning(f"⚠️ Error obteniendo enlaces de check-in: {exc}")
            return {'success': True, 'checkin_links': []}