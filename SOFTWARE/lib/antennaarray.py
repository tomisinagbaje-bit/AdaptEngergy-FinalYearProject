import math
import numpy as np

# Car price prediction problem
class AntennaArray:
    # The minimum distance between antennae.
    MIN_SPACING = 0.25
    
    # Construct an antenna design problem instance.
    # The parameter "n_antennae" specifies the number of antennae in our array.
    # The parameter "steering_angle" specifies the desired direction of the
    # main beam in degrees.
    def __init__(self,n_antennae,steering_angle):    
      self.n_antennae = n_antennae
      self.steering_angle = steering_angle
   
    # Rectangular bounds on the search space.
    # Returns a 2D array b such that b[i][0] is the minimum permissible value
    # of the ith solution component and b[i][1] is the maximum.    
    def bounds(self):
        return [[0,self.n_antennae/2] for i in range(self.n_antennae)]

    # Check whether an antenna design lies within the problem's feasible
    # region.
    # A design is a vector of n_antennae anntena placements.
    # A placement is a distance from the left hand side of the antenna array.
    # A valid placement is one in which
    #   1) all antennae are separated by at least MIN_SPACING
    #   2) the aperture size (the maximum element of the array) is exactly
    #      n_antennae/2.
    def is_valid(self, design):
        # The design has the correct number of antennae
        if len(design) != self.n_antennae:
          return False
        
        des = design.copy()
        des.sort()
        
        # Apperture size is exactly n_antennae/2
        if abs(des[-1] - self.n_antennae/2) > 1e-10:
          return False
        # All antennae lie within the problem bounds
        for placement, bound in zip(des,self.bounds()):
          if placement < bound[0] or placement > bound[1]:
            return False
        
        # All antennae are separated by at least MIN_SPACING        
        for i in range(len(des)-1):
          if des[i+1] - des[i] < AntennaArray.MIN_SPACING:
            return False

        # If none of the above checks have been failed, the design must be
        # valid.
        return True

    # Evaluate an antenna design returning peak SSL.
    # Designs which violate problem constraints will be penalised with extremely
    # high costs.
    # The parameter "design" is a valid antenna array design.
    # If the design is not valid, it will be penalised by being assigned the
    # maximum possible numerical cost, float('inf').
    def evaluate(self,design):
        if(not self.is_valid(design)): return float('inf');

        class PowerPeak:
            def __init__(self,elevation,power):
                self.elevation = elevation;
                self.power = power;
        
        # Find all the peaks in power
        peaks = []
        prev = PowerPeak(0.0,float('-inf'))
        current = PowerPeak(0.0,self.__array_factor(design,0.0));
        for elevation in np.arange(0.01,180.01,0.01):
            nxt = PowerPeak(elevation,self.__array_factor(design,elevation))
            if current.power >= prev.power and current.power >= nxt.power:
                peaks.append(current)
            prev = current
            current = nxt
        peaks.append(PowerPeak(180.0,self.__array_factor(design,180.0)))
        peaks.sort(reverse = True,key = lambda peak:peak.power)

        # No side-lobes case
        if len(peaks)<2:
          return float('-inf')
        
        # Filter out main lobe and then return highest lobe level
        distance_from_steering = abs(peaks[0].elevation - self.steering_angle);
        for i in range(1,len(peaks)):
          # If the peak with the highest power is not the closest peak to the
          # steering angle, it is a side lobe and, therefore, must be the peak
          # side lobe.
          if abs(peaks[i].elevation - self.steering_angle) < distance_from_steering:
            return peaks[0].power
        # Otherwise, the peak with the highest power is not a side lobe. The
        # peak with the second highest power must be the peak side lobe.
        return peaks[1].power

    def __array_factor(self,design,elevation):
        steering = 2.0*math.pi*self.steering_angle/360.0;
        elevation = 2.0*math.pi*elevation/360.0;
        sum = 0.0
        for placement in design:
            sum += math.cos(2 * math.pi * placement * (math.cos(elevation) - math.cos(steering)))
        return 20.0*math.log(abs(sum))