from lib import tsp
from lib.local_search import termination
import numpy as np
import random
import copy
import math
import pygad


# Performs swap mutation on a single offspring, returning the mutated
# individual
def swap_mutation(offspring):
  mutated_offspring = copy.deepcopy(offspring)
  i = random.randint(0,len(offspring)-2)
  j = random.randint(i+1,len(offspring)-1)
  mutated_offspring[i], mutated_offspring[j] = offspring[j], offspring[i]
  return mutated_offspring

# Performs order one crossover on pair of parents, returning two offspring
def order_one_crossover(parent_1, parent_2):
  def single_order_one_crossover(parent_1, parent_2, sublist_start,
                                 sublist_len):
    offspring = [None]*len(parent_1)
    
    # Works out where the end of the sublist should be if the sublist loops
    # round past the end of the list.
    sublist_end = sublist_start + sublist_len
    if sublist_end >= len(parent_1):
      sublist_end = sublist_end - len(parent_1)

    # Copy sub-list from parent 1 into offspring
    sublist_pos = sublist_start
    while sublist_pos != sublist_end:
      offspring[sublist_pos] = parent_1[sublist_pos]
      sublist_pos = sublist_pos + 1
      if sublist_pos == len(parent_1):
        sublist_pos = 0

    # Get cities which aren't yet in offspring in the order in which they
    # appear in parent 2, starting at the end of the sub-list copied on the
    # previous step.
    remaining_cities = []
    remainder_pos = sublist_end
    started = False
    while not started or remainder_pos != sublist_end:
      started = True
      city = parent_2[remainder_pos]
      if city not in offspring:
        remaining_cities.append(city)
      remainder_pos = remainder_pos + 1
      if remainder_pos == len(parent_1):
        remainder_pos = 0
        
    # Insert the remaining cities into offspring, starting at the end of the
    # sub-list from parent 1
    offspring_pos = sublist_end
    for city in remaining_cities:
      offspring[offspring_pos] = city
      offspring_pos = offspring_pos + 1
      if offspring_pos == len(parent_1):
        offspring_pos = 0

    return offspring
  
  # Picks the starting point and length of the sublist to be used for order 1
  # mutation. The length is constrained to be no more than the length of an
  # individual - 2 as, past this length, the resulting offspring is guaranteed
  # to be a clone of the parent.
  sublist_start = random.randint(0,len(parent_1) - 1)
  sublist_len = random.randint(0,len(parent_1) - 2)
    
  offspring_1 = single_order_one_crossover(parent_1,parent_2,sublist_start,
                                           sublist_len)
  offspring_2 = single_order_one_crossover(parent_2,parent_1,sublist_start,
                                           sublist_len)
  return offspring_1, offspring_2

# This function generates a solution to the TSP using an EA.
# The implementation is based on the pygad library. For documentation, which
# may help you if you want to modify this code, see:
# https://pygad.readthedocs.io/en/latest/pygad.html#pygad-ga-class
#
# This function wraps pygads implementation, allowing you to specify:
#  - tsp_instance: the problem to be solver,
#  - pop_size: the number of individuals in the population,
#  - tournament_size: this function uses tournament-based parent selection
#                     (pygad has other options available). This parameter
#                     allows you to specify the size of the tournament.
#  - elitism: a Boolean parameter which specifies whether the single fittest
#             individual from one generation should be copied into the next
#             generation. If False, then it is not. If True, then it is.
#  - mutation_probability: The probability that each offspring will undergo
#                          mutation.
#  - mutation_operator: The mutation operator for the EA. Should take a
#                       single offspring as input and return a single mutated
#                       offspring.
#  - crossover_probability: The probability that each pair of parents will
#                           undergo crossover.
#  - crossover_operator: The crossover operator for the EA. Should take a pair
#                        of parents as input and return a pair of offspring
#                        resulting from their crossover.
#  - time_limit: The amount of time (in seconds) to run the EA for.
#  - plot_fitness: a Boolean parameter which specifies whether a plot should be
#                  created when the EA terminates to show the fitness of the
#                  fittest solution found at each generation.
def solve_tsp(
    tsp_instance,
    pop_size = 100,
    tournament_size = 2,
    elitism = False,
    mutation_probability = 0.7,
    mutation_operator = swap_mutation,
    crossover_probability = 1.0,
    crossover_operator = order_one_crossover,
    time_limit = 3,
    plot_fitness = False
  ):
  is_minimization = True
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Representation
  # Internally, we will represent a TSP tour as a list of all cities
  # (including starting city). This representation works well with order 1
  # crossover. We will, however, need to add the loop back to the starting city
  # before we pass a tour to our evaluation function.
  n_cities = tsp_instance.number_of_nodes()
  # A solution should be a list of size n_cities
  num_genes = n_cities
  # Each element of the solution should be an integer...
  gene_type=int
  # ...and should be in the range [0,n_cities-1] (i.e. should be a valid city).
  gene_space = list(range(0,n_cities))
  # We do not allow cities to appear twice in the list.
  allow_duplicate_genes = False
  def complete_tsp_loop(route):
    return np.append(route,route[0])

  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Fitness evaluation
  #
  # pygad expects a fitness function to take 3 inputs: our GA instance, a
  # solution and the solution's index. We will wrap our evaluation function
  # so that it meets these requirements.
  #
  # Remember that EAs typically try to maximise fitness. We want a short TSP
  # tour, so need to transform the TSP evaluation function so that we get a
  # short tour by maximising it. The simple way to do this is to multiply by
  # -1.
 
  def fitness_function(ga_instance,solution,solution_idx):
    # Internally, no need to use the ga_instance and solution_idx variables
    if is_minimization:
      return -1*tsp.evaluate(tsp_instance,complete_tsp_loop(solution))
    else:
      return tsp.evaluate(tsp_instance,complete_tsp_loop(solution))

  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Initialisation
  #
  # pygad can initialise a population given the representation information
  # specified above.
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Population size
  sol_per_pop = pop_size
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Number of offspring: same as population size
  num_parents_mating = sol_per_pop
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Parent selection: tournament selection
  parent_selection_type="tournament"
  K_tournament = tournament_size
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Survivor selection: simple generational model. Parameterised option to
  # allow the most fit parent to persist into the next generation (elitism).

  # Do not keep any parents in the next generation...
  keep_parents = 0
  # ...unless the user has chosen to use elitism. If so, keep the single
  # fittest individual.
  if elitism:
    keep_elitism = 1
  else:
    keep_elitism = 0
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Mutation
  
  # Do not worry about this function. It simply applies whatever mutation
  # operator has been specified (by default, swap_mutation) to each individual
  # with probability given by mutation_probability
  def mutation_func(offspring_pop, ga_instance):
    for i in range(0,len(offspring_pop)):
      if random.random() < mutation_probability:
        offspring_pop[i] = mutation_operator(offspring_pop[i])
    return offspring_pop
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  # Recombination
  
  # As above, do not worry about this function. It simply applies whatever
  # crossover operator has been specified (by default, order_one_crossover) to
  # each pair of parents with probability given by crossover_probability
  def crossover_func(parents, offspring_size, ga_instance):
    offspring = []
    idx = 0
    while len(offspring) != offspring_size[0]:
      parent_1 = parents[idx % parents.shape[0], :].copy()
      parent_2 = parents[(idx + 1) % parents.shape[0], :].copy()

      if random.random() < crossover_probability:
        offspring_1, offspring_2 = crossover_operator(parent_1, parent_2)
      else:
        offspring_1, offspring_2 = parent_1, parent_2

      offspring.append(parent_1)
      idx += 1      
      # If the number of offspring is not divisible by 2, don't overfill the
      # offspring array.
      if len(offspring) != offspring_size[0]:
        offspring.append(offspring_2)
        idx += 1

    return np.array(offspring)
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  #Termination: time-based

  # In pygad, the EA will stop if its "on_generation" method returns the string
  # "stop" at any point. We will do this using a time-based criterion.
  termination_criterion = termination.Time_Expired(time_limit)
  def time_based_termination(ga_instance):
    if termination_criterion.condition_met(None,None,None):
      return "stop"
    else:
      return None

  # Set num_generations_max to an extremely high value. By default, pygad
  # terminates after this number of generations. We want to terminate based on
  # time, not number of generations so set this high enough that the time-based
  # criterion is triggered first.
  num_generations_max = 500000000
  #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
  
  def invert_fitness(ga_instance, last_population_fitness):
    if is_minimization:
      ga_instance.best_solutions_fitness = [ -1 * fitness for fitness in ga_instance.best_solutions_fitness]
    
  # Now start the GA. As specified at the start of the function, if you want to
  # modify this code, I recommend reading the documentation at
  # https://pygad.readthedocs.io/en/latest/pygad.html#pygad-ga-class
  ga_instance = pygad.GA(
    num_genes = num_genes,
    gene_type = gene_type,
    gene_space = gene_space,
    allow_duplicate_genes = allow_duplicate_genes,
    fitness_func = fitness_function,
    sol_per_pop = sol_per_pop,
    num_parents_mating = num_parents_mating,
    parent_selection_type = parent_selection_type,
    K_tournament = K_tournament,
    keep_parents = keep_parents,
    keep_elitism = keep_elitism,
    mutation_type = mutation_func,
    mutation_probability = mutation_probability,
    crossover_type = crossover_func,
    crossover_probability = crossover_probability,
    on_generation = time_based_termination,
    num_generations = num_generations_max,
    on_stop = invert_fitness
  )

  ga_instance.run()
  if plot_fitness:
    ga_instance.plot_fitness()
    
  solution, solution_fitness, solution_idx = ga_instance.best_solution()
  if is_minimization:
    solution_fitness = -1 * solution_fitness
  return complete_tsp_loop(solution), solution_fitness