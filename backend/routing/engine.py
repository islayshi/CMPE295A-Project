"""
A* Routing Engine Core
Fight Fire With AI

Implements the pure-Python A* algorithm on the BayAreaGrid graph.
NFR-P02: Must respond in < 2.0 seconds.
"""

import math
import heapq
import logging
from django.contrib.gis.geos import Point
from grid.models import BayAreaGrid

logger = logging.getLogger(__name__)

# Global cache for the grid graph to avoid re-querying 18,000 cells per request
_GRID_CACHE = None
_ADJACENCY_CACHE = None

def _haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in kilometers between two points 
    on the earth (specified in decimal degrees).
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles.
    return c * r

def _build_grid_graph():
    """
    Loads all BayAreaGrid cells into memory and builds the adjacency graph.
    Returns:
        nodes: dict of cell_id -> {'row': int, 'col': int, 'centroid': Point}
        adjacency: dict of cell_id -> list of neighbor cell_ids
    """
    global _GRID_CACHE, _ADJACENCY_CACHE
    if _GRID_CACHE is not None and _ADJACENCY_CACHE is not None:
        return _GRID_CACHE, _ADJACENCY_CACHE

    logger.info("Building BayAreaGrid graph cache...")
    cells = BayAreaGrid.objects.all().values('id', 'row', 'col', 'centroid')
    
    # Build fast lookups
    nodes = {c['id']: c for c in cells}
    grid_map = {(c['row'], c['col']): c['id'] for c in cells}
    
    adjacency = {}
    for c in cells:
        r, col = c['row'], c['col']
        neighbors = []
        # 8-directional movement
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                neighbor_id = grid_map.get((r + dr, col + dc))
                if neighbor_id is not None:
                    neighbors.append(neighbor_id)
        adjacency[c['id']] = neighbors
        
    _GRID_CACHE = nodes
    _ADJACENCY_CACHE = adjacency
    return nodes, adjacency

def _find_closest_cell(target_point, nodes):
    """
    Finds the closest grid cell to the given GPS point.
    Since nodes is in-memory, we just do a quick scan. 
    (For 18,000 nodes, a scan takes < 5ms).
    """
    closest_id = None
    min_dist = float('inf')
    
    t_lon, t_lat = target_point.x, target_point.y
    
    for cell_id, data in nodes.items():
        c_lon, c_lat = data['centroid'].x, data['centroid'].y
        dist = _haversine(t_lon, t_lat, c_lon, c_lat)
        if dist < min_dist:
            min_dist = dist
            closest_id = cell_id
            
    return closest_id

def _reconstruct_path(came_from, current_id, nodes):
    """
    Reconstructs the path from destination back to origin.
    Returns a list of Point objects (the centroids of the path cells).
    """
    path = [nodes[current_id]['centroid']]
    while current_id in came_from:
        current_id = came_from[current_id]
        path.append(nodes[current_id]['centroid'])
    path.reverse()
    return path

def compute_astar_route(origin_point: Point, destination_point: Point, blocked_cell_ids: set):
    """
    Computes the shortest path from origin to destination avoiding blocked_cell_ids.
    Uses A* on the 1x1 km BayAreaGrid.
    
    Returns:
        List of Point objects forming the safe route, or None if no path exists.
    """
    nodes, adjacency = _build_grid_graph()
    
    # 1. Find nearest grid cells for origin and destination
    start_id = _find_closest_cell(origin_point, nodes)
    goal_id = _find_closest_cell(destination_point, nodes)
    
    if not start_id or not goal_id:
        logger.error("Could not map origin/destination to grid cells.")
        return None
        
    if start_id in blocked_cell_ids:
        logger.warning("Origin is inside a blocked cell!")
        # We can still try to route them out, but it's dangerous.
        
    if goal_id in blocked_cell_ids:
        logger.warning("Destination is inside a blocked cell. No safe path possible.")
        return None

    # A* initialization
    # open_set is a min-heap queue. Entries are tuples of (f_score, cell_id)
    open_set = []
    heapq.heappush(open_set, (0, start_id))
    
    came_from = {}
    
    # g_score: cost from start along best known path
    g_score = {start_id: 0}
    
    # f_score: g_score + heuristic (estimated distance to goal)
    g_lon, g_lat = nodes[goal_id]['centroid'].x, nodes[goal_id]['centroid'].y
    start_lon, start_lat = nodes[start_id]['centroid'].x, nodes[start_id]['centroid'].y
    
    f_score = {start_id: _haversine(start_lon, start_lat, g_lon, g_lat)}
    
    # Keep track of items in open_set for O(1) membership check
    open_set_hash = {start_id}
    
    while open_set:
        current_f, current_id = heapq.heappop(open_set)
        open_set_hash.remove(current_id)
        
        if current_id == goal_id:
            return _reconstruct_path(came_from, current_id, nodes)
            
        c_lon, c_lat = nodes[current_id]['centroid'].x, nodes[current_id]['centroid'].y
            
        for neighbor_id in adjacency[current_id]:
            if neighbor_id in blocked_cell_ids:
                continue
                
            n_lon, n_lat = nodes[neighbor_id]['centroid'].x, nodes[neighbor_id]['centroid'].y
            
            # The distance from current to neighbor
            step_cost = _haversine(c_lon, c_lat, n_lon, n_lat)
            tentative_g_score = g_score[current_id] + step_cost
            
            if neighbor_id not in g_score or tentative_g_score < g_score[neighbor_id]:
                came_from[neighbor_id] = current_id
                g_score[neighbor_id] = tentative_g_score
                f_score[neighbor_id] = tentative_g_score + _haversine(n_lon, n_lat, g_lon, g_lat)
                
                if neighbor_id not in open_set_hash:
                    heapq.heappush(open_set, (f_score[neighbor_id], neighbor_id))
                    open_set_hash.add(neighbor_id)
                    
    logger.warning("A* search exhausted without reaching destination.")
    return None

# For testing purposes, allow resetting the cache
def _reset_cache():
    global _GRID_CACHE, _ADJACENCY_CACHE
    _GRID_CACHE = None
    _ADJACENCY_CACHE = None
