/* --- JAVASCRIPT INTEGRAL - VIATGES CARCAIXENT (RSW STUDIO) --- */

(() => {
    const navEntries = typeof performance.getEntriesByType === 'function'
        ? performance.getEntriesByType('navigation')
        : [];

    const isReload = navEntries.length > 0
        ? navEntries[0].type === 'reload'
        : (performance.navigation && performance.navigation.type === 1);

    if (isReload) {
        if ('scrollRestoration' in history) {
            history.scrollRestoration = 'manual';
        }

        window.addEventListener('load', () => {
            window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
        }, { once: true });
    }
})();

document.addEventListener('DOMContentLoaded', () => {

    // ✅ Variables globales para cruceros (arreglado ReferenceError)
    const sidePanel = document.getElementById('side-panel');
    const overlay = document.getElementById('side-panel-overlay');
    const content = document.getElementById('panel-content');

    // Hacer accesibles globalmente para openPanel()
    if (sidePanel) window.sidePanel = sidePanel;
    if (overlay) window.overlay = overlay;
    if (content) window.content = content;

    // 1. CALENDARIOS
    const configCalendario = {
        locale: "es",
        dateFormat: "d/m/Y",
        minDate: "today",
        animate: true,
        onOpen: (s, d, instance) => instance.element.closest('.index-search-item').classList.add('is-active'),
        onClose: (s, d, instance) => instance.element.closest('.index-search-item').classList.remove('is-active')
    };

    const fechaIdaEl = document.getElementById("fecha-ida");
    const fechaVueltaEl = document.getElementById("fecha-vuelta");

    if (fechaIdaEl && !fechaIdaEl._flatpickr) flatpickr("#fecha-ida", configCalendario);
    if (fechaVueltaEl && !fechaVueltaEl._flatpickr) flatpickr("#fecha-vuelta", configCalendario);

    // 2. DESTINOS
    const areaClick = document.getElementById('destino-click-area');
    const menu = document.getElementById('dropdown-menu');
    const display = document.getElementById('current-dest-display');
    const hiddenInput = document.getElementById('selected-destination-id');

    const destinosData = [
        { nombre: "Nueva York", sub: "EE.UU — Urban Luxe", precio: "1.250€", img: "images/nuevayork.webp", icono: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L4.5 20.29l.71.71L12 18l6.79 3 .71-.71z"/></svg>' },
        { nombre: "Tokio", sub: "Japón — Tradición Viva", precio: "1.420€", img: "assets/images/tokio.jpg", icono: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>' },
        { nombre: "Bali", sub: "Indonesia — Alma Zen", precio: "980€", img: "assets/images/bali.jpg", icono: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>' },
        { nombre: "Riviera Maya", sub: "México — Paraíso Azul", precio: "890€", img: "assets/images/mexico.jpg", icono: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2m0 18v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M1 12h2m18 0h2"/></svg>' }
    ];

    if (menu) {
        let content = `<div class="index-dropdown-header" style="margin-bottom:15px; font-weight:700; color:#888; font-size:0.8rem; text-transform:uppercase;">Explora Destinos Premium</div><div class="index-options-grid">`;
        destinosData.forEach(dest => {
            content += `
                <div class="index-option" data-value="${dest.nombre}" data-price="${dest.precio}" data-img="${dest.img}">
                    <div class="opt-icon-box">${dest.icono}</div>
                    <div class="opt-text">
                        <span class="opt-title">${dest.nombre}</span>
                        <span class="opt-sub">${dest.sub}</span>
                    </div>
                </div>`;
        });
        menu.innerHTML = content + `</div>`;

        menu.querySelectorAll('.index-option').forEach(option => {
            option.addEventListener('click', (e) => {
                e.stopPropagation();
                const val = option.dataset.value;
                display.innerHTML = `<div class="selected-wrapper">${option.querySelector('.opt-icon-box').innerHTML} <span>${val}</span></div>`;
                display.classList.add('has-value');
                hiddenInput.value = val;
                hiddenInput.setAttribute('data-price', option.dataset.price);
                hiddenInput.setAttribute('data-img', option.dataset.img);
                menu.classList.remove('show');
                areaClick.classList.remove('is-active');
            });
        });
    }

    if (areaClick) {
        areaClick.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('show');
            areaClick.classList.toggle('is-active');
        });
    }

    window.addEventListener('click', () => {
        menu?.classList.remove('show');
        areaClick?.classList.remove('is-active');
    });

    // --- NUEVA FUNCIÓN PARA CERRAR SIN RECARGAR ---
    window.cerrarPopup = function () {
        const popup = document.getElementById('simulated-result');
        if (popup) popup.style.display = 'none';
    };

    // --- SIMULACIÓN BÚSQUEDA MEJORADA ---
    window.activarSimulacion = function () {
        const btn = document.querySelector('.index-btn-search');
        const popup = document.getElementById('simulated-result');
        const destinoId = document.getElementById('selected-destination-id');
        const fIda = document.getElementById('fecha-ida').value;
        const fVuelta = document.getElementById('fecha-vuelta').value;

        // Validación para que no pete si no hay fechas
        if (!destinoId.value || !fIda || !fVuelta) {
            btn.style.animation = "shake 0.5s ease";
            setTimeout(() => btn.style.animation = "", 500);
            return;
        }

        // CÁLCULO DINÁMICO DE PRECIO
        // Convertimos fechas d/m/Y a objetos Date
        const parseDate = (str) => {
            const [d, m, y] = str.split('/');
            return new Date(y, m - 1, d);
        };

        const date1 = parseDate(fIda);
        const date2 = parseDate(fVuelta);
        const noches = Math.max(1, Math.round((date2 - date1) / (1000 * 60 * 60 * 24)));

        // Precio base desde el atributo (limpiando puntos y símbolo euro)
        let precioBase = parseInt(destinoId.getAttribute('data-price').replace('.', '').replace('€', ''));
        // Si son más de 3 noches, sumamos 75€ por cada noche extra
        let precioCalculado = noches > 3 ? precioBase + ((noches - 3) * 75) : precioBase;

        btn.disabled = true;
        btn.innerHTML = `<span>DISEÑANDO...</span>`;

        setTimeout(() => {
            // Rellenar la card
            document.getElementById('card-img').src = destinoId.getAttribute('data-img');
            document.getElementById('card-title').innerText = destinoId.value;
            document.getElementById('card-date').innerText = `${noches} noches (${fIda} - ${fVuelta})`;
            document.getElementById('card-price').innerText = `Total: ${precioCalculado.toLocaleString('es-ES')}€`;

            // CONFIGURAR BOTÓN WHATSAPP
            const btnWp = popup.querySelector('.index-btn-ver');
            const mensaje = `Hola Andrea! 👋 Estoy interesado en un viaje a ${destinoId.value}. 
Fechas: del ${fIda} al ${fVuelta} (${noches} noches). 
Presupuesto estimado: ${precioCalculado}€. 
¿Podemos hablar de los detalles?`;

            // Link de WhatsApp de Viatges Carcaixent
            btnWp.onclick = () => {
                window.open(`https://wa.me/34600000000?text=${encodeURIComponent(mensaje)}`, '_blank');
            };
            btnWp.innerText = "RESERVAR POR WHATSAPP";

            popup.style.display = 'block';
            btn.disabled = false;
            btn.innerHTML = `<span>BUSCAR</span>`;
        }, 1200);
    };

    // 1. ESTADO SIEMPRE FIJO (Sin leer localStorage)
    // Esto asegura que al cargar el JS, la variable sea siempre 1 y 0
    const paxState = {
        adults: 1,
        kids: 0,
        seguro: 0
    };

    // 2. LIMPIEZA TOTAL DE MEMORIA NADA MÁS ARRANCAR
    localStorage.removeItem('pax_adults');
    localStorage.removeItem('pax_kids');
    localStorage.clear(); // Por si acaso hay más rastros

    function initPasajeros() {
        console.log("🚀 RSW Studio: Sistema reseteado. Iniciando desde 1 Adulto.");

        const sincronizarTodo = () => {
            const a = Number(paxState.adults);
            const k = Number(paxState.kids);
            const total = a + k;

            // Actualizar visualmente los números en el menú (+ y -)
            if (document.getElementById('pax-adults-val')) {
                document.getElementById('pax-adults-val').innerText = a;
            }
            if (document.getElementById('pax-kids-val')) {
                document.getElementById('pax-kids-val').innerText = k;
            }

            // Actualizar el texto del botón principal
            const display = document.getElementById('pasajeros-display');
            if (display) {
                display.innerText = `${a} Adulto${a > 1 ? 's' : ''}${k > 0 ? ' + ' + k + ' Niñ.' : ''}`;
            }

            // Generar formularios de datos
            const container = document.getElementById('pax-forms-container');
            if (container) {
                container.innerHTML = '';
                for (let i = 1; i <= total; i++) {
                    container.innerHTML += `
                    <div class="pax-card-luxe" style="background:rgba(255,255,255,0.05); padding:15px; margin-bottom:10px; border-radius:8px; border-left:3px solid #d4af37;">
                        <span style="color:#d4af37; font-size:0.7rem; font-weight:bold;">VIAJERO ${i}</span>
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:5px;">
                            <input type="text" placeholder="Nombre" style="background:transparent; border:none; border-bottom:1px solid #444; color:white; padding:5px;">
                            <input type="text" placeholder="DNI" style="background:transparent; border:none; border-bottom:1px solid #444; color:white; padding:5px;">
                        </div>
                    </div>`;
                }
            }
        };

        // Escuchador de clics
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-pax-action');

            if (btn) {
                e.preventDefault();
                e.stopPropagation();

                const type = btn.getAttribute('data-type');
                const step = parseInt(btn.getAttribute('data-step'));

                if (type === 'adults') {
                    const result = paxState.adults + step;
                    if (result >= 1 && result <= 10) paxState.adults = result;
                } else if (type === 'kids') {
                    const result = paxState.kids + step;
                    if (result >= 0 && result <= 10) paxState.kids = result;
                }

                sincronizarTodo();
                return;
            }

            // Dropdown
            const wrapper = document.getElementById('pasajeros-wrapper');
            const menu = document.getElementById('pasajeros-menu');
            if (wrapper && wrapper.contains(e.target)) {
                if (menu) menu.classList.toggle('show');
            } else if (menu && !menu.contains(e.target)) {
                menu.classList.remove('show');
            }
        });

        // Primera sincronización al cargar la página
        sincronizarTodo();
    }

    // Inicializamos
    initPasajeros();

    /* RSW STUDIO - ULTRA ENGINE V9 (SCROLL & NAVIGATION FIX)
       Partners: Salva, Rafa & Gemini
    */

    (function () {
        let tempUserData = { adultos: [], ninos: [] };
        let currentCategoryId = '';
        let currentCategoryName = '';
        let localPax = { adults: 1, kids: 0 };
        window.currentExtra = 0;
        window.extraName = 'Fly Light';

        const catalogos = {
            'cruceros': {
                viajes: [
                    { id: 'c1', nombre: 'Islas Griegas: Joyas del Egeo', precio: 890, dias: '8 Días', noches: '7 Noches', img: 'https://images.unsplash.com/photo-1533105079780-92b9be482077?w=800', desc: 'Mykonos, Santorini y Atenas a bordo.', incluye: ['Pensión completa', 'Tasas portuarias', 'Shows Broadway'] },
                    { id: 'c2', nombre: 'Caribe: Paraíso Turquesa', precio: 1150, dias: '10 Días', noches: '9 Noches', img: 'https://images.unsplash.com/photo-1544735716-392fe2489ffa?w=800', desc: 'Bahamas, Jamaica y Gran Caimán.', incluye: ['Vuelos directos', 'Todo incluido', 'Pack excursiones'] },
                    { id: 'c3', nombre: 'Fiordos: Ruta de los Glaciares', precio: 1320, dias: '8 Días', noches: '7 Noches', img: 'https://images.unsplash.com/photo-1527267207156-32837bc70462?w=800', desc: 'Navegación por Geiranger y Flam.', incluye: ['Vuelo desde Valencia', 'Seguro total', 'Guía local'] },
                    { id: 'c4', nombre: 'Mediterráneo: Historia Viva', precio: 750, dias: '7 Días', noches: '6 Noches', img: 'https://images.unsplash.com/photo-1516483638261-f4dbaf036963?w=800', desc: 'Roma, Cannes y Palma de Mallorca.', incluye: ['Bebidas ilimitadas', 'Wifi a bordo', 'Kids Club'] },
                    { id: 'c5', nombre: 'Capitales Bálticas', precio: 1450, dias: '9 Días', noches: '8 Noches', img: 'https://images.unsplash.com/photo-1512100356956-c1b47f4b8a21?w=800', desc: 'Copenhague, Tallín y Helsinki.', incluye: ['Cenas temáticas', 'Traslados VIP', 'Guía privado'] },
                    { id: 'c6', nombre: 'Crucero fluvial Rin Romántico', precio: 1680, dias: '7 Días', noches: '6 Noches', img: 'https://images.unsplash.com/photo-1559139225-3327f806639d?w=800', desc: 'Castillos y viñedos de Alemania.', incluye: ['Catas de vino', 'Bicicletas gratis', 'Todo exterior'] }
                ]
            },
            'japon': {
                viajes: [
                    { id: 'j1', nombre: 'Japón: Templos y Ryokans', precio: 1250, dias: '12 Días', noches: '11 Noches', img: 'https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=800', desc: 'Ruta por Kyoto y los Alpes Japoneses.', incluye: ['JR Pass 7 días', 'Noche en Ryokan', 'Taller de Sushi'] },
                    { id: 'j2', nombre: 'Tokio: Neón y Futuro', precio: 1400, dias: '9 Días', noches: '8 Noches', img: 'https://images.unsplash.com/photo-1503899036084-c55cdd92da26?w=800', desc: 'Shibuya, Akihabara y el Monte Fuji.', incluye: ['Entradas TeamLab', 'Cena Robot', 'WiFi Pocket'] },
                    { id: 'j3', nombre: 'Osaka y Universal Studios', precio: 1100, dias: '8 Días', noches: '7 Noches', img: 'https://images.unsplash.com/photo-1590559899731-a382839e5549?w=800', desc: 'Gastronomía y diversión en Osaka.', incluye: ['Entrada Universal', 'Tour gastronómico', 'Hotel 4*'] },
                    { id: 'j4', nombre: 'Ruta de los Samurai (Kanazawa)', precio: 1550, dias: '14 Días', noches: '13 Noches', img: 'https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=800', desc: 'El Japón más auténtico y feudal.', incluye: ['Trenes incluidos', 'Guía historiador', 'Hoteles Zen'] },
                    { id: 'j5', nombre: 'Hokkaido: Naturaleza Salvaje', precio: 1890, dias: '10 Días', noches: '9 Noches', img: 'https://images.unsplash.com/photo-1516466723877-e4ec1d736c8a?w=800', desc: 'Parques nacionales y Onsens.', incluye: ['Coche alquiler', 'Vuelos internos', 'Seguro nieve'] },
                    { id: 'j6', nombre: 'Okinawa: El Caribe Japonés', precio: 1720, dias: '9 Días', noches: '8 Noches', img: 'https://images.unsplash.com/photo-1542358935821-e4e9f3f3c15d?w=800', desc: 'Playas de arena blanca y buceo.', incluye: ['Resort 5*', 'Curso buceo', 'Traslados lujo'] }
                ]
            },
            'islandia': {
                viajes: [
                    { id: 'i1', nombre: 'Auroras Boreales Mágicas', precio: 1850, dias: '6 Días', noches: '5 Noches', img: 'https://images.unsplash.com/photo-1531366930477-4f20f803fdf9?w=800', desc: 'Caza de auroras con fotógrafo experto.', incluye: ['Hoteles boutique', '4x4 privado', 'Trajes térmicos'] },
                    { id: 'i2', nombre: 'La Ring Road Completa', precio: 2200, dias: '11 Días', noches: '10 Noches', img: 'https://images.unsplash.com/photo-1476610182048-b716b8518aae?w=800', desc: 'Vuelta a la isla por la costa.', incluye: ['Avistamiento ballenas', 'Entrada Blue Lagoon', 'Guía 24h'] },
                    { id: 'i3', nombre: 'Cuevas de Cristal y Hielo', precio: 1650, dias: '5 Días', noches: '4 Noches', img: 'https://images.unsplash.com/photo-1481487196290-c152efe083f5?w=800', desc: 'Explora glaciares milenarios.', incluye: ['Equipamiento técnico', 'Hotel en glaciares', 'Vuelo desde VLC'] },
                    { id: 'i4', nombre: 'Islandia: Verano Infinito', precio: 1950, dias: '8 Días', noches: '7 Noches', img: 'https://images.unsplash.com/photo-1504829857797-ddff29c27927?w=800', desc: 'Cascadas y sol de medianoche.', incluye: ['Coche 4x4', 'Acampada lujo', 'Ruta senderismo'] },
                    { id: 'i5', nombre: 'Tierras Altas (Interior)', precio: 2400, dias: '9 Días', noches: '8 Noches', img: 'https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800', desc: 'Aventura extrema en el desierto.', incluye: ['Super Jeep', 'Comidas gourmet', 'Guía montaña'] },
                    { id: 'i6', nombre: 'Bienestar y Relax Termal', precio: 1590, dias: '5 Días', noches: '4 Noches', img: 'https://images.unsplash.com/photo-1520175480921-4edfa0683a2f?w=800', desc: 'Los mejores Onsens del norte.', incluye: ['Pases VIP termas', 'Masajes incluidos', 'Hoteles Spa'] }
                ]
            }
        };

        // FUNCIÓN PARA BLOQUEAR/DESBLOQUEAR SCROLL TOTAL
        function toggleScroll(block) {
            if (block) {
                document.documentElement.style.overflow = 'hidden';
                document.body.style.overflow = 'hidden';
                document.body.style.touchAction = 'none'; // Para móviles
            } else {
                document.documentElement.style.overflow = '';
                document.body.style.overflow = '';
                document.body.style.touchAction = '';
            }
        }

        window.cerrarSistema = function () {
            tempUserData = { adultos: [], ninos: [] };
            localPax = { adults: 1, kids: 0 };
            toggleScroll(false);
            const modal = document.getElementById('rsw-checkout');
            modal.classList.remove('active');
            setTimeout(() => modal.style.display = 'none', 400);
        };

        function saveCurrentInputs() {
            const aduRows = document.querySelectorAll('.row-adu');
            const ninRows = document.querySelectorAll('.row-nin');
            tempUserData.adultos = Array.from(aduRows).map(r => ({ n: r.querySelector('.r-name').value, d: r.querySelector('.r-dni').value }));
            tempUserData.ninos = Array.from(ninRows).map(r => ({ n: r.querySelector('.r-name').value, d: r.querySelector('.r-dni').value }));
        }

        if (!document.getElementById('rsw-v9-css')) {
            const style = document.createElement('style');
            style.id = 'rsw-v9-css';
            style.innerHTML = `
            #rsw-checkout { position: fixed; inset: 0; background: rgba(10, 15, 30, 0.5); backdrop-filter: blur(25px); z-index: 2147483647; display: none; align-items: center; justify-content: center; opacity: 0; transition: opacity 0.4s ease; font-family: 'Plus Jakarta Sans', sans-serif; }
            #rsw-checkout.active { opacity: 1; display: flex; }
            .rsw-window { background: #fff; width: 95%; max-width: 1250px; height: 88vh; border-radius: 40px; display: grid; grid-template-columns: 1.6fr 1fr; overflow: hidden; box-shadow: 0 50px 100px -20px rgba(0,0,0,0.5); transform: translateY(30px); transition: 0.5s cubic-bezier(0.19, 1, 0.22, 1); position: relative; }
            #rsw-checkout.active .rsw-window { transform: translateY(0); }
            
            .rsw-left { padding: 50px; overflow-y: auto; scrollbar-width: thin; position: relative; }
            .rsw-right { background: #F8FAFC; padding: 50px; border-left: 1px solid #E2E8F0; display: flex; flex-direction: column; overflow-y: auto; }
            
            .btn-close { position: absolute; top: 25px; right: 25px; background: #fff; border: 1px solid #E2E8F0; width: 45px; height: 45px; border-radius: 50%; cursor: pointer; transition: 0.3s; z-index: 9999; display: flex; align-items: center; justify-content: center; }
            .btn-close:hover { background: #000; color: #fff; transform: rotate(90deg); }
            
            .catalog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; margin-top: 30px; }
            .v-card { border-radius: 25px; border: 1px solid #F1F5F9; overflow: hidden; cursor: pointer; transition: 0.4s; background: #fff; text-align: left; }
            .v-card:hover { transform: translateY(-8px); border-color: #D4AF37; box-shadow: 0 20px 40px rgba(0,0,0,0.1); }
            
            .pax-row { display: grid; grid-template-columns: 1fr 140px; gap: 12px; margin-bottom: 10px; }
            .pax-row input { padding: 15px; border: 2px solid #F1F5F9; border-radius: 15px; font-size: 0.9rem; background: #F8FAFC; }
            .pax-row input:focus { border-color: #D4AF37; background: #fff; outline: none; }
            
            .extra-pill { border: 2.5px solid #F1F5F9; padding: 20px; border-radius: 20px; cursor: pointer; transition: 0.3s; margin-bottom: 12px; background: #fff; }
            .extra-pill.active { border-color: #D4AF37; background: #FFFDF5; }
            
            .btn-confirm { background: #0F172A; color: #fff; padding: 22px; border-radius: 20px; border: none; font-weight: 800; cursor: pointer; font-size: 1.1rem; transition: 0.3s; width: 100%; margin-top: auto; }
            .btn-confirm:hover { background: #000; transform: scale(1.02); }

            @media (max-width: 950px) { .rsw-window { grid-template-columns: 1fr; } .rsw-right { border-left: none; border-top: 1px solid #eee; } }
        `;
            document.head.appendChild(style);
        }

        window.iniciarReserva = function (cat, title) {
            currentCategoryId = cat;
            currentCategoryName = title;
            toggleScroll(true); // BLOQUEO RADICAL
            const modal = document.getElementById('rsw-checkout');
            modal.style.display = 'flex';
            setTimeout(() => modal.classList.add('active'), 10);
            renderCatalog();
        };

        // ASIGNAR ESTA FUNCIÓN AL BOTÓN "VOLVER"
        window.volverAlCatalogo = function () {
            saveCurrentInputs();
            renderCatalog();
        };

        function renderCatalog() {
            const data = catalogos[currentCategoryId];
            const container = document.getElementById('rsw-checkout');
            container.innerHTML = `
            <div class="rsw-window" style="display:block; padding:60px; text-align:center; overflow-y:auto;">
                <button class="btn-close" onclick="cerrarSistema()">✕</button>
                <span style="color:#D4AF37; font-weight:800; font-size:0.7rem; letter-spacing:4px;">RSW STUDIO | VIATGES CARCAIXENT</span>
                <h2 style="font-size:2.8rem; margin:10px 0 45px;">${currentCategoryName}</h2>
                <div class="catalog-grid">
                    ${data.viajes.map(v => `
                        <div class="v-card" onclick="renderCheckout('${v.id}')">
                            <div style="height:180px; background:url('${v.img}') center/cover;"></div>
                            <div style="padding:25px;">
                                <div style="display:flex; justify-content:space-between; color:#D4AF37; font-weight:bold; font-size:0.75rem; margin-bottom:8px;">
                                    <span>${v.noches.toUpperCase()}</span>
                                    <span>${v.dias}</span>
                                </div>
                                <h3 style="margin:0 0 12px; font-size:1.3rem;">${v.nombre}</h3>
                                <p style="color:#64748B; font-size:0.85rem; line-height:1.4; margin-bottom:15px;">${v.desc}</p>
                                <div style="border-top:1px solid #F1F5F9; padding-top:15px; display:flex; justify-content:space-between; align-items:center;">
                                    <strong style="font-size:1.4rem;">${v.precio}€</strong>
                                    <span style="font-weight:bold; color:#0F172A; font-size:0.8rem;">RESERVAR</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        }

        window.renderCheckout = function (tripId) {
            saveCurrentInputs();
            const viaje = catalogos[currentCategoryId].viajes.find(v => v.id === tripId);
            const total = ((viaje.precio * localPax.adults) + ((viaje.precio * 0.5) * localPax.kids)) + (window.currentExtra * (localPax.adults + localPax.kids));

            document.getElementById('rsw-checkout').innerHTML = `
            <div class="rsw-window">
                <button class="btn-close" onclick="cerrarSistema()">✕</button>
                <div class="rsw-left">
                    <button onclick="volverAlCatalogo()" style="background:none; border:none; color:#D4AF37; cursor:pointer; font-weight:800; margin-bottom:20px; font-size:0.9rem; padding:0;">← VOLVER AL CATÁLOGO</button>
                    <h2 style="font-size:2.2rem; margin-bottom:10px;">${viaje.nombre}</h2>
                    <p style="color:#64748B; margin-bottom:35px;">Configuración de reserva profesional.</p>

                    <div style="display:flex; gap:30px; margin-bottom:30px;">
                        <div>
                            <span style="font-size:0.7rem; font-weight:800; color:#94A3B8; display:block; margin-bottom:8px;">ADULTOS</span>
                            <div style="display:flex; align-items:center; gap:15px; background:#F8FAFC; padding:10px 20px; border-radius:15px; border:1px solid #E2E8F0;">
                                <button onclick="updateP(-1,0,'${tripId}')" style="border:none; cursor:pointer; background:none; font-weight:bold; font-size:1.2rem;">-</button>
                                <span style="font-weight:900;">${localPax.adults}</span>
                                <button onclick="updateP(1,0,'${tripId}')" style="border:none; cursor:pointer; background:none; font-weight:bold; font-size:1.2rem;">+</button>
                            </div>
                        </div>
                        <div>
                            <span style="font-size:0.7rem; font-weight:800; color:#94A3B8; display:block; margin-bottom:8px;">NIÑOS (Dto. 50%)</span>
                            <div style="display:flex; align-items:center; gap:15px; background:#F8FAFC; padding:10px 20px; border-radius:15px; border:1px solid #E2E8F0;">
                                <button onclick="updateP(0,-1,'${tripId}')" style="border:none; cursor:pointer; background:none; font-weight:bold; font-size:1.2rem;">-</button>
                                <span style="font-weight:900;">${localPax.kids}</span>
                                <button onclick="updateP(0,1,'${tripId}')" style="border:none; cursor:pointer; background:none; font-weight:bold; font-size:1.2rem;">+</button>
                            </div>
                        </div>
                    </div>

                    <div id="pax-list">
                        ${Array.from({ length: localPax.adults }, (_, i) => `
                            <div class="pax-row row-adu">
                                <input type="text" placeholder="Nombre Adulto ${i + 1}" class="r-name" value="${tempUserData.adultos[i]?.n || ''}">
                                <input type="text" placeholder="DNI / Pasaporte" class="r-dni" value="${tempUserData.adultos[i]?.d || ''}">
                            </div>
                        `).join('')}
                        ${Array.from({ length: localPax.kids }, (_, i) => `
                            <div class="pax-row row-nin">
                                <input type="text" placeholder="Nombre Niño ${i + 1}" class="r-name" value="${tempUserData.ninos[i]?.n || ''}">
                                <input type="text" placeholder="DNI / NIE" class="r-dni" value="${tempUserData.ninos[i]?.d || ''}">
                            </div>
                        `).join('')}
                    </div>

                    <div style="margin-top:40px; background:#F8FAFC; padding:25px; border-radius:25px; border:1px solid #E2E8F0;">
                        <h4 style="margin:0 0 12px; font-size:1rem; color:#0F172A;">Itinerario e Inclusiones</h4>
                        <ul style="margin:0; padding-left:18px; color:#64748B; font-size:0.85rem; line-height:1.8;">
                            ${viaje.incluye.map(item => `<li>${item}</li>`).join('')}
                        </ul>
                    </div>
                </div>

                <div class="rsw-right">
                    <h4 style="margin:0 0 20px; color:#64748B; font-size:0.75rem; letter-spacing:1px; font-weight:800;">TARIFA SELECCIONADA</h4>
                    <div class="extra-pill ${window.currentExtra === 0 ? 'active' : ''}" onclick="changeExtra(0, 'Fly Light', '${tripId}')">
                        <strong style="font-size:1rem; display:block; margin-bottom:4px;">Fly Light</strong>
                        <p style="margin:0; font-size:0.8rem; color:#64748B;">Equipaje de mano estándar.</p>
                        <div style="margin-top:10px; font-weight:900;">+ 0€</div>
                    </div>
                    <div class="extra-pill ${window.currentExtra > 0 ? 'active' : ''}" onclick="changeExtra(145, 'Premium RSW', '${tripId}')">
                        <strong style="font-size:1rem; display:block; margin-bottom:4px; color:#D4AF37;">Premium RSW Pack</strong>
                        <p style="margin:0; font-size:0.8rem; color:#64748B;">Maleta 23kg + Seguros VIP.</p>
                        <div style="margin-top:10px; font-weight:900; color:#D4AF37;">+ 145€ / pers.</div>
                    </div>

                    <div style="margin-top:auto; padding-top:30px; border-top:2px dashed #E2E8F0;">
                        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:20px;">
                            <span style="font-weight:800; font-size:1.1rem; color:#64748B;">TOTAL</span>
                            <span style="font-size:3.2rem; font-weight:900; color:#0F172A; line-height:1;">${total.toFixed(0)}€</span>
                        </div>
                        <button class="btn-confirm" onclick="finalizarReserva('${viaje.nombre}', ${total})">CONFIRMAR RESERVA</button>
                    </div>
                </div>
            </div>
        `;
        };

        window.updateP = function (a, k, id) { saveCurrentInputs(); localPax.adults = Math.max(1, localPax.adults + a); localPax.kids = Math.max(0, localPax.kids + k); renderCheckout(id); };
        window.changeExtra = function (e, l, id) { saveCurrentInputs(); window.currentExtra = e; window.extraName = l; renderCheckout(id); };

        window.finalizarReserva = function (v, t) {
            saveCurrentInputs();
            alert(`RSW Studio - Reserva de "${v}" lista.\nTotal: ${t}€`);
            cerrarSistema();
        };
    })();


    // 4. SCROLL & PARALLAX
    const header = document.querySelector('.main-header');
    const heroBg = document.querySelector('.index-hero-bg');

    window.addEventListener('scroll', () => {
        const scrolled = window.pageYOffset;
        header?.classList.toggle('header-scrolled', scrolled > 50);
        if (heroBg) heroBg.style.transform = `scale(1.1) translateY(${scrolled * 0.25}px)`;
    });

    // 5. ANIMACIONES DE ENTRADA & CONTADORES
    const revealElements = document.querySelectorAll('.counter, .reveal-up');
    const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                if (entry.target.classList.contains('counter')) animateCounter(entry.target);
                else entry.target.classList.add('active');
                revealObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    revealElements.forEach(el => revealObserver.observe(el));

    function animateCounter(el) {
        const target = +el.getAttribute('data-target');
        let count = 0;
        const update = () => {
            count++;
            el.innerText = count + (target === 100 ? '%' : '+');
            if (count < target) setTimeout(update, 2000 / target);
        };
        update();
    }
});

/* --- FUNCIONES DE CATÁLOGO Y MODALES (FUERA DEL DOM) --- */

function activarSimulacion() {
    const hiddenInput = document.getElementById('selected-destination-id');
    const destino = hiddenInput.value;
    const precio = hiddenInput.getAttribute('data-price');
    const foto = hiddenInput.getAttribute('data-img');
    const popup = document.getElementById('simulated-result');

    if (!destino) { alert("Por favor elige un destino primero."); return; }

    document.getElementById('card-title').innerText = "Viaje a " + destino;
    document.getElementById('card-price').innerText = precio;
    document.getElementById('card-img').src = foto;
    popup.classList.add('active');
}

function mostrarDetalle(tipo) {
    const modal = document.getElementById('custom-modal');
    const container = document.querySelector('.modal-features');
    const iconContainer = document.getElementById('modal-icon');
    const btn = document.getElementById('btn-envio');

    const catalog = {
        'cruceros': {
            titulo: "Cruceros Exclusive",
            svg: `<svg viewBox="0 0 24 24" width="60" height="60" stroke="#0056b3" stroke-width="1.5" fill="none"><path d="M2 21h20M19.38 20L21 7l-9-4-9 4 1.62 13M12 3v7M12 13h7M7 13h2"></path></svg>`,
            opciones: [
                { nombre: "Wonder of the Seas", desc: "Ruta Islas Griegas y Turquía.", dias: "8 días / 7 noches", plus: "Todo Incluido Premium" },
                { nombre: "MSC World Europa", desc: "Mediterráneo Occidental.", dias: "7 días", plus: "Bebidas incluido" }
            ]
        },
        'japon': {
            titulo: "Esencia de Japón",
            svg: `<svg viewBox="0 0 24 24" width="60" height="60" stroke="#e63946" stroke-width="1.5" fill="none"><path d="M2 20h20M7 20v-5M17 20v-5M3 15h18L12 4 3 15z"></path></svg>`,
            opciones: [
                { nombre: "Circuito Clásico", desc: "Tokio, Kioto y Osaka.", dias: "12 días", plus: "Hoteles 5* y JR Pass" },
                { nombre: "Japón Rural", desc: "Alpes japoneses y aldeas.", dias: "10 días", plus: "Experiencia en Ryokan" }
            ]
        },
        'islandia': {
            titulo: "Islandia Salvaje",
            svg: `<svg viewBox="0 0 24 24" width="60" height="60" stroke="#00b894" stroke-width="1.5" fill="none"><path d="M4 22L12 6l8 16M10 18l2-4 2 4"></path></svg>`,
            opciones: [
                { nombre: "Ring Road Express", desc: "Vuelta completa en 4x4.", dias: "9 días", plus: "Seguro total" },
                { nombre: "Auroras Boreales", desc: "Glaciares y luces.", dias: "5 días", plus: "Garantizado" }
            ]
        },
        'kenia': {
            titulo: "Safari en Kenia",
            svg: `<svg viewBox="0 0 24 24" width="60" height="60" stroke="#d35400" stroke-width="1.5" fill="none"><path d="M12 22v-9M5 20l2-5h10l2 5M12 13L7 9M12 13l5-4M12 7a4 4 0 100-8 4 4 0 000 8z"></path></svg>`,
            opciones: [
                { nombre: "Aventura Masai Mara", desc: "Safari fotográfico.", dias: "9 días", plus: "Lodge de lujo" },
                { nombre: "Kenia y Zanzíbar", desc: "Safari y relax.", dias: "14 días", plus: "Pensión completa" }
            ]
        }
    };

    const data = catalog[tipo];
    document.getElementById('modal-title').innerText = data.titulo;
    iconContainer.innerHTML = data.svg;
    container.innerHTML = data.opciones.map(opt => `
        <div class="mini-card" onclick="seleccionarOpcion(this, '${opt.nombre}')">
            <h4>${opt.nombre}</h4>
            <p>${opt.desc}</p>
            <div class="details">⏳ ${opt.dias} | ✨ ${opt.plus}</div>
        </div>`).join('');

    modal.classList.add('active');
}

let opcionSeleccionada = null;
function seleccionarOpcion(elemento, nombre) {
    document.querySelectorAll('.mini-card').forEach(card => card.classList.remove('selected'));
    elemento.classList.add('selected');
    opcionSeleccionada = nombre;
    const btn = document.getElementById('btn-envio');
    btn.disabled = false;
    btn.querySelector('.btn-text').innerText = "SOLICITAR INFO PARA " + nombre.toUpperCase();
}

function enviarSolicitud(btn) {
    const textSpan = btn.querySelector('.btn-text');
    textSpan.innerText = "ENVIANDO...";
    btn.disabled = true;
    setTimeout(() => {
        btn.classList.add('enviado');
        textSpan.innerText = "✓ ¡SOLICITUD ENVIADA!";
        setTimeout(() => { cerrarModal(); }, 1500);
    }, 1500);
}

function cerrarModal() {
    document.getElementById('custom-modal').classList.remove('active');
}

function verMasDetalles() {
    alert("¡Próximamente! Estamos preparando el itinerario detallado.");
}

// --- SIDEBAR "DEEP TRAVEL" ENGINE ---

function openPanel(filterType) {
    if (!window.CRUISES_DATA) return;

    // ✅ Usar referencias globales
    const sidePanel = window.sidePanel;
    const overlay = window.overlay;
    const content = window.content;

    if (!sidePanel || !overlay || !content) {
        console.error('❌ Elementos del panel no encontrados');
        return;
    }

    // 1. Filtrar Datos
    let filteredTours = [];
    let title = "";

    if (filterType === 'msc' || filterType === 'mediterraneo') {
        title = "Cruceros Mediterráneo";
        filteredTours = window.CRUISES_DATA.filter(t => t.destino.toLowerCase().includes('mediterr'));
    } else {
        title = "Grandes Viajes & Fiordos";
        filteredTours = window.CRUISES_DATA.filter(t => !t.destino.toLowerCase().includes('mediterr'));
    }

    // 2. Renderizar LISTA
    content.innerHTML = `
            <div class="panel-header-img" style="background-image: url('${filteredTours[0]?.img || ''}')"></div>
            <div class="panel-body">
                <button class="close-panel-btn" onclick="closePanel()">✕</button>
                <h2>${title}</h2>
                <p class="panel-desc">Selecciona un itinerario para ver la ruta animada y los detalles día a día.</p>
                
                <div class="tours-list-sidebar">
                    ${filteredTours.map((t, i) => `
                        <div class="sidebar-tour-card" onclick="showTourDetails(${i})">
                            <div class="st-img" style="background-image:url('${t.img}')"></div>
                            <div class="st-info">
                                <h4>${t.titulo}</h4>
                                <span>Desde ${t.precio}€</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            <!-- Contenedor invisible para detalles -->
            <div id="tour-detail-view" class="tour-detail-view" style="display:none;"></div>
        `;

    // Guardar para uso
    window.currentFilteredTours = filteredTours;

    sidePanel.classList.add('active');
    overlay.classList.add('active');
    document.body.style.overflow = 'hidden';
}

window.showTourDetails = function (index) {
    const tour = window.currentFilteredTours[index];
    const detailView = document.getElementById('tour-detail-view');

    // Parsear Itinerario (viene como objeto o string JSON si falló el parsing de flask)
    let itinerary = [];
    if (typeof tour.itinerario === 'string') itinerary = JSON.parse(tour.itinerario);
    else itinerary = tour.itinerario;

    // Renderizado del detalle
    detailView.innerHTML = `
            <button class="back-btn" onclick="document.getElementById('tour-detail-view').style.display='none'">← Volver</button>
            <h3>${tour.titulo}</h3>
            
            <!-- MAPA ANIMADO SIMULADO -->
            <div class="animated-map-container">
                <div class="map-line"></div>
                <div class="map-ship">🚢</div>
                <p class="map-label">Ruta Interactiva</p>
            </div>

            <div class="itinerary-timeline">
                ${itinerary.map(day => `
                    <div class="timeline-item">
                        <div class="day-badge">Día ${day.dia}</div>
                        <div class="day-content">
                            <strong>${day.puerto || day.titulo}</strong>
                            <p>${day.llegada ? 'Llegada: ' + day.llegada : ''} ${day.salida ? 'Salida: ' + day.salida : ''}</p>
                            <small>${day.desc || ''}</small>
                        </div>
                    </div>
                `).join('')}
            </div>

            <button class="btn-lo-quiero" onclick="abrirModalReserva('${tour.id}', '${tour.titulo}', '${tour.precio}', '${tour.img}')">
                SOLICITAR PRESUPUESTO
            </button>
        `;
    detailView.style.display = 'block';
}

// LISTENER BOTONES FILTRADO
const btnMed = document.getElementById('btn-filter-med');
const btnOther = document.getElementById('btn-filter-others'); // Usando IDs nuevos

if (btnMed) {
    btnMed.addEventListener('click', (e) => {
        e.preventDefault();
        openPanel('mediterraneo');
    });
}
if (btnOther) {
    btnOther.addEventListener('click', (e) => {
        e.preventDefault();
        openPanel('royal');
    });
}

// Cerrar
[closeBtn, overlay].forEach(el => {
    el.addEventListener('click', closePanel);
});


window.closePanel = function () {
    document.getElementById('side-panel').classList.remove('active');
    document.getElementById('side-panel-overlay').classList.remove('active');
    document.body.style.overflow = '';
}



AOS.init({ duration: 800, once: true });

// Lógica de Filtrado de Ofertas
const filterBtns = document.querySelectorAll('.filter-btn');
const cards = document.querySelectorAll('.oferta-card');

filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // Cambiar clase activa
        filterBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        const filterValue = btn.getAttribute('data-filter');

        cards.forEach(card => {
            if (filterValue === 'all' || card.getAttribute('data-category') === filterValue) {
                card.style.display = 'block';
                setTimeout(() => { card.style.opacity = '1'; card.style.transform = 'scale(1)'; }, 10);
            } else {
                card.style.opacity = '0';
                card.style.transform = 'scale(0.8)';
                setTimeout(() => { card.style.display = 'none'; }, 300);
            }
        });
    });
});

/* =========================================
RSW STUDIO - INTERACCIONES PREMIUM 2026
========================================= */

document.addEventListener('DOMContentLoaded', () => {

    // 1. INICIALIZAR AOS (Animaciones de Scroll)
    AOS.init({
        duration: 1000,
        once: true,
        mirror: false,
        offset: 100
    });

    // 2. EFECTO PARALLAX EN EL HERO (Mouse Move)
    const hero = document.querySelector('.hero-canvas-ofertas');
    const images = document.querySelectorAll('.gallery-item');
    const bgText = document.querySelector('.canvas-bg-text');

    if (hero) {
        hero.addEventListener('mousemove', (e) => {
            const { clientX, clientY } = e;
            const xPos = (clientX / window.innerWidth - 0.5) * 40;
            const yPos = (clientY / window.innerHeight - 0.5) * 40;

            images.forEach((img, index) => {
                const speed = (index + 1) * 0.5;
                img.style.transform = `translate(${xPos * speed}px, ${yPos * speed}px)`;
            });

            if (bgText) {
                bgText.style.transform = `translate(calc(-50% + ${-xPos * 0.2}px), calc(-50% + ${-yPos * 0.2}px))`;
            }
        });
    }

    // 3. CONTADOR REAL PARA OFERTAS FLASH
    const updateTimers = () => {
        const now = new Date().getTime();
        // Ponemos una fecha objetivo (por ejemplo, 3 días desde hoy)
        const targetDate = new Date(now + (3 * 24 * 60 * 60 * 1000)).getTime();

        const timers = document.querySelectorAll('.timer-overlay');

        timers.forEach(timer => {
            if (timer.classList.contains('urgent')) return; // Saltamos los que dicen "Último día"

            const distance = targetDate - now;

            const days = Math.floor(distance / (1000 * 60 * 60 * 24));
            const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((distance % (1000 * 60)) / 1000);

            // Inyectamos el HTML de forma limpia
            timer.innerHTML = `
                <span class="time-item">${days < 10 ? '0' + days : days}<small>D</small></span>
                <span class="time-sep">:</span>
                <span class="time-item">${hours < 10 ? '0' + hours : hours}<small>H</small></span>
                <span class="time-sep">:</span>
                <span class="time-item">${minutes < 10 ? '0' + minutes : minutes}<small>M</small></span>
                <span class="time-sep">:</span>
                <span class="time-item">${seconds < 10 ? '0' + seconds : seconds}<small>S</small></span>
            `;
        });
    };

    setInterval(updateTimers, 1000);
    updateTimers();

    // 4. HEADER DINÁMICO (Cambia al hacer scroll)
    const header = document.querySelector('.main-header');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            header.classList.add('header-scrolled');
        } else {
            header.classList.remove('header-scrolled');
        }
    });

    // 5. VALIDACIÓN SUTIL DEL FORMULARIO NEWSLETTER
    const newsForm = document.querySelector('.news-form');
    if (newsForm) {
        newsForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const btn = newsForm.querySelector('button');
            const originalText = btn.innerHTML;

            btn.innerHTML = 'SOLICITANDO...';
            btn.disabled = true;

            setTimeout(() => {
                btn.style.background = '#27ae60';
                btn.innerHTML = '¡ACCESO CONCEDIDO! <i class="fas fa-check"></i>';
                newsForm.reset();
            }, 1500);
        });
    }
});

document.addEventListener('DOMContentLoaded', () => {
    if (!document.body.classList.contains('page-presupuesto')) return;

    let currentStep = 1;
    const totalSteps = 3;

    const updateUI = () => {
        // Mostrar/Ocultar Secciones
        document.querySelectorAll('.step-section').forEach(s => s.classList.remove('active'));
        document.getElementById(`step${currentStep}`).classList.add('active');

        // Actualizar Stepper Moderno
        document.querySelectorAll('.step-item').forEach((item, idx) => {
            if (idx + 1 <= currentStep) item.classList.add('active');
            else item.classList.remove('active');
        });

        // Visibilidad Botón Anterior
        const btnPrev = document.getElementById('prevBtn');
        btnPrev.style.opacity = currentStep === 1 ? '0' : '1';
        btnPrev.style.pointerEvents = currentStep === 1 ? 'none' : 'all';

        // Texto Botón Siguiente
        document.getElementById('nextBtn').innerHTML = currentStep === totalSteps
            ? 'ENVIAR SOLICITUD <i class="fas fa-crown"></i>'
            : 'SIGUIENTE PASO <i class="fas fa-arrow-right"></i>';

        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    document.getElementById('nextBtn').addEventListener('click', () => {
        if (currentStep < totalSteps) {
            currentStep++;
            updateUI();
        } else {
            handleSuccess();
        }
    });

    document.getElementById('prevBtn').addEventListener('click', () => {
        if (currentStep > 1) {
            currentStep--;
            updateUI();
        }
    });

    // Lógica Slider Presupuesto
    const budgetInput = document.getElementById('budgetInput');
    const priceLabel = document.getElementById('priceLabel');
    if (budgetInput) {
        budgetInput.addEventListener('input', (e) => {
            priceLabel.innerText = `${parseInt(e.target.value).toLocaleString()}€`;
        });
    }

    function handleSuccess() {
        document.querySelector('.presupuesto-content').innerHTML = `
            <div style="text-align:center; padding: 100px 0; animation: fadeIn 1s ease;">
                <i class="fas fa-paper-plane" style="font-size:4rem; color:var(--accent); margin-bottom:30px;"></i>
                <h1 style="font-family:var(--font-editorial); font-size:3.5rem;">Casi estamos</h1>
                <p style="color:var(--text-muted); margin-top:20px; font-size: 1.2rem;">Andrea revisará tu propuesta personalmente y te contactará.</p>
                <a href="index.html" class="btn-next" style="display:inline-block; margin-top:40px; text-decoration:none;">VOLVER AL INICIO</a>
            </div>
        `;
    }
});

/* RSW Studio - Motor de FAQ Blindado */
console.log("RSW Studio: Iniciando motor de FAQS...");

const setupFaqRSW = () => {
    const accordion = document.getElementById('rswAccordionMain');

    if (!accordion) {
        console.error("Error: No se ha encontrado el ID rswAccordionMain en el HTML.");
        return;
    }

    // Usamos delegación de eventos en el contenedor padre
    accordion.onclick = function (event) {
        const btn = event.target.closest('.faq-question');
        if (!btn) return;

        const item = btn.parentElement;
        const wasActive = item.classList.contains('active');

        // Cerramos todos
        const allItems = accordion.querySelectorAll('.faq-item');
        allItems.forEach(el => el.classList.remove('active'));

        // Si no estaba abierto, lo abrimos
        if (!wasActive) {
            item.classList.add('active');
        }
    };

    console.log("RSW Studio: Motor de FAQS activado con éxito.");
};

// Forzamos la ejecución al cargar la ventana completa
window.onload = setupFaqRSW;




// Control de apertura de menús
document.querySelectorAll('.rsw-dropdown-container, #pasajeros-wrapper').forEach(item => {
    item.addEventListener('click', function (e) {
        e.stopPropagation();
        // Cerramos otros abiertos
        document.querySelectorAll('.rsw-dropdown-menu, .index-pasajeros-dropdown').forEach(menu => {
            menu.classList.remove('active');
        });
        // Abrimos el actual
        const menu = this.querySelector('.rsw-dropdown-menu') || this.querySelector('.index-pasajeros-dropdown');
        if (menu) menu.classList.add('active');
    });
});

// Cerrar al clicar fuera
document.addEventListener('click', () => {
    document.querySelectorAll('.rsw-dropdown-menu, .index-pasajeros-dropdown').forEach(menu => {
        menu.classList.remove('active');
    });
});


// Función de simulación eliminada para usar la búsqueda real en index.html