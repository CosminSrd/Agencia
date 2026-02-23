
// --- SERVICIOS EXTRA (MALETAS) ---
let serviciosActuales = [];
window.serviciosSeleccionados = new Set(); // IDs de servicios seleccionados
window.preciosServicios = {}; // Mapa ID -> Precio

function esServicioEquipaje(service) {
    const tipo = String(service?.type || '').toLowerCase();
    return tipo.includes('baggage') || tipo.includes('bag') || tipo.includes('luggage');
}

function getServiciosFallbackDesdeVueloSeleccionado(offerId) {
    const candidatos = [];
    if (typeof vueloIdaSeleccionado !== 'undefined' && vueloIdaSeleccionado) {
        candidatos.push(vueloIdaSeleccionado);
    }
    if (typeof vueloVueltaSeleccionado !== 'undefined' && vueloVueltaSeleccionado) {
        candidatos.push(vueloVueltaSeleccionado);
    }

    const vuelo = candidatos.find(v => v && v.id === offerId);
    return (vuelo && Array.isArray(vuelo.available_services)) ? vuelo.available_services : [];
}

async function cargarServiciosExtra(offerId) {
    const container = document.getElementById('contenedor-servicios-extra');
    if (!container) return;

    container.innerHTML = '<div class="cargando-spinner">↻ Buscando opciones de equipaje...</div>';
    serviciosActuales = [];
    window.serviciosSeleccionados.clear();
    window.preciosServicios = {};
    if (typeof extraMaletas !== 'undefined') extraMaletas = 0;
    if (typeof actualizarPrecioUI === 'function') actualizarPrecioUI();

    try {
        const res = await fetch(`/api/vuelos/detalles/${offerId}`);
        const data = await res.json();

        if (data.success && data.data) {
            serviciosActuales = data.data.available_services || [];
            if (!serviciosActuales.length) {
                serviciosActuales = getServiciosFallbackDesdeVueloSeleccionado(offerId);
            }
            renderizarServicios(serviciosActuales);
        } else {
            serviciosActuales = getServiciosFallbackDesdeVueloSeleccionado(offerId);
            renderizarServicios(serviciosActuales);
        }
    } catch (e) {
        console.error("Error cargando servicios:", e);
        serviciosActuales = getServiciosFallbackDesdeVueloSeleccionado(offerId);
        renderizarServicios(serviciosActuales);
    }
}

function renderizarServicios(services) {
    const container = document.getElementById('contenedor-servicios-extra');
    const bags = (services || []).filter(esServicioEquipaje);

    let html = '';

    // --- Maletas ---
    if (bags.length > 0) {
        html += '<h5 style="margin: 10px 0; color:#475569; font-size: 0.95rem;">Selecciona equipaje extra (click para añadir/quitar):</h5>';
        html += '<div class="service-grid">';

        bags.forEach(bag => {
            const precio = parseFloat(bag.total_amount);
            window.preciosServicios[bag.id] = precio;

            let desc = 'Maleta Extra';
            if (bag.metadata && bag.metadata.maximum_weight_kg) {
                desc = `${bag.metadata.maximum_weight_kg}kg`;
            }

            // Identificar pasajero
            let paxLabel = '';
            if (bag.passenger_ids && bag.passenger_ids.length > 0 && typeof vueloIdaSeleccionado !== 'undefined') {
                const paxIndex = vueloIdaSeleccionado.passengers.findIndex(p => p.id === bag.passenger_ids[0]);
                if (paxIndex >= 0) {
                    const tipo = vueloIdaSeleccionado.passengers[paxIndex].type;
                    const num = paxIndex + 1;
                    const tipoStr = tipo === 'adult' ? 'Adulto' : (tipo === 'child' ? 'Niño' : 'Bebé');
                    paxLabel = `<div style="font-size:0.75rem; color:#6366f1; font-weight:600; margin-bottom:4px;">👤 Pasajero ${num} (${tipoStr})</div>`;
                }
            }

            const isSelected = window.serviciosSeleccionados.has(bag.id) ? 'selected' : '';

            html += `
            <div class="service-card ${isSelected}" onclick="toggleServicio(this, '${bag.id}')">
                ${paxLabel}
                <div style="font-size:1.5rem;">🧳</div>
                <span style="font-size:0.85rem;">${desc}</span>
                <span class="service-price">+${precio.toFixed(2)}€</span>
            </div>`;
        });
        html += '</div>';
    } else {
        html += `
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:12px; margin-bottom:15px; color:#64748b; font-size:0.9rem;">
            <div style="font-weight:700; color:#334155; margin-bottom:6px;">🧳 Equipaje extra no disponible ahora</div>
            <div>Esta aerolínea o tarifa no ofrece precompra de maletas en este momento.</div>
            <div style="margin-top:4px; font-size:0.85rem;">Podrás añadir equipaje durante el check-in o en la web de la aerolínea, si lo permite.</div>
        </div>`;
    }

    // --- Asientos ---
    html += `
    <div style="margin-top: 20px; padding-top: 15px; border-top: 1px dashed #e2e8f0; display:flex; justify-content:space-between; align-items:center;">
            <div>
            <h4 style="margin:0; font-size:1rem; color:#1e293b;">Asientos</h4>
            <p style="margin:2px 0 0 0; font-size:0.8rem; color:#64748b;">Elige tu lugar en el avión</p>
            </div>
            <button id="btn-open-seats" type="button" onclick="abrirSeleccionAsientos()" 
            style="padding: 8px 16px; border: 1px solid #e2e8f0; background: white; border-radius: 6px; cursor: pointer; font-size: 0.9rem; transition:all 0.2s; color:#1e293b; font-weight:600;">
            💺 Seleccionar Asientos
            </button>
    </div>
`;

    container.innerHTML = html;
}

function toggleServicio(card, serviceId) {
    if (window.serviciosSeleccionados.has(serviceId)) {
        window.serviciosSeleccionados.delete(serviceId);
        card.classList.remove('selected');
    } else {
        window.serviciosSeleccionados.add(serviceId);
        card.classList.add('selected');
    }

    // Recalcular total maletas
    let totalMaletas = 0;
    window.serviciosSeleccionados.forEach(id => {
        totalMaletas += (window.preciosServicios[id] || 0);
    });

    if (typeof extraMaletas !== 'undefined') extraMaletas = totalMaletas;
    if (typeof actualizarPrecioUI === 'function') actualizarPrecioUI();
}
