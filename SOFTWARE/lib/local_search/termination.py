import math
import time

# This condition is met when called twice consecutively if the second cost
# passed to the conditon_met method is no better than the first cost.
class No_Improvement:
  def __init__(self):
    self.prev_cost = float('inf')
  
  def condition_met(self,_,__,current_cost):
    if(math.isclose(self.prev_cost,current_cost)):
      return True
    else:
      self.prev_cost = current_cost
      return False

# This condition is met when the time in seconds indicated by time_limit has
# passed since the condition's construction.
class Time_Expired:
  # Construct a time-limit based termination condition.
  #  - time_limit: The time in seconds until the the algorithm should
  #                terminate.
  def __init__(self,time_limit):
    self.start_time = time.time()
    self.time_limit = time_limit

  def condition_met(self,_,__,___):
    return time.time() >= self.start_time + self.time_limit
    