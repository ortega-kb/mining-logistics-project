import os
import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

os.makedirs("data/cache", exist_ok=True)

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['SF Pro Display', 'Neue Haas Grotesk', 'Helvetica', 'Lato', 'Arial']

ox.settings.cache_folder = "data/cache"
ox.settings.log_console = True  
ox.settings.use_cache = True

print("Starting the extraction of the mining network...")

# Approximate coordinates to cover the mining corridor
north = -10.50
south = -13.00
east = 28.60
west = 25.20

road_filter = (
    '["highway"~"trunk|primary|secondary|tertiary"]'
)

try:
    mining_graph = ox.graph_from_bbox(
            bbox=(west, south, east, north),
            network_type='drive', 
            custom_filter=road_filter, 
            simplify=True
    )   

    print("Extraction successful!")
    print(f"Number of nodes (intersections): {len(mining_graph.nodes)}")
    print(f"Number of edges (road segments): {len(mining_graph.edges)}")

    mining_graph = ox.truncate.largest_component(mining_graph, strongly=True)
    print(f"After cleaning, number of nodes: {len(mining_graph.nodes)}")

    print("Standardizing edge lengths for HPC compatibility...")
    for u, v, key, data in mining_graph.edges(keys=True, data=True):
        if 'length' in data:
            valeur = data['length']
            if isinstance(valeur, list):
                data['length'] = float(sum(valeur))
            elif isinstance(valeur, str) and valeur.startswith('['):
                try:
                    liste_longueurs = ast.literal_eval(valeur)
                    data['length'] = float(sum(liste_longueurs))
                except:
                    data['length'] = 1.0
            elif isinstance(valeur, str):
                try:
                    data['length'] = float(valeur)
                except:
                    data['length'] = 1.0
            else:
                data['length'] = float(valeur)
        else:
            data['length'] = 1.0

    graphml_path = "data/mining_network.graphml"
    ox.save_graphml(mining_graph, filepath=graphml_path)
    print(f"Graph successfully saved to '{graphml_path}' for fast loading!")

    # Graph visualization without labels
    fig, ax = ox.plot_graph(
        mining_graph, 
        node_size=0,         
        edge_linewidth=0.25, 
        edge_color="#333333", 
        bgcolor="white",
        show=False, 
        close=False
    )

    output_filename = "fig/mining_network.png"
    plt.savefig(output_filename, bbox_inches="tight", dpi=300)
    print(f"Network plot saved successfully as '{output_filename}'")
    plt.close(fig)

    # Graph visualization with main cities
    fig, ax = ox.plot_graph(
        mining_graph, 
        node_size=0, 
        edge_linewidth=0.25, 
        edge_color="#333333", 
        bgcolor="white",
        show=False, 
        close=False
    )
    
    cities = {
        "Kolwezi": (25.49, -10.71),
        "Fungurume": (26.32, -10.62),
        "Likasi": (26.73, -10.98),
        "Lubumbashi": (27.48, -11.67),
        "Kasumbalesa": (27.80, -12.27),
        "Sakania": (28.56, -12.75)
    }
    
    for name, (lon, lat) in cities.items():
        ax.scatter(lon, lat, color="#d9534f", edgecolor="black", s=10, zorder=0)
        ax.text(lon + 0.03, lat - 0.02, name, fontsize=5, fontweight="bold", 
                color="#222222", zorder=6, 
                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', boxstyle='round,pad=0.2'))

    output_filename_labeled = "fig/mining_network_labeled.png"
    plt.savefig(output_filename_labeled, bbox_inches="tight", dpi=300)
    print(f"Labeled network plot saved successfully as '{output_filename_labeled}'")
    plt.close(fig)

except Exception as e:
    raise Exception(f"An error occurred during extraction of the mining network: {e}") 