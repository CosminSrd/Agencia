"""
Duffel API Client
Cliente simplificado para interactuar con Duffel API
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DuffelClient:
    """Cliente para Duffel API"""
    
    BASE_URL = "https://api.duffel.com"
    
    def __init__(self, api_key: str):
        """
        Inicializa el cliente Duffel
        
        Args:
            api_key: API key de Duffel
        """
        if not api_key:
            raise ValueError("DUFFEL_API_KEY is required")
        
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Duffel-Version': 'v2',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        logger.info("Duffel API client initialized")
    
    def search_flights(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str] = None,
        passengers: Dict = None,
        cabin_class: str = 'economy'
    ) -> Dict:
        """
        Buscar vuelos disponibles
        
        Args:
            origin: Código IATA del aeropuerto de origen
            destination: Código IATA del aeropuerto de destino
            departure_date: Fecha de salida (YYYY-MM-DD)
            return_date: Fecha de regreso (opcional)
            passengers: Diccionario con adultos, niños, bebés
            cabin_class: Clase de cabina
        
        Returns:
            Dict con ofertas de vuelos
        """
        
        if passengers is None:
            passengers = {'adults': 1, 'children': 0, 'infants': 0}
        
        # Construir lista de pasajeros para Duffel
        passenger_list = []
        for _ in range(passengers.get('adults', 1)):
            passenger_list.append({'type': 'adult'})
        for _ in range(passengers.get('children', 0)):
            passenger_list.append({'type': 'child'})
        for _ in range(passengers.get('infants', 0)):
            passenger_list.append({'type': 'infant_without_seat'})
        
        # Construir slices
        slices = [
            {
                'origin': origin,
                'destination': destination,
                'departure_date': departure_date
            }
        ]
        
        if return_date:
            slices.append({
                'origin': destination,
                'destination': origin,
                'departure_date': return_date
            })
        
        payload = {
            'data': {
                'slices': slices,
                'passengers': passenger_list,
                'cabin_class': cabin_class
            }
        }
        
        try:
            logger.info(f"Creating offer request: {origin} -> {destination}")
            response = self.session.post(
                f'{self.BASE_URL}/air/offer_requests',
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            offer_request = response.json()
            offer_request_id = offer_request['data']['id']
            
            # Obtener ofertas
            logger.info(f"Fetching offers for request: {offer_request_id}")
            response = self.session.get(
                f'{self.BASE_URL}/air/offers',
                params={'offer_request_id': offer_request_id},
                timeout=30
            )
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Duffel API error: {e}")
            raise
    
    def autocomplete_airports(self, query: str) -> List[Dict]:
        """
        Autocompletar aeropuertos
        
        Args:
            query: Texto de búsqueda (código IATA o nombre)
        
        Returns:
            Lista de aeropuertos encontrados
        """
        
        try:
            response = self.session.get(
                f'{self.BASE_URL}/air/airports',
                params={'name': query},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            airports = data.get('data', [])
            
            # Formatear resultados
            results = []
            for airport in airports[:10]:  # Limitar a 10 resultados
                results.append({
                    'iata_code': airport.get('iata_code'),
                    'name': airport.get('name'),
                    'city_name': airport.get('city_name'),
                    'country': airport.get('country', {}).get('name'),
                    'label': f"{airport.get('city_name')} ({airport.get('iata_code')})",
                    'value': airport.get('iata_code')
                })
            
            return results
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Autocomplete error: {e}")
            raise
    
    def get_available_seats(self, offer_id: str) -> Dict:
        """
        Obtener asientos disponibles para una oferta
        
        Args:
            offer_id: ID de la oferta
        
        Returns:
            Dict con información de asientos
        """
        
        try:
            response = self.session.get(
                f'{self.BASE_URL}/air/seat_maps',
                params={'offer_id': offer_id},
                timeout=15
            )
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching seats: {e}")
            raise
    
    def get_offer(self, offer_id: str) -> Dict:
        """
        Obtener detalles de una oferta específica
        
        Args:
            offer_id: ID de la oferta
        
        Returns:
            Dict con detalles de la oferta
        """
        
        try:
            response = self.session.get(
                f'{self.BASE_URL}/air/offers/{offer_id}',
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching offer: {e}")
            raise
    
    def get_available_services(self, offer_id: str) -> Dict:
        """
        Obtener servicios adicionales disponibles
        
        Args:
            offer_id: ID de la oferta
        
        Returns:
            Dict con servicios disponibles (equipaje, comidas, etc.)
        """
        
        try:
            response = self.session.get(
                f'{self.BASE_URL}/air/offers/{offer_id}/available_services',
                timeout=10
            )
            response.raise_for_status()
            
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching services: {e}")
            raise
