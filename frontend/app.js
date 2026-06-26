// Mapbox
const mapBoxAccessToken = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN;

const corridorBounds = [
    [23.70, -15.50],
    [30.10, -8.00]
];

let isIncidentMode = false;

const map = new mapboxgl.Map({
    accessToken: mapBoxAccessToken,
    container: 'map',
    style: 'mapbox://styles/mapbox/navigation-day-v1',
    bounds: corridorBounds,
    maxBounds: corridorBounds,
    fitBoundsOptions: { padding: 20 },
    center: [26.50, -11.50],
    pitch: 0,
    bearing: 0
});

map.addControl(new mapboxgl.NavigationControl({ showCompass: true, showZoom: true }), 'top-right');

// WebSockets & Elements
const ws = new WebSocket("ws://localhost:8000/ws/trucks");
const els = {
    status: document.getElementById("ws-status"),
    total: document.getElementById("count-total"),
    moving: document.getElementById("count-moving"),
    blocked: document.getElementById("count-blocked"),
    delivered: document.getElementById("count-delivered"),
    btnIncident: document.getElementById("btn-toggle-incident-mode")
};

const activeTrucks = {};

ws.onopen = () => {
    els.status.textContent = "Connected";
    els.status.style.color = "#10b981";
};

ws.onclose = () => {
    els.status.textContent = "Disconnected";
    els.status.style.color = "#ef4444";
};

ws.onmessage = (event) => updateTruckMarkers(JSON.parse(event.data));

function updateTruckMarkers(trucks) {
    let stats = { moving: 0, blocked: 0, delivered: 0 };

    trucks.forEach(truck => {
        const truckId = truck._id;
        const truckPos = [truck.lon, truck.lat];

        // Stats
        if (truck.status === 'moving') stats.moving++;
        else if (truck.status === 'routing' || truck.status === 'blocked') stats.blocked++;
        else if (truck.status === 'delivered') stats.delivered++;

        const popupHTML = `
            <div class="popup-header"><strong>${truckId}</strong></div>
            <div class="popup-row"><span>To:</span> <span>${truck.destination}</span></div>
            <div class="popup-row"><span>Status:</span> <span style="text-transform: capitalize;">${truck.status}</span></div>
        `;

        if (activeTrucks[truckId]) {
            activeTrucks[truckId].setLngLat(truckPos);
            activeTrucks[truckId].getPopup().setHTML(popupHTML);
        } else {
            const el = document.createElement('div');
            el.className = 'truck-marker';
            // Assure-toi d'avoir du CSS pour .truck-marker (ex: width:12px, height:12px, background:blue, border-radius:50%)

            activeTrucks[truckId] = new mapboxgl.Marker(el)
                .setLngLat(truckPos)
                .setPopup(new mapboxgl.Popup({ offset: 15 }).setHTML(popupHTML))
                .addTo(map);
        }
    });

    els.total.textContent = trucks.length;
    els.moving.textContent = stats.moving;
    els.blocked.textContent = stats.blocked;
    els.delivered.textContent = stats.delivered;
}

els.btnIncident.addEventListener('click', () => {
    isIncidentMode = !isIncidentMode;
    els.btnIncident.classList.toggle('active', isIncidentMode);
    els.btnIncident.textContent = isIncidentMode ? "Mode Incident: CLICK ON A ROAD" : "Mode Incident: OFF";
    map.getCanvas().style.cursor = isIncidentMode ? 'crosshair' : '';
});

map.on('load', () => {
    // Trouver la couche d'étiquettes pour glisser le graphe en dessous (évite la superposition)
    const layers = map.getStyle().layers;
    let firstSymbolId;
    for (const layer of layers) {
        if (layer.type === 'symbol') {
            firstSymbolId = layer.id;
            break;
        }
    }

    map.addSource('mining-network-source', {
        'type': 'geojson',
        'data': 'http://localhost:8000/api/network'
    });

    // 1. Couche visible professionnelle (semi-transparente)
    map.addLayer({
        'id': 'mining-road-layer',
        'type': 'line',
        'source': 'mining-network-source',
        'paint': {
            'line-color': '#3b82f6',
            'line-width': 3,
            'line-opacity': 0.5
        }
    }, firstSymbolId);

    // 2. Couche invisible épaisse pour faciliter le clic (hitbox)
    map.addLayer({
        'id': 'mining-road-click-layer',
        'type': 'line',
        'source': 'mining-network-source',
        'paint': {
            'line-width': 15,
            'line-opacity': 0
        }
    }, firstSymbolId);

    // Événements sur la hitbox
    map.on('click', 'mining-road-click-layer', (e) => {
        if (!isIncidentMode) return;

        const feature = e.features[0];
        const nodeU = feature.properties.source;
        const nodeV = feature.properties.target;

        if (nodeU && nodeV) {
            triggerIncidentAPI(nodeU, nodeV);
        }
    });

    map.on('mouseenter', 'mining-road-click-layer', () => {
        if (isIncidentMode) map.getCanvas().style.cursor = 'pointer';
    });

    map.on('mouseleave', 'mining-road-click-layer', () => {
        if (isIncidentMode) map.getCanvas().style.cursor = 'crosshair';
    });
});

async function triggerIncidentAPI(u, v) {
    try {
        const response = await fetch('http://localhost:8000/api/trigger-incident', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_u: u, node_v: v })
        });

        const data = await response.json();

        if (data.status === 'ok') {
            displayDamagedRoad(data.coordinates);
        } else {
            console.warn(data.message);
        }
    } catch (err) {
        console.error("Erreur API incident:", err);
    } finally {
        isIncidentMode = false;
        els.btnIncident.classList.remove('active');
        els.btnIncident.textContent = "Mode Incident: OFF";
        map.getCanvas().style.cursor = '';
    }
}

function displayDamagedRoad(coords) {
    const sourceId = 'damaged-road-source';
    const layerId = 'damaged-road-layer';

    if (map.getLayer(layerId)) map.removeLayer(layerId);
    if (map.getSource(sourceId)) map.removeSource(sourceId);

    map.addSource(sourceId, {
        'type': 'geojson',
        'data': { 'type': 'Feature', 'geometry': { 'type': 'LineString', 'coordinates': coords } }
    });

    // Couche visuelle d'alerte (rouge clignotant / pointillé)
    map.addLayer({
        'id': layerId,
        'type': 'line',
        'source': sourceId,
        'paint': {
            'line-color': '#ef4444',
            'line-width': 6,
            'line-dasharray': [2, 2]
        }
    });
}