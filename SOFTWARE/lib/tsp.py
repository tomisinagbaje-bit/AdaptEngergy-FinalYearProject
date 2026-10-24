import numpy as np
import math
import matplotlib.pyplot as plt
import networkx as nx
from networkx.classes.function import path_weight
import random

# Constructs a TSP instance from a matrix (i.e. list of lists) adjacency_matrix
# in which adjacency_matrix[i][j] corresponds to the length of the edge from
# city i to city j.
def construct(adjacency_matrix):
  return nx.from_numpy_matrix(np.matrix(adjacency_matrix))

# Constructs a TSP instance from a matrix city_coords in which each row of the
# matrix represents the Cartesian coordinates of a city.
def construct_from_city_coords(city_coords):
  def dist(x,y):
    return math.sqrt((x[0] - y[0])**2 + (x[1] - y[1])**2)

  adjacency_matrix = [ [dist(x,y) for x in city_coords] for y in city_coords]
  
  return construct(adjacency_matrix)

# Displays a TSP instance on a 2D plane. Optional args:
#  - city_coords: Cartesian coordinates of the cities use to position cities in
#    the 2D plane. If no coordinates are provided, arbitrary ones are
#    generated.
#  - label_edges: Whether or not the edges of the graph should be labelled with
#    their weights. It is recommended to set this as False for all but very
#    small graphs as the number of edges quickly grows very large.
#  - title: A title for the plot
def display_instance(tsp_instance,city_coords = None,label_edges=False,title=None):
  if city_coords is None:
    city_coords = nx.spring_layout(tsp_instance)
  
  # First, we create a new figure into which to plot our graph.
  plt.figure()
  # With the positions defined, we can now draw the graph itself...
  nx.draw_networkx(tsp_instance,city_coords)
  # ... and, if we wish, we can label the edges according to their weights.
  if label_edges:
    edge_labels = nx.get_edge_attributes(tsp_instance,'weight')
    nx.draw_networkx_edge_labels(tsp_instance,city_coords,edge_labels=edge_labels)
  # Add a title to the plot
  if title is not None:
    plt.title(title)
  # Finally, we display the graph
  plt.show()

# Checks that an array specifies a valid TSP route. A valid TSP route should:
#   - visit all cities
#   - visit its starting city twice: once at the start and once at the end of
#     the route,
#   - aside from its starting city, it should visit each city exactly once. 
#
# An example of a valid route for a TSP instance with 4 cities would be 
# [1,2,3,0,1].
def is_valid_route(tsp_instance,route):
  number_of_cities = tsp_instance.number_of_nodes()
  # Check if the route returns to the starting city
  if route[0] != route[-1]: return False
  # Check that only the starting city is repeated in the route
  elif len(route) != len(set(route)) + 1: return False
  # Check all cities have been visited
  elif len(route) != number_of_cities + 1: return False
  # If so, the route is valid
  else: return True

# Displays a TSP instance on a 2D plane. Overlays a specified route on this
# instance. Optional args:
#  - city_coords: Cartesian coordinates of the cities use to position cities in
#    the 2D plane. If no coordinates are provided, arbitrary ones are
#    generated.
#  - label_edges: Whether or not the edges of the graph should be labelled with
#    their weights. It is recommended to set this as False for all but very
#    small graphs as the number of edges quickly grows very large.
#  - title: A title for the plot
def display_route(tsp_instance,route,city_coords = None,label_edges=False,title=None):
  if not is_valid_route(tsp_instance,route):
    raise ValueError('{} is not a valid route for a TSP instance with {} cities'.format(route,tsp_instance.number_of_nodes()))
  
  if city_coords is None:
    city_coords = nx.spring_layout(tsp_instance)

  # First, we create a new figure into which to plot our graph.
  plt.figure()
  # With the positions defined, we can now draw the TSP instance itself...
  nx.draw_networkx(tsp_instance,city_coords,edge_color="blue",width=0.5)

  # ...then overlay the route.
  edge_list = list(nx.utils.pairwise(route))
  nx.draw_networkx(
    tsp_instance,
    city_coords,
    edgelist=edge_list,
    edge_color="red",
    width=3,
  )
  # Label the edges according to their weights.
  if label_edges:
    edge_labels = nx.get_edge_attributes(tsp_instance,'weight')
    nx.draw_networkx_edge_labels(tsp_instance,city_coords,edge_labels=edge_labels)
  # Add a title to the plot
  if title is not None:
    plt.title(title)
  # Finally, we display the graph
  plt.show()

# Evaluates a given route on a TSP instance, returning the total length of the
# tour.
def evaluate(tsp_instance,route):
  if not is_valid_route(tsp_instance,route):
    raise ValueError('{} is not a valid route for a TSP instance with {} cities'.format(route,tsp_instance.number_of_nodes()))
  return path_weight(tsp_instance, route, weight="weight")

# Generates a random, valid route for a given TSP instance. As TSP routes are
# complete loops, we will generate routes which start and end at city 0.
def random_route(tsp_instance):
  number_of_cities = tsp_instance.number_of_nodes()
  # Start with a valid route (minus the starting city - city 0).
  route_middle = [*range(1,number_of_cities)]
  # Shuffle the route into a random order.
  random.shuffle(route_middle)
  # Add the starting city and loop back to it at the end.
  return [0] + route_middle + [0]