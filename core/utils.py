import math
import networkx as nx 

def euclidean_distance(node_a, node_b, graph):
    """
    Calculates the Euclidean distance between two nodes in a graph.
    
    Parameters:
    node_a: The first node
    node_b: The second node
    graph: The graph
    
    Returns:
    The Euclidean distance between the two nodes
    """
    x1, y1 = graph.nodes[node_a].get('x', 0), graph.nodes[node_a].get('y', 0)
    x2, y2 = graph.nodes[node_b].get('x', 0), graph.nodes[node_b].get('y', 0)
    return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)

GLOBAL_ROUTING_GRAPH = None

def init_worker(nodes_dict, edges_list):
    """
    Initialisation garantie sans crash : on ne reçoit que des strings/floats primitifs.
    """
    global GLOBAL_ROUTING_GRAPH
    try:
        GLOBAL_ROUTING_GRAPH = nx.DiGraph()
        
        for node, (x, y) in nodes_dict.items():
            GLOBAL_ROUTING_GRAPH.add_node(node, x=x, y=y)
            
        for u, v, length in edges_list:
            GLOBAL_ROUTING_GRAPH.add_edge(u, v, length=length)
            
        print(f"Worker CPU initialisé avec succès ({len(nodes_dict)} noeuds)")
    except Exception as e:
        print(f"ERREUR CRITIQUE Worker Init : {e}")

def astar_worker(args):
    source, target, blocked_edges = args
    graph = GLOBAL_ROUTING_GRAPH

    if source not in graph or target not in graph:
        return []

    removed_edges = []
    for u, v in blocked_edges:
        if graph.has_edge(u, v):
            removed_edges.append((u, v, graph[u][v]['length']))
            graph.remove_edge(u, v)

    def euclidean_distance_in(u, v):
        try:
            x1, y1 = graph.nodes[u]['x'], graph.nodes[u]['y']
            x2, y2 = graph.nodes[v]['x'], graph.nodes[v]['y']
            return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        except KeyError:
            return 0.0

    try:
        route = nx.astar_path(
            graph,
            source=source,
            target=target,
            weight='length',
            heuristic=euclidean_distance_in
        )
        return route[1:] 
        
    except nx.NetworkXNoPath:
        return []
    except Exception as e:
        print(f"Erreur A* : {e}")
        return []
    finally:
        for u, v, length in removed_edges:
            graph.add_edge(u, v, length=length)