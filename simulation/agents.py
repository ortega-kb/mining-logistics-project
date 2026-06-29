import mesa
import random
from enum import Enum
import shapely.wkt as wkt

class TruckStatus(Enum):
    IDLE = "idle"
    MOVING = "moving"
    DELIVERED = "delivered"
    BLOCKED = "blocked"
    ROUTING = "routing"

class TruckAgent(mesa.Agent):
    def __init__(self, model, truck_id, destination_node, destination_city):
        super().__init__(model)
        self.truck_id = truck_id
        self.destination_node = destination_node
        self.destination_city = destination_city
        self.status = TruckStatus.IDLE
        self.route = []
        self.delay = random.randint(0, 10)
        self.visual_sub_itinerary = []
        self.actual_coordinates = None
        
    def step(self):
        # 1. Attente au départ
        if self.delay > 0:
            self.delay -= 1
            return

        # 2. Si la route est bloquée sans déviation possible, on attend la dépanneuse
        if self.status == TruckStatus.BLOCKED:
            return

        # 3. Attente du calcul GPS
        if self.status == TruckStatus.ROUTING:
            return 

        # 4. Arrivée à destination
        if self.pos == self.destination_node:
            self.status = TruckStatus.DELIVERED
            self.route = []
            return 

        # 5. Demande de recalcul (ex: le GPS vient d'effacer la route à cause d'un incident)
        if not self.route: 
            self.status = TruckStatus.ROUTING
            return 

        self.status = TruckStatus.MOVING

        # 6. Avancée visuelle progressive vers le prochain carrefour
        if self.visual_sub_itinerary:
            self.actual_coordinates = self.visual_sub_itinerary.pop(0)
            return 

        # 7. Franchissement d'un carrefour : on prend le tronçon suivant
        if self.route:
            next_node = self.route.pop(0)
            edge_data = self.model.G.get_edge_data(self.pos, next_node)

            if edge_data and 0 in edge_data and 'geometry' in edge_data[0]:
                geom = edge_data[0]['geometry']
                try:
                    if isinstance(geom, str):
                        geom = wkt.loads(geom)
                    coords = list(geom.coords)
                    self.visual_sub_itinerary = coords[1:]
                except Exception:
                    self.visual_sub_itinerary = []
            
            # Déplacement logique dans Mesa
            self.model.grid.move_agent(self, next_node)
            
            if not self.actual_coordinates and not self.visual_sub_itinerary:
                node_data = self.model.G.nodes[self.pos]
                self.actual_coordinates = (float(node_data['x']), float(node_data['y']))