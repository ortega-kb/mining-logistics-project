from simulation.agents import TruckAgent, TruckStatus
import multiprocessing as mp
from collections import Counter
from core.utils import astar_worker
import logging
import mesa 
import random
import networkx as nx


class HPCLogisticsModel(mesa.Model):
    def __init__(self, num_agents, cities: dict, graph_path="data/mining_network.graphml"):
        super().__init__()

        self.num_agents = num_agents
        self.G = nx.read_graphml(graph_path)

        for node, data in self.G.nodes(data=True):
            try:
                data['x'] = float(data.get('x', 0.0))
                data['y'] = float(data.get('y', 0.0))
            except (ValueError, TypeError):
                data['x'] = 0.0
                data['y'] = 0.0

        for u, v, key, data in self.G.edges(keys=True, data=True):
            try:
                data['length'] = float(data.get('length', 1.0))
            except (ValueError, TypeError):
                data['length'] = 1.0

        self.grid = mesa.space.NetworkGrid(self.G)    

        self.city_nodes = {}
        for city_name, coords in cities.items():
            self.city_nodes[city_name] = self.find_nearest_node(target_lon=coords[0], target_lat=coords[1])

        self.city_names = list(self.city_nodes.keys())  
        self.incident_timer = 0
        self.damaged_edges = []

        for i in range(self.num_agents):
            self.spawn_truck(start_city="Lubumbashi", end_city="Kolwezi")
    
    def spawn_truck(self, start_city=None, end_city=None):
        """
        Permet de créer un camion spécifique ou aléatoire.
        """
        if not start_city or start_city not in self.city_nodes:
            start_city = random.choice(self.city_names)
        if not end_city or end_city not in self.city_nodes or end_city == start_city:
            end_city = random.choice([c for c in self.city_names if c != start_city])

        truck_id = f"TRK-{len(self.agents)+1:04d}"
        departure_node = self.city_nodes[start_city]
        destination_node = self.city_nodes[end_city]
        
        agent = TruckAgent(self, truck_id=truck_id, destination_node=destination_node, destination_city=end_city)
        self.grid.place_agent(agent=agent, node_id=departure_node)
        return agent

    def step(self):
        active_trucks = [a for a in self.agents if a.status != TruckStatus.DELIVERED]
        
        if not active_trucks:
            if self.running:
                logging.info("Tous les camions sont arrivés. Mise en veille de la simulation (IDLE).")
                self.running = False
            return

        if self.incident_timer > 0:
            self.incident_timer -= 1
            if self.incident_timer == 0:
                self.resolve_incident()

        agents_on_hold = [a for a in self.agents if a.status == TruckStatus.ROUTING]
        MAX_ROUTES_PER_TICK = 5
        agents_to_process = agents_on_hold[:MAX_ROUTES_PER_TICK]

        if agents_to_process: 
            logging.info(f"Calcul des routes A* pour {len(agents_to_process)} camions (En attente: {len(agents_on_hold) - len(agents_to_process)})")
            tasks = [(self.G, a.pos, a.destination_node) for a in agents_to_process]

            results = [astar_worker(task) for task in tasks]

            for agent, route in zip(agents_to_process, results):
                if route is None or len(route) == 0:
                    agent.status = TruckStatus.BLOCKED
                else:
                    agent.route = route
                    agent.status = TruckStatus.MOVING
        
        self.agents.shuffle_do("step")


    def find_nearest_node(self, target_lon, target_lat):
        nearest_node = None
        min_distance = float('inf')

        for node, data in self.G.nodes(data=True):
            lon = float(data.get('x', 0.0))
            lat = float(data.get('y', 0.0))

            dist = ((lon - target_lon) ** 2 + (lat - target_lat) ** 2)

            if dist < min_distance:
                min_distance = dist
                nearest_node = node

        return nearest_node
    
    def trigger_incident(self, edge=None, duration_ticks=30):
        """
        Si 'edge' est fourni (tuple u,v), l'incident est ciblé.
        Sinon, l'incident est déclenché sur le tronçon le plus fréquenté.
        """
        if edge:
            node_u, node_v = edge
            # Sécurité: Vérifier l'existence dans les deux sens au cas où le graphe est dirigé différemment
            if not self.G.has_edge(node_u, node_v) and not self.G.has_edge(node_v, node_u):
                return None
        else:
            traffic = Counter()
            for agent in self.agents:
                if agent.route:
                    traffic[(agent.pos, agent.route[0])] += 1
            if not traffic: return None
            (node_u, node_v), _ = traffic.most_common(1)[0]

        # Application du blocage
        self.damaged_edges = []
        for u, v in [(node_u, node_v), (node_v, node_u)]:
            if self.G.has_edge(u, v):
                for k in list(self.G[u][v].keys()):
                    data = dict(self.G[u][v][k])
                    self.damaged_edges.append((u, v, k, data))
                    self.G.remove_edge(u, v, key=k)

        self.incident_timer = duration_ticks
        
        # Reroutage dynamique des agents affectés
        for agent in self.agents:
            if agent.route:
                future_path = [agent.pos] + agent.route
                if (node_u, node_v) in zip(future_path[:-1], future_path[1:]) or \
                   (node_v, node_u) in zip(future_path[:-1], future_path[1:]):
                    agent.route = [] 
                    agent.status = TruckStatus.ROUTING
        
        try:
            coords = [
                [float(self.G.nodes[node_u]['x']), float(self.G.nodes[node_u]['y'])],
                [float(self.G.nodes[node_v]['x']), float(self.G.nodes[node_v]['y'])]
            ]
            return coords
        except KeyError as e:
            logging.error(f"Coordonnées manquantes sur les noeuds de l'incident : {e}")
            return None

    def resolve_incident(self):
        logging.info("INCIDENT RÉSOLU : Réouverture de la route. Réveil des camions bloqués...")
        
        for u, v, k, data in self.damaged_edges:
            self.G.add_edge(u, v, key=k, **data)
            
        self.damaged_edges = []

        for agent in self.agents:
            if agent.status == TruckStatus.BLOCKED:
                agent.status = TruckStatus.ROUTING
        
 
    def get_truck_positions(self):
        positions = []
        for agent in self.agents:
            if hasattr(agent, 'actual_coordinates') and agent.actual_coordinates:
                lon, lat = agent.actual_coordinates
            else:
                node_data = self.G.nodes[agent.pos]
                lat = float(node_data.get('y', 0.0))
                lon = float(node_data.get('x', 0.0))
            
            positions.append({
                "_id": agent.truck_id,
                "lat": lat,
                "lon": lon,
                "status": agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
                "destination": agent.destination_city
            })

        return positions




