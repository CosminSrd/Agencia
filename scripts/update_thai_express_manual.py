
import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_db_session, Tour

def update_thai_express():
    print("🚀 Updating THAI EXPRESS with manual high-quality data...")
    db = get_db_session()
    
    # 1. Find the tour
    # Try by URL or part of URL
    target_url_part = "THAI-EXPRESS"
    tour = db.query(Tour).filter(Tour.url_proveedor.ilike(f"%{target_url_part}%")).first()
    
    if not tour:
        print("❌ PRE-CHECK: Tour 'THAI EXPRESS' not found in DB. Creating a placeholder to update...")
        tour = Tour(
            url_proveedor="https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-EXPRESS",
            titulo="THAI EXPRESS",
            slug="thai-express-manual",
            activo=True
        )
        db.add(tour)
        db.commit()
        db.refresh(tour)
    
    print(f"   found tour: {tour.id} - {tour.titulo}")

    # 2. Prepare Data
    
    # Title & Description
    tour.titulo = "THAI EXPRESS: Bangkok - Phuket" # More descriptive title
    tour.destino = "Tailandia"
    tour.pais = "Tailandia"
    tour.descripcion = """El País de la Sonrisa nos invita a recorrer desde la vibrante Bangkok hasta los paisajes idílicos de sus playas. Un viaje que se enriquece con la exquisita gastronomía tailandesa, la magia de sus mercados y un legado cultural fascinante, convirtiendo cada instante en una experiencia verdaderamente inolvidable."""
    
    # Dates & Duration
    tour.duracion_dias = 9
    tour.temporada_inicio = "JAN 2026"
    tour.temporada_fin = "MAR 2027"
    
    # Price
    tour.precio_desde = 1495.0
    
    # Itinerary (Parsed from user text)
    itinerario_data = [
        {
            "dia": 1,
            "titulo": "CIUDAD DE ORIGEN – BANGKOK",
            "descripcion": "Embarque en vuelo con destino Bangkok. Noche a bordo"
        },
        {
            "dia": 2,
            "titulo": "BANGKOK",
            "descripcion": "Llegada al aeropuerto de Bangkok. Tras los trámites de inmigración y recogida de equipaje, traslado a su hotel. Tarde libre para descansar o empezar a disfrutar de esta vibrante ciudad."
        },
        {
            "dia": 3,
            "titulo": "BANGKOK",
            "descripcion": "Tras el desayuno, salida en autobús desde el hotel para recorrer las principales avenidas de la ciudad hasta llegar al vibrante barrio de Chinatown, donde realizaremos nuestra primera parada: el Wat Traimit, conocido como el Templo del Buda de Oro. Este santuario alberga una impresionante imagen de Buda de 5 toneladas de oro macizo, cuya historia es fascinante: permaneció oculta durante siglos bajo una capa de yeso para protegerla de la destrucción durante la guerra. La siguiente visita nos llevará al majestuoso Wat Pho, el Templo del Buda Reclinado. Aquí contemplaremos uno de los budas reclinados más grandes del mundo, con 46 metros de longitud, y descubriremos en la planta de sus pies un grabado extraordinario con 108 imágenes que simbolizan acciones positivas del budismo. Finalmente, de regreso al hotel, realizaremos una parada en la fábrica estatal de piedras preciosas, donde conoceremos más sobre este arte tradicional tailandés. Tarde libre y alojamiento."
        },
        {
            "dia": 4,
            "titulo": "BANGKOK",
            "descripcion": "Desayuno. Día libre a disposición. Posibilidad de realizar excursiones opcionales o seguir disfrutando de la ciudad y sus múltiples opciones de ocio."
        },
        {
            "dia": 5,
            "titulo": "BANGKOK - PHUKET",
            "descripcion": "Desayuno. A la hora indicada traslado al aeropuerto para tomar el vuelo con destino Phuket. Llegada y traslado al hotel y alojamiento."
        },
        {
            "dia": 6,
            "titulo": "PHUKET",
            "descripcion": "Desayuno en el hotel. Días libres para disfrutar de la isla a tu propio ritmo: desde excursiones opcionales que revelan la riqueza natural y cultural de Phuket, hasta la posibilidad de descansar en sus playas de arena blanca y aguas cristalinas. Alojamiento."
        },
        {
            "dia": 7,
            "titulo": "PHUKET",
            "descripcion": "Desayuno en el hotel. Días libres para disfrutar de la isla a tu propio ritmo: desde excursiones opcionales que revelan la riqueza natural y cultural de Phuket, hasta la posibilidad de descansar en sus playas de arena blanca y aguas cristalinas. Alojamiento."
        },
        {
            "dia": 8,
            "titulo": "PHUKET",
            "descripcion": "Desayuno en el hotel. Días libres para disfrutar de la isla a tu propio ritmo: desde excursiones opcionales que revelan la riqueza natural y cultural de Phuket, hasta la posibilidad de descansar en sus playas de arena blanca y aguas cristalinas. Alojamiento."
        },
        {
            "dia": 9,
            "titulo": "PHUKET - CIUDAD DE ORIGEN",
            "descripcion": "Desayuno en el hotel. Tiempo libre hasta la hora indicada de traslado al aeropuerto para embarcar en vuelo con destino a nuestra ciudad de origen. Noche a bordo. Llegada y fin de nuestros servicios."
        }
    ]
    tour.itinerario = json.dumps(itinerario_data, ensure_ascii=False)
    
    # Includes
    incluye_list = [
        "Vuelos internacionales",
        "Tasas de aeropuerto",
        "3 noches en Bangkok AD",
        "4 noches en Phuket AD",
        "Todos los traslados en vehículos acondicionados",
        "Visita de Bangkok con guía de habla hispana",
        "Vuelo interno Bangkok - Phuket",
        "Seguro básico de viaje"
    ]
    tour.incluye = json.dumps(incluye_list, ensure_ascii=False)
    
    # Excludes
    no_incluye_list = [
        "Gastos personales, bebidas en las comidas",
        "Propinas",
        "Ningún servicio no mencionado como incluido"
    ]
    tour.no_incluye = json.dumps(no_incluye_list, ensure_ascii=False)
    
    # Extra data (Observations, Hotels) - Assuming description or separate field if available, 
    # but for now appending important info to description or handling visually if needed.
    # We'll just stick to standard fields.
    
    tour.imagen_url = "https://images.unsplash.com/photo-1552465011-b4e21bf6e79a?q=80&w=2039&auto=format&fit=crop" # Generic nice Thailand image
    
    db.commit()
    print("✅ THAI EXPRESS updated successfully!")
    db.close()

if __name__ == "__main__":
    update_thai_express()
