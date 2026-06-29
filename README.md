# 🚛 Simulateur de Logistique Minière (HPC)

Ce projet est une application de simulation haute performance (HPC) de la logistique minière. Il modélise et visualise les déplacements de camions (agents) entre différentes villes minières clés de la République Démocratique du Congo (RDC) telles que Kolwezi, Lubumbashi, Likasi, etc., en utilisant un réseau routier réel extrait d'OpenStreetMap.

La simulation est basée sur **Mesa** (Agent-based modeling) et utilise le calcul parallèle (`multiprocessing`) pour optimiser la recherche de chemin (A* routing) sur le réseau routier. Elle est exposée via une API **FastAPI** et visualisée en temps réel sur une interface web.

## 📂 Structure du projet

*   **`api/`** : Contient le backend FastAPI (`main.py`) qui gère la simulation, les WebSockets pour la diffusion en temps réel des positions des camions, et les endpoints de contrôle (ajout de camions, déclenchement d'incidents).
*   **`core/`** : 
    *   `extraction.py` : Script d'extraction du réseau routier depuis OpenStreetMap avec `osmnx` (sauvegardé en `.graphml`).
    *   `metrics.py` et `utils.py` : Outils de collecte de métriques système (CPU, RAM, temps de calcul) et fonctions utilitaires pour le routage.
*   **`simulation/`** : Cœur de la simulation Mesa.
    *   `model.py` : `HPCLogisticsModel`, le modèle principal qui gère le pool de processus (HPC) et orchestre les étapes de simulation.
    *   `agents.py` : Définition de l'agent `TruckAgent` et de ses états (ROUTING, MOVING, BLOCKED, DELIVERED).
*   **`frontend/`** : Interface utilisateur (HTML/CSS/JS) qui se connecte au backend via WebSockets pour afficher la carte interactive et le trafic des camions.
*   **`data/`** : Contient les données générées comme le réseau extrait (`mining_network.graphml`) et les fichiers de métriques (`.csv`, `.json`).
*   **`fig/`** : Dossier pour les figures et rendus visuels du réseau générés par matplotlib/osmnx.

## 🚀 Fonctionnalités principales

*   **Simulation Multi-Agents (ABM)** : Modélisation du trafic de centaines de camions simultanément.
*   **Routage Haute Performance (HPC)** : Utilisation d'un pool de processus (`ProcessPoolExecutor`) pour distribuer les calculs de l'algorithme A* sur plusieurs cœurs CPU.
*   **Réseau Routier Réel** : Données extraites d'OpenStreetMap via `osmnx` (filtrées pour les véhicules).
*   **Suivi en Temps Réel** : Serveur WebSocket FastAPI diffusant la position exacte de chaque camion au frontend.
*   **Gestion des Incidents** : Capacité à simuler des routes bloquées (incidents) en temps réel, forçant les camions à recalculer dynamiquement leur itinéraire.
*   **Métriques et Télémétrie** : Collecte des performances de simulation (Routes/sec, utilisation CPU/RAM).

## 🛠 Prérequis et Installation

1.  **Environnement Python** : Assurez-vous d'avoir Python installé et de préférence un environnement virtuel (`.venv`).
2.  **Dépendances** : Installez les paquets requis.
    ```bash
    pip install -r requirements.txt
    ```

## ▶️ Utilisation

1.  **Extraction du réseau (optionnel si déjà fourni)** : 
    Avant de lancer la simulation, il faut générer le fichier `mining_network.graphml`.
    ```bash
    python core/extraction.py
    ```
2.  **Lancement du serveur et de la simulation** :
    Démarrez l'API FastAPI, qui initialisera également la boucle de simulation en arrière-plan.
    ```bash
    python api/main.py
    ```
3.  **Interface Utilisateur** : 
    Ouvrez votre navigateur et accédez à `http://localhost:8080/` pour visualiser le tableau de bord interactif de la logistique minière en temps réel.
