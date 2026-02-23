#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para categorizar automáticamente los tours existentes
Añade continente, país, tipo de viaje, etc. a los tours scrapeados
"""

import sys
import os
import re
from datetime import date

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import get_db_session, Tour
from sqlalchemy import func
from slugify import slugify

# Mapeos de destinos a continentes
CONTINENTE_MAP = {
    # Asia
    'Japón': 'Asia', 'China': 'Asia', 'Tailandia': 'Asia', 'Vietnam': 'Asia',
    'Indonesia': 'Asia', 'Filipinas': 'Asia', 'Malasia': 'Asia', 'Singapur': 'Asia',
    'India': 'Asia', 'Sri Lanka': 'Asia', 'Nepal': 'Asia', 'Myanmar': 'Asia',
    'Laos': 'Asia', 'Camboya': 'Asia', 'Corea': 'Asia', 'Uzbekistán': 'Asia',
    'Jordania': 'Asia', 'Emiratos': 'Asia', 'Arabia': 'Asia', 'Turquía': 'Asia',
    
    # Europa
    'España': 'Europa', 'Francia': 'Europa', 'Italia': 'Europa', 'Grecia': 'Europa',
    'Portugal': 'Europa', 'Alemania': 'Europa', 'Reino Unido': 'Europa', 'Suiza': 'Europa',
    'Islandia': 'Europa', 'Noruega': 'Europa', 'Finlandia': 'Europa', 'Suecia': 'Europa',
    'Croacia': 'Europa', 'Eslovenia': 'Europa', 'Montenegro': 'Europa', 'Serbia': 'Europa',
    'Bosnia': 'Europa', 'Albania': 'Europa', 'Macedonia': 'Europa',
    'Georgia': 'Europa', 'Armenia': 'Europa', 'Azerbaiyán': 'Europa',
    
    # África
    'Egipto': 'África', 'Marruecos': 'África', 'Túnez': 'África', 'Kenia': 'África',
    'Tanzania': 'África', 'Sudáfrica': 'África', 'Namibia': 'África', 'Botswana': 'África',
    'Senegal': 'África', 'Etiopía': 'África', 'Madagascar': 'África',
    
    # América
    'Perú': 'América', 'Chile': 'América', 'Argentina': 'América', 'Brasil': 'América',
    'México': 'América', 'Cuba': 'América', 'Estados Unidos': 'América', 'Canadá': 'América',
    'Costa Rica': 'América', 'Panamá': 'América', 'Colombia': 'América', 'Ecuador': 'América',
    
    # Oceanía
    'Australia': 'Oceanía', 'Nueva Zelanda': 'Oceanía', 'Polinesia': 'Oceanía',
    'Fiji': 'Oceanía', 'Tahití': 'Oceanía'
}

# Palabras clave para tipos de viaje
TIPO_VIAJE_KEYWORDS = {
    'Playa': ['playa', 'resort', 'caribe', 'islas', 'maldivas', 'punta cana', 'riviera'],
    'Cultural': ['cultural', 'templo', 'museo', 'historia', 'patrimonio', 'milenario', 'antiguo'],
    'Aventura': ['aventura', 'trekking', 'safari', 'montaña', 'rafting', '4x4', 'glaciar'],
    'Circuito': ['circuito', 'ruta', 'recorrido', 'tour', 'itinerario', 'días'],
    'Crucero': ['crucero', 'navegación', 'barco', 'islas griegas', 'mediterráneo']
}

# Destinos populares (para marcar como destacados)
DESTINOS_POPULARES = [
    'Japón', 'Tailandia', 'Egipto', 'Grecia', 'Italia', 'Islandia', 
    'Perú', 'Kenia', 'Marruecos', 'Vietnam', 'Indonesia'
]


def detectar_continente(destino):
    """Detecta el continente basado en el destino"""
    if not destino:
        return None
    
    destino = destino.strip()
    
    # Buscar coincidencia exacta
    for pais, continente in CONTINENTE_MAP.items():
        if pais.lower() in destino.lower():
            return continente
    
    return None


def detectar_pais(destino):
    """Extrae el país principal del destino"""
    if not destino:
        return None
    
    destino = destino.strip()
    
    # Buscar coincidencia
    for pais in CONTINENTE_MAP.keys():
        if pais.lower() in destino.lower():
            return pais
    
    # Si no encuentra, usar el destino completo
    return destino.split(',')[0].strip()


def detectar_tipo_viaje(tour):
    """Detecta el tipo de viaje basado en título y descripción"""
    texto_completo = f"{tour.titulo or ''} {tour.descripcion or ''} {tour.categoria or ''}".lower()
    
    # Puntuar cada tipo
    scores = {}
    for tipo, keywords in TIPO_VIAJE_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in texto_completo)
        if score > 0:
            scores[tipo] = score
    
    # Retornar el tipo con mayor score
    if scores:
        return max(scores, key=scores.get)
    
    # Fallback basado en categoría
    if tour.categoria:
        return tour.categoria.capitalize()
    
    return 'Circuito'  # Default


def detectar_nivel_confort(tour):
    """Detecta el nivel de confort basado en precio y descripción"""
    precio = tour.precio_desde or 0
    texto = f"{tour.titulo or ''} {tour.descripcion or ''}".lower()
    
    # Palabras clave de lujo
    palabras_lujo = ['lujo', 'premium', 'exclusivo', '5 estrellas', 'boutique', 'deluxe']
    es_lujo = any(palabra in texto for palabra in palabras_lujo)
    
    if es_lujo or precio > 3000:
        return 'Lujo'
    elif precio > 2000:
        return 'Premium'
    elif precio > 1000:
        return 'Medio'
    else:
        return 'Económico'


def generar_slug(titulo):
    """Genera slug SEO-friendly"""
    if not titulo:
        return None
    
    # Usar slugify (instalar con: pip install python-slugify)
    try:
        return slugify(titulo, max_length=200)
    except:
        # Fallback manual
        slug = titulo.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = slug.strip('-')
        return slug[:200]


def generar_keywords(tour):
    """Genera keywords para búsqueda"""
    keywords = []
    
    if tour.destino:
        keywords.append(tour.destino.lower())
    if tour.pais:
        keywords.append(tour.pais.lower())
    if tour.categoria:
        keywords.append(tour.categoria.lower())
    if tour.tipo_viaje:
        keywords.append(tour.tipo_viaje.lower())
    
    # Extraer palabras importantes del título
    if tour.titulo:
        palabras = re.findall(r'\b[a-záéíóúñ]+\b', tour.titulo.lower())
        palabras_importantes = [p for p in palabras if len(p) > 4][:5]
        keywords.extend(palabras_importantes)
    
    return ', '.join(set(keywords))


def categorizar_tours():
    """Categoriza todos los tours de la base de datos"""
    db = get_db_session()
    
    try:
        tours = db.query(Tour).all()
        print(f"📊 Encontrados {len(tours)} tours para categorizar\n")
        
        tours_actualizados = 0
        tours_destacados = 0
        errores = []
        
        for tour in tours:
            try:
                # Detectar continente y país
                if not tour.continente:
                    tour.continente = detectar_continente(tour.destino)
                
                if not tour.pais:
                    tour.pais = detectar_pais(tour.destino)
                
                # Detectar tipo de viaje
                if not tour.tipo_viaje:
                    tour.tipo_viaje = detectar_tipo_viaje(tour)
                
                # Detectar nivel de confort
                if not tour.nivel_confort:
                    tour.nivel_confort = detectar_nivel_confort(tour)
                
                # Generar slug único
                if not tour.slug:
                    base_slug = generar_slug(tour.titulo)
                    slug = base_slug
                    counter = 1
                    while db.query(Tour).filter(Tour.slug == slug, Tour.id != tour.id).first():
                        slug = f"{base_slug}-{counter}"
                        counter += 1
                    tour.slug = slug
                
                # Generar keywords
                if not tour.keywords:
                    tour.keywords = generar_keywords(tour)
                
                # Marcar como destacado si cumple criterios
                if not tour.destacado:
                    es_popular = any(destino in (tour.destino or '') for destino in DESTINOS_POPULARES)
                    precio_alto = (tour.precio_desde or 0) > 2000
                    
                    if es_popular or precio_alto:
                        tour.destacado = True
                        tours_destacados += 1
                
                # Establecer precio_hasta si no existe
                if not tour.precio_hasta and tour.precio_desde:
                    tour.precio_hasta = tour.precio_desde * 1.5  # Estimación
                
                tours_actualizados += 1
                
                if tours_actualizados % 20 == 0:
                    print(f"✓ Procesados {tours_actualizados}/{len(tours)} tours...")
                
            except Exception as e:
                errores.append(f"Error en tour ID {tour.id}: {str(e)}")
                continue
        
        # Commit de cambios
        db.commit()
        
        print(f"\n✅ Categorización completada:")
        print(f"   - Tours actualizados: {tours_actualizados}")
        print(f"   - Tours destacados: {tours_destacados}")
        
        if errores:
            print(f"\n⚠️  Errores encontrados ({len(errores)}):")
            for error in errores[:10]:  # Mostrar máximo 10
                print(f"   - {error}")
        
        # Mostrar estadísticas
        print(f"\n📈 Estadísticas generales:")
        continentes = db.query(Tour.continente, func.count(Tour.id)).group_by(Tour.continente).all()
        for continente, count in continentes:
            print(f"   - {continente or 'Sin categorizar'}: {count} tours")
        
        print(f"\n🎯 Tipos de viaje:")
        tipos = db.query(Tour.tipo_viaje, func.count(Tour.id)).group_by(Tour.tipo_viaje).all()
        for tipo, count in tipos:
            print(f"   - {tipo or 'Sin categorizar'}: {count} tours")
        
    except Exception as e:
        print(f"❌ Error general: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    print("🚀 Iniciando categorización de tours...\n")
    categorizar_tours()
    print("\n✨ ¡Proceso completado!")
