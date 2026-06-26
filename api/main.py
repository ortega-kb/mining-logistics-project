from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import logging
import shapely.wkt as wkt

from pydantic import BaseModel

# 1. On crée un modèle pour forcer FastAPI à lire le JSON (Body)
# 2. On utilise 'str' car NetworkX stocke les ID du GraphML sous forme de texte
class IncidentRequest(BaseModel):
    node_u: str = None
    node_v: str = None

# Logger
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from api.websockets import router as websocket_router, publish_positions
from simulation.model import HPCLogisticsModel

app = FastAPI()
app.include_router(websocket_router)

app.state.hpc_logisic_model = None
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)


# city coordinates dict
cities = {
    "Kolwezi": (25.49, -10.71),
    "Fungurume": (26.32, -10.62),
    "Likasi": (26.73, -10.98),
    "Lubumbashi": (27.48, -11.67),
    "Kasumbalesa": (27.80, -12.27),
    "Sakania": (28.56, -12.75)
}

# Simulates real trucks in real time
async def trucks_simulation():
    app.state.hpc_logisic_model = HPCLogisticsModel(num_agents=50, cities=cities)
    while True:
        await asyncio.to_thread(app.state.hpc_logisic_model.step)
        events = app.state.hpc_logisic_model.get_truck_positions()

        await publish_positions(events)
        await asyncio.sleep(0.2)

@app.post("/api/trigger-incident")
async def api_trigger_incident(request: IncidentRequest):
    if not app.state.hpc_logisic_model:
        return {"status": "error", "message": "Simulation non initialisée"}

    target_edge = (request.node_u, request.node_v) if (request.node_u and request.node_v) else None
    
    duration = 30
    coords = app.state.hpc_logisic_model.trigger_incident(edge=target_edge, duration_ticks=duration)
    
    if coords:
        return {"status": "ok", "coordinates": coords}
        
    return {"status": "warning", "message": "Aucun incident possible sur ce tronçon. Il est peut-être déjà coupé."}
    

@app.post("/api/spawn-truck")
async def api_spawn_truck(start_city: str = None, end_city: str = None):
    # Permet de spawn un camion manuellement via une requête POST
    truck = app.state.hpc_logisic_model.spawn_truck(start_city=start_city, end_city=end_city)
    return {"status": "ok", "truck_id": truck.truck_id}


@app.get("/api/network")
async def get_network_geojson():
    if not app.state.hpc_logisic_model:
        return {"type": "FeatureCollection", "features": []}

    G = app.state.hpc_logisic_model.G
    features = []

    for u, v, key, data in G.edges(keys=True, data=True):
        coords = []
        
        if 'geometry' in data:
            try:
                geom = data['geometry']
                if isinstance(geom, str):
                    geom = wkt.loads(geom)
                coords = list(geom.coords)
            except Exception:
                pass
        
        if not coords:
            u_node = G.nodes[u]
            v_node = G.nodes[v]
            coords = [
                [float(u_node.get('x', 0)), float(u_node.get('y', 0))],
                [float(v_node.get('x', 0)), float(v_node.get('y', 0))]
            ]

        feature = {
            "type": "Feature",
            "properties": {
                "source": u,    
                "target": v,    
                "key": key
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            }
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}

@app.on_event("startup")
async def startup():
    logger.info("Starting trucks simulation")
    asyncio.create_task(trucks_simulation())
