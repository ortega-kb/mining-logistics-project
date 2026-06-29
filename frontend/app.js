const mapBoxAccessToken = '';

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
    bearing: 0,
    antialias: true
});

map.addControl(new mapboxgl.NavigationControl(), 'top-right');

const els = {
    status: document.getElementById("ws-status"),
    total: document.getElementById("count-total"),
    moving: document.getElementById("count-moving"),
    blocked: document.getElementById("count-blocked"),
    delivered: document.getElementById("count-delivered"),
    btnIncident: document.getElementById("btn-toggle-incident-mode")
};

let truckStates = new Map();
const ANIMATION_SMOOTHNESS = 0.12;

function lerp(start, end, factor) {
    return start + (end - start) * factor;
}

function updateAnimation() {
    const features = [];
    let stats = { moving: 0, blocked: 0, delivered: 0 };

    truckStates.forEach((truck, id) => {
        truck.currentLon = lerp(truck.currentLon, truck.targetLon, ANIMATION_SMOOTHNESS);
        truck.currentLat = lerp(truck.currentLat, truck.targetLat, ANIMATION_SMOOTHNESS);

        if (truck.status === 'moving') stats.moving++;
        else if (truck.status === 'blocked' || truck.status === 'routing') stats.blocked++;
        else if (truck.status === 'delivered') stats.delivered++;

        features.push({
            type: 'Feature',
            geometry: {
                type: 'Point',
                coordinates: [truck.currentLon, truck.currentLat]
            },
            properties: {
                _id: id,
                status: truck.status,
                destination: truck.destination
            }
        });
    });

    if (map.getSource('trucks-source')) {
        map.getSource('trucks-source').setData({
            type: 'FeatureCollection',
            features: features
        });
    }

    if (els.total) els.total.textContent = truckStates.size;
    if (els.moving) els.moving.textContent = stats.moving;
    if (els.blocked) els.blocked.textContent = stats.blocked;
    if (els.delivered) els.delivered.textContent = stats.delivered;

    requestAnimationFrame(updateAnimation);
}

requestAnimationFrame(updateAnimation);

const ws = new WebSocket("ws://localhost:8080/ws/trucks");

ws.onmessage = (event) => {
    const trucksFromServer = JSON.parse(event.data);
    const activeIds = new Set();

    trucksFromServer.forEach(t => {
        activeIds.add(t._id);
        const lat = parseFloat(t.lat);
        const lon = parseFloat(t.lon);

        if (!truckStates.has(t._id)) {
            truckStates.set(t._id, {
                currentLon: lon, currentLat: lat,
                targetLon: lon, targetLat: lat,
                status: t.status, destination: t.destination
            });
        } else {
            const state = truckStates.get(t._id);
            state.targetLon = lon;
            state.targetLat = lat;
            state.status = t.status;
            state.destination = t.destination;
        }
    });

    for (let id of truckStates.keys()) {
        if (!activeIds.has(id)) truckStates.delete(id);
    }
};

ws.onopen = () => { els.status.textContent = "Connected"; els.status.style.color = "#10b981"; };
ws.onclose = () => { els.status.textContent = "Disconnected"; els.status.style.color = "#ef4444"; };

map.on('load', () => {
    map.addSource('trucks-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] }
    });

    map.addLayer({
        id: 'trucks-layer',
        type: 'circle',
        source: 'trucks-source',
        paint: {
            'circle-radius': [
                'interpolate', ['linear'], ['zoom'],
                5, 4,
                10, 8,
                15, 12
            ],
            'circle-color': [
                'match', ['get', 'status'],
                'moving', '#10b981',
                'blocked', '#ef4444',
                'routing', '#f59e0b',
                'delivered', '#3b82f6',
                '#94a3b8'
            ],
            'circle-opacity': 1,
            'circle-stroke-width': 1.5,
            'circle-stroke-color': '#ffffff',
            'circle-stroke-opacity': 1
        }
    });

    map.addSource('mining-network-source', {
        'type': 'geojson',
        'data': 'http://localhost:8080/api/network'
    });

    map.addLayer({
        'id': 'mining-road-layer',
        'type': 'line',
        'source': 'mining-network-source',
        'paint': {
            'line-color': '#475569',
            'line-width': 2,
            'line-opacity': 0.3
        }
    });

    map.addLayer({
        'id': 'mining-road-click-layer',
        'type': 'line',
        'source': 'mining-network-source',
        'paint': { 'line-width': 15, 'line-opacity': 0 }
    });

    map.on('click', 'trucks-layer', (e) => {
        const props = e.features[0].properties;
        new mapboxgl.Popup({ offset: 10, closeButton: false })
            .setLngLat(e.features[0].geometry.coordinates)
            .setHTML(`<b>${props._id}</b><br>Vers: ${props.destination}<br>Etat: ${props.status}`)
            .addTo(map);
    });

    map.on('mouseenter', 'trucks-layer', () => map.getCanvas().style.cursor = 'pointer');
    map.on('mouseleave', 'trucks-layer', () => map.getCanvas().style.cursor = '');
});


els.btnIncident.addEventListener('click', () => {
    isIncidentMode = !isIncidentMode;
    els.btnIncident.classList.toggle('active', isIncidentMode);
    els.btnIncident.textContent = isIncidentMode ? "Mode Incident: CLIQUEZ SUR UNE ROUTE" : "Mode Incident: OFF";
});

map.on('click', 'mining-road-click-layer', (e) => {
    if (!isIncidentMode) return;
    const f = e.features[0];
    triggerIncidentAPI(f.properties.source, f.properties.target);
});

async function triggerIncidentAPI(u, v) {
    try {
        const response = await fetch('http://localhost:8080/api/trigger-incident', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ node_u: u, node_v: v })
        });
        const data = await response.json();
        if (data.status === 'ok') displayDamagedRoad(data.coordinates);
    } catch (err) { console.error(err); }
    finally {
        isIncidentMode = false;
        els.btnIncident.classList.remove('active');
        els.btnIncident.textContent = "Mode Incident: OFF";
    }
}

function displayDamagedRoad(coords) {
    const sid = 'damaged-road-source', lid = 'damaged-road-layer';
    if (map.getLayer(lid)) map.removeLayer(lid);
    if (map.getSource(sid)) map.removeSource(sid);
    map.addSource(sid, { 'type': 'geojson', 'data': { 'type': 'Feature', 'geometry': { 'type': 'LineString', 'coordinates': coords } } });
    map.addLayer({ 'id': lid, 'type': 'line', 'source': sid, 'paint': { 'line-color': '#ef4444', 'line-width': 4, 'line-dasharray': [2, 1] } });
}
