from core.metrics import get_active_agents, get_compute_time, get_cpu_usage, get_ram_usage_mb, get_routing_queue, get_routes_per_sec
from simulation.agents import TruckAgent, TruckStatus
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
from core.utils import astar_worker, init_worker
from mesa.datacollection import DataCollector
import logging
import mesa 
import random
import networkx as nx
import psutil 
import time
import json 

class HPCLogisticsModel(mesa.Model):
    def __init__(self, num_agents, cities: dict, graph_path="data/mining_network.graphml"):
        super().__init__()

        self.num_agents = num_agents
        self.G = nx.read_graphml(graph_path)

        self.start_wall_time = time.time() 
        self.total_simulation_duration = 0.0
        self.last_compute_time = 0.0        
        self.last_routes_per_sec = 0.0
        
        psutil.cpu_percent(interval=None)

        for node, data in self.G.nodes(data=True):
            data['x'] = float(data.get('x', 0.0))
            data['y'] = float(data.get('y', 0.0))

        for u, v, key, data in self.G.edges(keys=True, data=True):
            data['length'] = float(data.get('length', 1.0))

        # On extrait un dictionnaire { "node_id": (x, y) }
        nodes_dict = {
            str(n): (float(d.get('x', 0.0)), float(d.get('y', 0.0))) 
            for n, d in self.G.nodes(data=True)
        }
        
        # On extrait une liste de tuples (noeud_dep, noeud_arr, longueur)
        edges_list = []
        for u, v, key, data in self.G.edges(keys=True, data=True):
            edges_list.append((str(u), str(v), float(data.get('length', 1.0))))


        total_cpus = mp.cpu_count() 
        self.num_cpus = max(1, total_cpus - 1)

        ctx = mp.get_context('spawn')
        self.process_pool = ProcessPoolExecutor(
            max_workers=self.num_cpus,
            initializer=init_worker,
            mp_context=ctx,
            initargs=(nodes_dict, edges_list)
        )      

        logging.info(f"Initialisation du pool de calcul avec {self.num_cpus} CPUs virtuels/physiques.")

        self.datacollector = DataCollector(
            model_reporters={
                "Active_Agents": get_active_agents,
                "Compute_Time_sec": get_compute_time,
                "CPU_Usage_percent": get_cpu_usage,
                "RAM_Usage_MB": get_ram_usage_mb,       
                "Routing_Queue_Size": get_routing_queue,
                "Routes_Per_Sec": get_routes_per_sec 
            }
        )

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
                self.total_simulation_duration = time.time() - self.start_wall_time
                logging.info("Tous les camions sont arrivés. Mise en veille de la simulation (IDLE).")
                self.running = False
                self.export_metrics_to_csv()
                self.process_pool.shutdown(wait=True)
            return

        if self.incident_timer > 0:
            self.incident_timer -= 1
            if self.incident_timer == 0:
                self.resolve_incident()

        agents_to_process = [a for a in self.agents if a.status == TruckStatus.ROUTING]

        self.last_routes_per_sec = 0.0  
        self.last_compute_time = 0.0

        if agents_to_process: 
            logging.info(f"Calcul en parallèle des routes A* pour {len(agents_to_process)} camions sur {self.num_cpus} cœurs...")            
            blocked_edges = [(str(u), str(v)) for u, v, k, data in self.damaged_edges]
            tasks = [(str(a.pos), str(a.destination_node), blocked_edges) for a in agents_to_process]
            start_time = time.perf_counter()

            results = list(self.process_pool.map(astar_worker, tasks, chunksize=10, timeout=15.0))
            self.last_compute_time = time.perf_counter() - start_time

            if self.last_compute_time > 0:
                self.last_routes_per_sec = len(tasks) / self.last_compute_time

            for agent, route in zip(agents_to_process, results):
                if route is None or len(route) == 0:
                    agent.status = TruckStatus.BLOCKED
                else:
                    agent.route = route
                    agent.status = TruckStatus.MOVING
        
        self.agents.shuffle_do("step")
        self.datacollector.collect(self)

    def export_metrics_to_csv(self, is_hpc = False):
        df = self.datacollector.get_model_vars_dataframe()
        filename = f"data/metrics/metrics_agents_{self.num_agents}.csv"
        summary_file = f"data/metrics/metrics_summary_agents_{self.num_agents}.json"
        if is_hpc:
            filename = f"data/metrics/metrics_agents_{self.num_agents}_hpc.csv"
            summary_file = f"data/metrics/metrics_summary_agents_{self.num_agents}_hpc.json"
        df.to_csv(filename, index_label="Tick")

        summary = {
            "Num_Agents": self.num_agents,
            "Total_Duration_Sec": round(self.total_simulation_duration, 2),
            "Final_Tick": len(df),
            
            "Avg_Routes_Per_Sec": round(df["Routes_Per_Sec"].mean(), 2),
            "Peak_Routes_Per_Sec": round(df["Routes_Per_Sec"].max(), 2),
            
            "Avg_Cpu_Usage": round(df["CPU_Usage_percent"].mean(), 2),
            "Compute_Time_Stability_Std": round(df["Compute_Time_sec"].std(), 4),
            
            "Max_Queue_Size": int(df["Routing_Queue_Size"].max())
        }

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=4)

        logging.info(f"Summary and metrics exported to {filename} and {summary_file}")

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




