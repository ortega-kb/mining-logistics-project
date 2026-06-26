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

def astar_worker(args):
    graph, source, target = args

    def euclidean_distance_in(u, v):
        """
        Calculates the Euclidean distance between two nodes in a graph.
        
        Parameters:
        u: The first node
        v: The second node
        
        Returns:
        The Euclidean distance between the two nodes
        """
        try:
            x1, y1 = float(graph.nodes[u].get('x', 0)), float(graph.nodes[u].get('y', 0))
            x2, y2 = float(graph.nodes[v].get('x', 0)), float(graph.nodes[v].get('y', 0))
            return math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        except (KeyError, TypeError):
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