import time
import psutil
import pandas as pd
import os
from simulation.agents import TruckStatus

def get_active_agents(model):
    return len([a for a in model.agents if a.status != TruckStatus.DELIVERED])

def get_compute_time(model):
    return model.last_compute_time

def get_cpu_usage(model):
    return psutil.cpu_percent(interval=None)

def get_ram_usage_mb(model):
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)

def get_routing_queue(model):
    return len([a for a in model.agents if a.status == TruckStatus.ROUTING])

def get_routes_per_sec(model):
    return model.last_routes_per_sec
