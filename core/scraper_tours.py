import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import re
from datetime import datetime

# --- CONFIGURACIÓN DE ENTORNO ---
# Permitir ejecución directa del script y cargar variables
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_session, Tour
from database import get_db_session, Tour
from core.security import descifrar
from dotenv import load_dotenv

load_dotenv()

class ScraperToursB2B:
    def __init__(self):
        self.session = requests.Session()
        # Headers para simular un navegador real y evitar bloqueos
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.creds = self._cargar_credenciales()

    def _cargar_credenciales(self):
        """Descifra y carga las credenciales desde .env (Para futuras conexiones API)"""
        claves = ['SAMA', 'SARAYA', 'EXPLORA', 'MONTURISTA', 'COSTA']
        credenciales = {}
        for k in claves:
            try:
                user_enc = os.getenv(f'{k}_USER')
                pass_enc = os.getenv(f'{k}_PASS')
                if user_enc and pass_enc:
                    credenciales[k] = {'user': descifrar(user_enc), 'pass': descifrar(pass_enc)}
            except:
                pass 
        return credenciales

    def scrape_sama_travel(self):
        """
        Scraper DEEP para Sama Travel (Versión Mejorada Inteligente).
        Extrae: Precio, Itinerario detallado, Fechas, Salidas y Detalles específicos.
        """
        tours = []
        print("\n🐫 --- Iniciando DEEP SCRAPING MASIVO de Sama Travel (MEJORADO) ---")

        # --- LISTA MAESTRA DE URLs (Todos los destinos) ---
        urls_tours = [
            # ORIENTE MEDIO
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/ARABIA_SAUDI/joyas_de_arabia_saudi",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/ARABIA_SAUDI/descubre_arabia_saudi",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/EMIRATOS_%C3%81RABES/dubai_y_estambul",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/EMIRATOS_%C3%81RABES/dubai_y_phuket",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/EMIRATOS_%C3%81RABES/escapada_a_omman",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/EMIRATOS_%C3%81RABES/DUBAI-MALDIVAS",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/JORDANIA/raices_de_jordania",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/JORDANIA/raices_de_jordania_y_desierto",
            "https://www.samatravel.com/es/Viajes/MEDIO_ORIENTE/JORDANIA/esencias_de_jordania",

            # ASIA CENTRAL Y CHINA
            "https://www.samatravel.com/es/Viajes/ASIA/UZBEQUISTAN/UZBEKISTAN-CLASICO",
            "https://www.samatravel.com/es/Viajes/ASIA/UZBEQUISTAN/RUTA-DE-LA-SEDA_",
            "https://www.samatravel.com/es/Viajes/ASIA/UZBEQUISTAN/RUTA-DE-LA-SEDA-Y-FERGANA",
            "https://www.samatravel.com/es/Viajes/ASIA/UZBEQUISTAN/RUTA-DE-LA-SEDA-Y-KAZAJISTAN",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-ESENCIAL",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-IMPERIAL",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-ESCENICA",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-RUTA-DE-LA-SEDA",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-TIERRA-DE-PANDAS",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-Y_CRUCERO-YANGTSE",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-AVATAR",
            "https://www.samatravel.com/es/Viajes/ASIA/CHINA/CHINA-Y-EL-TIBET",

            # JAPÓN
            "https://www.samatravel.com/es/Viajes/ASIA/JAPON/japon_express",
            "https://www.samatravel.com/es/Viajes/ASIA/JAPON/colores_de_japon",
            "https://www.samatravel.com/es/Viajes/ASIA/JAPON/JAPON-DE-ENSUE%C3%91O",
            "https://www.samatravel.com/es/Viajes/ASIA/JAPON/JAPON-KUMANO-KODO",

            # SUDESTE ASIÁTICO
            "https://www.samatravel.com/es/Viajes/ASIA/FILIPINAS/filipinas_esencial",
            "https://www.samatravel.com/es/Viajes/ASIA/FILIPINAS/paraiso_filipinas",
            "https://www.samatravel.com/es/Viajes/ASIA/FILIPINAS/AUTENTICA_FILIPINAS",
            "https://www.samatravel.com/es/Viajes/ASIA/FILIPINAS/FILIPINAS_ESENCIAL_Y_JOYAS_DE_PALAWAN_",
            "https://www.samatravel.com/es/Viajes/ASIA/INDONESIA/BALI-CULTURA-Y-PLAYA",
            "https://www.samatravel.com/es/Viajes/ASIA/INDONESIA/BALI-Y-PLAYAS-DE-GILI",
            "https://www.samatravel.com/es/Viajes/ASIA/INDONESIA/HONG_KONG_Y_BALI",
            "https://www.samatravel.com/es/Viajes/ASIA/INDONESIA/BALI-EXCLUSIVE",
            "https://www.samatravel.com/es/Viajes/ASIA/INDONESIA/BALI_SEMANA_SANTA_2026",
            "https://www.samatravel.com/es/Viajes/ASIA/MALASIA/CAPITALES_DE_ASIA",
            "https://www.samatravel.com/es/Viajes/ASIA/MALASIA/MALASIA_Y_SINGAPUR_CULTURA_Y_PLAYA",
            "https://www.samatravel.com/es/Viajes/ASIA/MALASIA/selva_y_playas_de_malasia",
            "https://www.samatravel.com/es/Viajes/ASIA/MALASIA/ORANGUTANES-EN-EL-BORNEO-MALAYO",
            "https://www.samatravel.com/es/Viajes/ASIA/MYANMAR%2c_LAOS_Y_CAMBOYA/camboya_y_vietnam_al_completo22",
            "https://www.samatravel.com/es/Viajes/ASIA/MYANMAR%2c_LAOS_Y_CAMBOYA/laos_al_completo_y_camboya",
            "https://www.samatravel.com/es/Viajes/ASIA/MYANMAR%2c_LAOS_Y_CAMBOYA/tesoros_de_indochina",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-EXPRESS",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-TRIANGULO-DE-ORO",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-RUTA-IMPERIAL",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI_NORTE_Y_PLAYAS",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-JUNGLA-Y-PLAYA",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-NORTE-Y-CAMBOYA",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-RUTA-IMPERIAL-Y-TRIBUS",
            "https://www.samatravel.com/es/Viajes/ASIA/TAILANDIA/THAI-IMPERIAL-Y-VIETNAM",
            "https://www.samatravel.com/es/Viajes/ASIA/VIETNAM/raices_de_vietnam_y_sapa",
            "https://www.samatravel.com/es/Viajes/ASIA/VIETNAM/descubre_vietnam",
            "https://www.samatravel.com/es/Viajes/ASIA/VIETNAM/THAI-IMPERIAL-Y-VIETNAM2",
            "https://www.samatravel.com/es/Viajes/ASIA/VIETNAM/camboya_y_vietnam_al_completo2",
            "https://www.samatravel.com/es/Viajes/ASIA/VIETNAM/descubre_vietnam222",

            # INDIA Y SRI LANKA
            "https://www.samatravel.com/es/Viajes/ASIA/INDIA/INDIA-A-TU-ALCANCE",
            "https://www.samatravel.com/es/Viajes/ASIA/INDIA/india_espiritual",
            "https://www.samatravel.com/es/Viajes/ASIA/INDIA/INDIA-INEDITA",
            "https://www.samatravel.com/es/Viajes/ASIA/SRI_LANKA/sri_lanka_al_completo",
            "https://www.samatravel.com/es/Viajes/ASIA/SRI_LANKA/SRI-LANKA-INEDITA",
            "https://www.samatravel.com/es/Viajes/ASIA/SRI_LANKA/SRI-LANKA-SAFARIS-DEL-SUR",
            "https://www.samatravel.com/es/Viajes/ASIA/SRI_LANKA/SRI-LANKA-Y-MALDIVAS",
            "https://www.samatravel.com/es/Viajes/ASIA/SRI_LANKA/sri_lanka_al_completo2",

            # EGIPTO
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/egipto_esencial",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/egipto_esencial_desde_Aswan",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/PARAISOS_DEL_MAR_ROJO",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/descubre_egipto",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/descubre_egipto_desde_aswan",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/paisajes_de_egipto_regional",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/EGIPTO-TODO-INCLUIDO2",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/egipto_todo_incluido_desde_aswan",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/secretos_nilo_todo_incluido_regional",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/GRAN-TOUR-DE-EGIPTO-Y-MAR-ROJO",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/egipto_esencia",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/descubre_egipto22",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/EGIPTO/EGIPTO-TODO-INCLUIDO22",

            # ÁFRICA Y OTROS
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/kenya_esencial",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/safari_niara",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/safari_samburu",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/descubre_tanzania",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/kenya_y_tanzania_esencial",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/KENYA/safari_niara222",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/MARRUECOS_Y_T%C3%9ANEZ/escapada_a_marruecos",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/MARRUECOS_Y_T%C3%9ANEZ/alma_de_marruecos",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/MARRUECOS_Y_T%C3%9ANEZ/descubre_marruecos",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/SENEGAL/SENEGAL_CULTURA_Y_PLAYA",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/SENEGAL/SENEGAL_COLONIAL",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/SENEGAL/descubre_senegal",
            "https://www.samatravel.com/es/Viajes/NORTE-DE-AFRICA/SENEGAL/PUEBLOS_Y_ETNIAS_DE_SENEGAL",

            # EUROPA, TURQUÍA, CÁUCASO
            "https://www.samatravel.com/es/Viajes/EUROPA/BALCANES/CROACIA_Y_BOSNIA_2026",
            "https://www.samatravel.com/es/Viajes/EUROPA/BALCANES/ALBANIA_Y_LAGO_OHRID",
            "https://www.samatravel.com/es/Viajes/EUROPA/BALCANES/GRAN_TOUR_POR_LOS_BALCANES",
            "https://www.samatravel.com/es/Viajes/EUROPA/BALCANES/BELLEZAS_DE_MONTENEGRO2",
            "https://www.samatravel.com/es/Viajes/EUROPA/BALCANES/ALBANIA%2c_MACEDONIA_DEL_NORTE_Y_GRECIA",
            "https://www.samatravel.com/es/Viajes/ASIA/ARMENIA/DESCUBRE-ARMENIA",
            "https://www.samatravel.com/es/Viajes/ASIA/ARMENIA/DESCUBRIENDO-GEORGIA",
            "https://www.samatravel.com/es/Viajes/ASIA/ARMENIA/armenia_gastronomica",
            "https://www.samatravel.com/es/Viajes/ASIA/ARMENIA/DESCUBRE-ARMENIA-Y-GEORGIA",
            "https://www.samatravel.com/es/Viajes/ASIA/ARMENIA/AZERBAIYAN_Y_GEORGIA",
            "https://www.samatravel.com/es/Viajes/EUROPA/TURQUIA/DESCUBRE_TURQUIA_SEMANA_SANTA_2026",
            "https://www.samatravel.com/es/Viajes/EUROPA/TURQUIA/TURQUIA_PUENTE_DE_MAYO_2026",
            "https://www.samatravel.com/es/Viajes/EUROPA/TURQUIA/DESCUBRE_TURQUIA_SEMANA_DE_PASCUA"
        ]

        total_urls = len(urls_tours)
        print(f"📋 Cargadas {total_urls} rutas maestras para procesar.")

        for index, url in enumerate(urls_tours, 1):
            try:
                print(f"   [{index}/{total_urls}] Analizando: {url}")
                # Timeout de 30s para dar tiempo a descargar todo
                resp = self.session.get(url, timeout=30)
                
                if resp.status_code != 200:
                    print(f"   ⚠️ Error {resp.status_code} en {url}")
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                # --- 1. EXTRACCIÓN DE DATOS BÁSICOS ---
                
                # TÍTULO (Mejorado para SEO/Meta)
                titulo = soup.find('meta', property='og:title')
                if titulo and titulo.get('content'):
                    titulo = titulo['content'].strip().replace(' - Sama Travel', '').replace(' | Sama Travel', '')
                else:
                    titulo_tag = soup.find('h1')
                    titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sin Título"
                
                # TITULO FALLBACK (Si meta está vacío)
                if not titulo:
                    h1 = soup.find('h1')
                    titulo = h1.get_text(strip=True) if h1 else "Tour Sama Travel"


                # DESCRIPCIÓN (Prioridad Párrafo Negrita > Meta > Intro)
                descripcion = ""
                # Prioridad 1: Párrafo en negrita (Introducción típica)
                intro_p = soup.select_one('p.font-weight-bold')
                if intro_p and len(intro_p.get_text(strip=True)) > 20:
                     descripcion = intro_p.get_text(strip=True)
                
                # Prioridad 2: Meta description
                if not descripcion:
                    meta_desc = soup.find('meta', property='og:description')
                    if meta_desc and meta_desc.get('content'):
                        descripcion = meta_desc['content'].strip()
                
                # Prioridad 3: Primer párrafo largo
                if not descripcion:
                    for p in soup.find_all('p', limit=5):
                        t = p.get_text(strip=True)
                        if len(t) > 100:
                            descripcion = t[:600]
                            break

                # PRECIO (Mejorado con selectores específicos)
                precio = 0.0
                precio_tag = soup.select_one('.price.font-size-20.font-weight-bold') # Selector específico
                if not precio_tag:
                     precio_tag = soup.select_one('.precio, .price, .amount, .precio-desde, .precio-final')
                
                if precio_tag:
                    txt = ''.join([c for c in precio_tag.get_text() if c.isdigit() or c == ',' or c == '.'])
                    txt = txt.replace('.', '').replace(',', '.')
                    try: precio = float(txt)
                    except: pass
                
                # DURACIÓN (Regex Inteligente)
                duracion = 8
                duracion_elem = soup.find(string=re.compile(r'\d+\s*d[ií]as?', re.I))
                if duracion_elem:
                    duracion_text = duracion_elem.get_text() if hasattr(duracion_elem, 'get_text') else str(duracion_elem)
                    match = re.search(r'(\d+)\s*d[ií]as?', duracion_text, re.IGNORECASE)
                    if match:
                        duracion = int(match.group(1))

                # --- 2. FECHAS Y SALIDAS ---
                texto_fechas = "Consultar fechas"
                temporada_inicio = None
                temporada_fin = None
                
                bloque_fechas = soup.find(string=re.compile(r'Salidas.*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|daily|diarias)', re.I))
                if bloque_fechas:
                     texto_fechas = bloque_fechas.strip()
                     # Extraer mes inicio/fin simple
                     meses_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                     encontrados = [m for m in meses_es if m in texto_fechas.lower()]
                     if encontrados:
                         temporada_inicio = encontrados[0].capitalize()
                         temporada_fin = encontrados[-1].capitalize() if len(encontrados) > 1 else encontrados[0].capitalize()


                # --- 3. ITINERARIO (Nuevo Parser Inteligente) ---
                itinerario_data = []
                itinerario_div = soup.select_one('.itinerary-wrapper')
                
                if itinerario_div:
                    # Lógica: Buscar títulos en azul (p.font-blue) y sus descripciones siguientes
                    dias_titulos = itinerario_div.select('p.font-blue')
                    for i, dt in enumerate(dias_titulos):
                        titulo_dia = dt.get_text(strip=True)
                        desc_dia = ""
                        
                        # Recorrer hermanos siguientes hasta encontrar otro título
                        sibling = dt.find_next_sibling('p')
                        while sibling and 'font-blue' not in sibling.get('class', []):
                             texto_sib = sibling.get_text(strip=True)
                             if texto_sib:
                                 desc_dia += texto_sib + " "
                             sibling = sibling.find_next_sibling('p')
                        
                        itinerario_data.append({
                            "dia": i + 1, 
                            "titulo": titulo_dia, 
                            "descripcion": desc_dia.strip()
                        })
                else:
                     # Fallback antiguo si no hay wrapper específico
                     dias_html = soup.select('.dia, .itinerario-dia, .accordion-item')
                     for i, dia_div in enumerate(dias_html, 1):
                        t = dia_div.find(['h3', 'h4', 'strong'])
                        d = dia_div.find('p')
                        itinerario_data.append({
                            "dia": i,
                            "titulo": t.get_text(strip=True) if t else f"Día {i}",
                            "descripcion": d.get_text(strip=True) if d else ""
                        })

                if not itinerario_data:
                    itinerario_data = [{"dia": 1, "titulo": "Consultar Itinerario", "descripcion": "Ver web oficial"}]


                # --- 4. INCLUYE / NO INCLUYE (Nuevo Parser JSON) ---
                incluye = []
                no_incluye = []
                
                services_wrapper = soup.select_one('.services-wrapper')
                if services_wrapper:
                    rows = services_wrapper.select('.row')
                    for row in rows:
                        header = row.select_one('.bg-blue')
                        content = row.select_one('.bg-white')
                        if header and content:
                            header_txt = header.get_text(strip=True).lower()
                            # Parsear contenido separando por <br>
                            items_html = content.decode_contents() 
                            items_raw = re.split(r'<br\s*/?>|\n', items_html)
                            clean_items = [re.sub(r'<[^>]+>', '', x).strip() for x in items_raw if x.strip()]
                            
                            if 'incluye' in header_txt and 'no incluye' not in header_txt:
                                incluye = clean_items
                            elif 'no incluye' in header_txt:
                                no_incluye = clean_items
                
                # Fallback antiguo para no_incluye si no se encontró en services_wrapper
                if not no_incluye:
                    div_no_incluye = soup.select_one('#no_incluye, .no-incluye, .not-includes')
                    if div_no_incluye:
                        items = [li.get_text(strip=True) for li in div_no_incluye.find_all('li')]
                        if items: no_incluye = items

                # --- 5. IMAGEN PRINCIPAL (Selector Específico) ---
                img_url = None
                img_tag = soup.select_one('img.img-fluid.w-100')
                if img_tag:
                     src = img_tag.get('src', '')
                     if 'Productos' in src: # Validar que es imagen de producto
                         img_url = src if src.startswith('http') else f"https://www.samatravel.com{src}"
                
                if not img_url:
                    # Fallback old
                    img_elem = soup.select_one('.slider img, .main-image img')
                    if img_elem and img_elem.get('src'):
                        src = img_elem.get('src')
                        img_url = src if src.startswith('http') else f"https://www.samatravel.com{src}"

                # Lógica de Destino (Maps)
                destino = "Multidestino"
                u = url.upper()
                if "FILIPINAS" in u: destino = "Filipinas"
                elif "INDIA" in u: destino = "India"
                elif "INDONESIA" in u or "BALI" in u: destino = "Indonesia"
                elif "JAPON" in u: destino = "Japón"
                elif "MALASIA" in u or "SINGAPUR" in u: destino = "Malasia"
                elif "MYANMAR" in u or "CAMBOYA" in u or "VIETNAM" in u: destino = "Indochina"
                elif "SRI_LANKA" in u: destino = "Sri Lanka"
                elif "TAILANDIA" in u: destino = "Tailandia"
                elif "EGIPTO" in u: destino = "Egipto"
                elif "KENYA" in u or "TANZANIA" in u: destino = "Kenia y Tanzania"
                elif "MARRUECOS" in u: destino = "Marruecos"
                elif "SENEGAL" in u: destino = "Senegal"
                elif "TURQUIA" in u: destino = "Turquía"
                elif "JORDANIA" in u: destino = "Jordania"
                elif "BALCANES" in u or "CROACIA" in u: destino = "Balcanes"
                elif "CHINA" in u: destino = "China"
                elif "UZBEQUISTAN" in u: destino = "Uzbekistán"
                elif "ARABIA" in u: destino = "Arabia Saudí"
                elif "EMIRATOS" in u or "DUBAI" in u: destino = "Emiratos Árabes"
                elif "ARMENIA" in u or "GEORGIA" in u: destino = "Cáucaso"

                # --- 6. CONSTRUCCIÓN DEL OBJETO FINAL ---
                tours.append({
                    'titulo': titulo,
                    'descripcion': descripcion,
                    'destino': destino,
                    'pais': destino, # Usar destino como país por defecto
                    'precio_desde': precio,
                    'duracion_dias': duracion,
                    'imagen_url': img_url if img_url else "https://images.unsplash.com/photo-1488646953014-85cb44e25828?w=800",
                    'proveedor': 'Sama Travel',
                    'url_proveedor': url,
                    'categoria': 'circuito',
                    'incluye': json.dumps(incluye, ensure_ascii=False) if incluye else '[]',
                    'no_incluye': json.dumps(no_incluye, ensure_ascii=False) if no_incluye else '[]',
                    'itinerario': json.dumps(itinerario_data, ensure_ascii=False),
                    'temporada_inicio': temporada_inicio,
                    'temporada_fin': temporada_fin,
                    'mapa_url': ''
                })

            except Exception as e:
                print(f"   ❌ Error crítico en {url}: {e}")

        return tours

    # --- SCRAPERS SIMULADOS (Mantenidos para no perder funcionalidad) ---
    def scrape_costa_cruceros(self):
        # ... (Tu código anterior de Costa Cruceros se mantiene igual si quieres) ...
        # Para abreviar, devolvemos lista vacía aquí, pero puedes pegar tu función anterior.
        return []

    def scrape_saraya_tours(self):
        return []

    def scrape_explora_traveller(self):
        return []

    def scrape_monturista(self):
        return []

    # --- FUNCIÓN DE ACTUALIZACIÓN DE BASE DE DATOS ---
    def actualizar_base_datos(self, tours):
        """Guarda o actualiza contando nuevos vs actualizados"""
        db = get_db_session()
        nuevos = 0
        actualizados = 0
        
        try:
            for tour_data in tours:
                # Usar URL del proveedor como identificador único
                # (el título puede estar vacío o duplicado)
                tour_existente = None
                if tour_data.get('url_proveedor'):
                    tour_existente = db.query(Tour).filter_by(
                        url_proveedor=tour_data['url_proveedor']
                    ).first()
                
                if tour_existente:
                    # Actualizar tour existente
                    for key, value in tour_data.items():
                        setattr(tour_existente, key, value)
                    tour_existente.fecha_actualizacion = datetime.now()
                    tour_existente.activo = True
                    actualizados += 1
                else:
                    # Crear nuevo tour
                    nuevo_tour = Tour(**tour_data)
                    nuevo_tour.activo = True
                    db.add(nuevo_tour)
                    nuevos += 1
            
            db.commit()
            print(f"✅ Sincronización Completada: {nuevos} Nuevos | {actualizados} Actualizados | Total: {len(tours)}")
        except Exception as e:
            db.rollback()
            print(f"❌ Error en DB: {e}")
        finally:
            db.close()

    def ejecutar_scraping_completo(self):
        print("\n🚀 --- INICIANDO PROCESO GLOBAL ---")
        todos = []
        
        # Ejecutar Sama (REAL)
        todos.extend(self.scrape_sama_travel())
        
        # Ejecutar otros (Si tuvieras datos reales)
        # todos.extend(self.scrape_costa_cruceros())
        
        if todos:
            self.actualizar_base_datos(todos)
        
        print(f"\n🏁 Fin del proceso. Total procesados: {len(todos)}")

if __name__ == '__main__':
    scraper = ScraperToursB2B()
    scraper.ejecutar_scraping_completo()
