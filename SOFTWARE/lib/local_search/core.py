# Runs local search until a termination condition is reached then return the
# best solution found along with its cost.
# - initializer: a function which constructs a valid initial solution to the
#                problem being solved.
# - evaluate: A function to measure solution quality. Takes a valid solution as
#             input and returns its objective function value.
# - termination: A termination condition. Must be an object with a 
#                "condition_met" method which takes iteration count, the current
#                solution and its cost as input. Returns True if the
#                termination condition has been met, false otherwise.
# - neighbourhood: A neighbourhood function. Takes a solution as input and 
#                  returns a list containing all neighbours of that solution.
# - step: A step function. Takes the current solution and its cost, a list of
#         neighbours and an evaluation function. It chooses the next solution to
#         try in local search and returns it, along with its cost.
# - print_improvements: Whether to print the cost and value of improved
#                       solutions when they are found.
def run(
      initializer,
      evaluate,
      termination,
      neighbourhood,
      step,
      print_improvements = False
  ):
  iteration = 0
  current_soln = initializer()
  current_cost = evaluate(current_soln)
  best_soln, best_cost = current_soln, current_cost
  while not termination.condition_met(iteration,current_soln,current_cost):
    neighbouring_solns = neighbourhood(current_soln)
    current_soln, current_cost = step(
      current_soln,
      current_cost,
      neighbouring_solns,
      evaluate
    )
    if current_cost < best_cost:
      best_soln, best_cost = current_soln, current_cost
      if print_improvements:
        print("New best cost is {}.".format(best_cost))
        print("New best solution is {}.".format(best_soln))
  return best_soln, best_cost

# Runs local search, restarting the search whenever a restart condition is met
# and repeating until a termination condition is met. Returns the best
# solution found along with its cost.
# - initializer: a function which constructs a valid initial solution to the
#                problem being solved.
# - evaluate: A function to measure solution quality. Takes a valid solution as
#             input and returns its objective function value.
# - make_restart: A function which can be called to create a new restart
#                condition. Similarly to the below, the restart condition must
#                be an object with a "condition_met" method which takes
#                iteration count, the current solution and its cost as input.
#                Returns True if the termination condition has been met, false
#                otherwise.
# - termination: A termination condition. Must be an object with a 
#                "condition_met" method which takes iteration count, the current
#                solution and its cost as input. Returns True if the
#                termination condition has been met, false otherwise.
# - neighbourhood: A neighbourhood function. Takes a solution as input and 
#                  returns a list containing all neighbours of that solution.
# - step: A step function. Takes the current solution and its cost, a list of
#         neighbours and an evaluation function. It chooses the next solution to
#         try in local search and returns it, along with its cost.
# - print_improvements: Whether to print the cost and value of improved
#                       solutions when they are found.
def run_with_restart(
      initializer,
      evaluate,
      make_restart,
      termination,
      neighbourhood,
      step,
      print_improvements = False
  ):
    
  restart = make_restart()
  current_soln, current_cost = run(initializer,evaluate,restart,neighbourhood,step)
  best_soln, best_cost = current_soln, current_cost
   
  iteration = 0
  while not termination.condition_met(iteration,current_soln,current_cost):
    iteration = iteration + 1
    restart = make_restart()
    current_soln, current_cost = run(initializer,evaluate,restart,neighbourhood,step)
    if current_cost < best_cost:
      best_soln, best_cost = current_soln, current_cost
      if print_improvements:
        print("New best cost is {}.".format(best_cost))
        print("New best solution is {}.".format(best_soln))

  return best_soln, best_cost