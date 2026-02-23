"""
Tests unitarios para core/scraper_motor.py
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
import sys
import os

# Añadir el directorio raíz al path para imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.scraper_motor import MotorBusqueda


class TestMotorBusqueda(unittest.TestCase):
    """Suite de tests para MotorBusqueda"""
    
    def setUp(self):
        """Configuración antes de cada test"""
        # Mock de variables de entorno
        with patch.dict('os.environ', {
            'DUFFEL_API_TOKEN': 'test_token_123',
            'AGENCY_MARKUP_PERCENT': '10.0',
            'CACHE_DURATION_MINUTES': '5'
        }):
            self.motor = MotorBusqueda()
    
    def test_init(self):
        """Test de inicialización correcta"""
        self.assertIsNotNone(self.motor.duffel_token)
        self.assertEqual(self.motor.markup_percent, Decimal('10.0'))
        self.assertEqual(self.motor.TIEMPO_CACHE_MINUTOS, 5)
    
    def test_apply_markup(self):
        """Test de aplicación de markup"""
        amount = Decimal('100.00')
        resultado = self.motor.apply_markup(amount)
        self.assertEqual(resultado, Decimal('110.00'))
    
    def test_apply_markup_sin_comision(self):
        """Test de markup con 0% de comisión"""
        self.motor.markup_percent = Decimal('0.0')
        amount = Decimal('100.00')
        resultado = self.motor.apply_markup(amount)
        self.assertEqual(resultado, Decimal('100.00'))
    
    def test_get_headers(self):
        """Test de headers correctos para API"""
        headers = self.motor._get_headers()
        self.assertIn('Authorization', headers)
        self.assertIn('Bearer test_token_123', headers['Authorization'])
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(headers['Duffel-Version'], 'v2')
    
    @patch('core.scraper_motor.requests.get')
    def test_autocompletar_aeropuerto_success(self, mock_get):
        """Test de autocompletado exitoso"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [
                {
                    'name': 'Madrid Barajas',
                    'iata_code': 'MAD',
                    'type': 'airport',
                    'city_name': 'Madrid'
                },
                {
                    'name': 'Madrid',
                    'iata_city_code': 'MAD',
                    'type': 'city'
                }
            ]
        }
        mock_get.return_value = mock_response
        
        resultado = self.motor.autocompletar_aeropuerto('madrid')
        
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado[0]['value'], 'MAD')
        self.assertIn('Madrid', resultado[0]['label'])
    
    @patch('core.scraper_motor.requests.get')
    def test_autocompletar_aeropuerto_sin_resultados(self, mock_get):
        """Test de autocompletado sin resultados"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': []}
        mock_get.return_value = mock_response
        
        resultado = self.motor.autocompletar_aeropuerto('zzzz')
        self.assertEqual(len(resultado), 0)
    
    @patch('core.scraper_motor.requests.get')
    def test_autocompletar_aeropuerto_error_api(self, mock_get):
        """Test de manejo de errores en autocompletado"""
        mock_get.side_effect = Exception("API Error")
        
        resultado = self.motor.autocompletar_aeropuerto('madrid')
        self.assertEqual(len(resultado), 0)
    
    @patch('core.scraper_motor.requests.post')
    def test_buscar_vuelos_success(self, mock_post):
        """Test de búsqueda de vuelos exitosa"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'offers': [
                    {
                        'id': 'off_test123',
                        'total_amount': '150.00',
                        'total_currency': 'EUR',
                        'owner': {'name': 'Test Airlines', 'iata_code': 'TA'},
                        'slices': [
                            {
                                'origin': {'iata_code': 'MAD'},
                                'destination': {'iata_code': 'BCN'},
                                'duration': 'PT1H30M',
                                'segments': [
                                    {
                                        'operating_carrier': {'iata_code': 'TA'},
                                        'departing_at': '2026-03-01T10:00:00Z',
                                        'arriving_at': '2026-03-01T11:30:00Z',
                                        'duration': 'PT1H30M'
                                    }
                                ]
                            }
                        ],
                        'conditions': {},
                        'available_services': []
                    }
                ]
            }
        }
        mock_post.return_value = mock_response
        
        resultado = self.motor.buscar_vuelos('MAD', 'BCN', '2026-03-01', adultos=1)
        
        self.assertIsInstance(resultado, list)
        self.assertGreater(len(resultado), 0)
        self.assertEqual(resultado[0]['id'], 'off_test123')
        self.assertEqual(resultado[0]['source'], 'Duffel')
    
    @patch('core.scraper_motor.requests.post')
    def test_crear_order_duffel_success(self, mock_post):
        """Test de creación de orden exitosa"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'data': {
                'id': 'ord_test456',
                'booking_reference': 'ABC123'
            }
        }
        mock_post.return_value = mock_response
        
        pasajeros = [
            {
                'id': 'pas_123',
                'given_name': 'Juan',
                'family_name': 'Pérez'
            }
        ]
        
        resultado = self.motor.crear_order_duffel(
            'off_test123',
            pasajeros,
            type='instant'
        )
        
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['order_id'], 'ord_test456')
        self.assertEqual(resultado['booking_reference'], 'ABC123')
    
    @patch('core.scraper_motor.requests.post')
    def test_crear_payment_intent_success(self, mock_post):
        """Test de creación de payment intent"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'data': {
                'id': 'pit_test789',
                'client_token': 'token_test'
            }
        }
        mock_post.return_value = mock_response
        
        resultado = self.motor.crear_payment_intent(Decimal('150.00'), 'EUR')
        
        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['data']['id'], 'pit_test789')
    
    def test_parse_duration(self):
        """Test de parseo de duración ISO"""
        self.assertEqual(self.motor._parse_duration('PT1H30M'), '1h 30m')
        self.assertEqual(self.motor._parse_duration('PT2H'), '2h 0m')
        self.assertEqual(self.motor._parse_duration('PT45M'), '0h 45m')
    
    @patch('core.scraper_motor.requests.post')
    def test_cancelar_orden_success(self, mock_post):
        """Test de cancelación de orden"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'id': 'ord_test456'}}
        mock_post.return_value = mock_response
        
        resultado = self.motor.cancelar_orden('ord_test456')
        
        self.assertTrue(resultado['success'])
    
    def test_cache_busqueda(self):
        """Test de sistema de caché"""
        # Primera búsqueda (debería cachear)
        cache_key = "test_cache_key"
        test_data = ['resultado1', 'resultado2']
        
        self.motor.cache[cache_key] = {
            'data': test_data,
            'timestamp': datetime.now()
        }
        
        # Verificar que está en caché
        self.assertIn(cache_key, self.motor.cache)
        self.assertEqual(self.motor.cache[cache_key]['data'], test_data)


class TestMotorBusquedaSinToken(unittest.TestCase):
    """Tests para escenarios sin configuración"""
    
    def test_init_sin_token(self):
        """Test de inicialización sin token de Duffel"""
        with patch.dict('os.environ', {}, clear=True):
            motor = MotorBusqueda()
            self.assertIsNone(motor.duffel_token)
    
    def test_autocompletar_sin_token(self):
        """Test de autocompletado sin token configurado"""
        with patch.dict('os.environ', {}, clear=True):
            motor = MotorBusqueda()
            resultado = motor.autocompletar_aeropuerto('madrid')
            self.assertEqual(len(resultado), 0)


class TestMotorBusquedaIntegration(unittest.TestCase):
    """Tests de integración (requieren credenciales reales)"""
    
    @unittest.skip("Test de integración - requiere API key real")
    def test_busqueda_real(self):
        """Test con API real de Duffel (skip por defecto)"""
        motor = MotorBusqueda()
        if motor.duffel_token:
            resultado = motor.buscar_vuelos('MAD', 'BCN', '2026-04-01', adultos=1)
            self.assertIsInstance(resultado, list)


def run_tests():
    """Ejecutar todos los tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestMotorBusqueda))
    suite.addTests(loader.loadTestsFromTestCase(TestMotorBusquedaSinToken))
    suite.addTests(loader.loadTestsFromTestCase(TestMotorBusquedaIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
