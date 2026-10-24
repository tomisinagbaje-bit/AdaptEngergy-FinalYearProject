import random

# The best improver step function evaluates all solutions in a neighbourhood
# and returns the one with the lowest cost.
def best_improver(current_soln,current_cost,neighbouring_solns,evaluate):
  best_neighbour, best_neighbour_cost = current_soln,current_cost
  for neighbour in neighbouring_solns:
    neighbour_cost = evaluate(neighbour)
    if neighbour_cost < best_neighbour_cost:
      best_neighbour, best_neighbour_cost = neighbour, neighbour_cost
  return best_neighbour, best_neighbour_cost