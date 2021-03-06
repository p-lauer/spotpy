# -*- coding: utf-8 -*-
'''

:author: Patrick Lauer

This class holds the Fitness Scaled Chaotic Artificial Bee Colony(FSCABC) algorithm, based on Zhang (2011):

Yudong Zhang, Lenan Wu, and Shuihua Wang. “Magnetic Resonance Brain Image Classification by an Improved Artificial Bee Colony Algorithm.” Progress In Electromagnetics Research 116. EMW Publishing: 65–79. 2011

Yudong Zhang, Lenan Wu, and Shuihua Wang. “UCAV Path Planning by Fitness-Scaling Adaptive Chaotic Particle Swarm Optimization.” Mathematical Problems in Engineering 2013. Hindawi Publishing Corporation. 2013

'''
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from . import _algorithm
import spotpy
import numpy as np
import time
import random
import itertools
from operator import itemgetter


class fscabc(_algorithm):
    '''
    Implements the FSCABC algorithm from Zhang (2011).

    Input
    ----------
    spot_setup: class
        model: function 
            Should be callable with a parameter combination of the parameter-function 
            and return an list of simulation results (as long as evaluation list)
        parameter: function
            When called, it should return a random parameter combination. Which can 
            be e.g. uniform or Gaussian
        objectivefunction: function 
            Should return the objectivefunction for a given list of a model simulation and 
            observation.
        evaluation: function
            Should return the true values as return by the model.

    dbname: str
        * Name of the database where parameter, objectivefunction value and simulation results will be saved.

    dbformat: str
        * ram: fast suited for short sampling time. no file will be created and results are saved in an array.
        * csv: A csv file will be created, which you can import afterwards.        

    parallel: str
        * seq: Sequentiel sampling (default): Normal iterations on one core of your cpu.
        * mpc: Multi processing: Iterations on all available cores on your cpu (recommended for windows os).
        * mpi: Message Passing Interface: Parallel computing on cluster pcs (recommended for unix os).

    save_sim: boolean
        *True:  Simulation results will be saved
        *False: Simulationt results will not be saved
     '''

    def __init__(self, spot_setup, dbname=None, dbformat=None, parallel='seq', save_sim=True):

        _algorithm.__init__(self, spot_setup, dbname=dbname,
                            dbformat=dbformat, parallel=parallel, save_sim=save_sim)

    def mutate(self, r):
        x = 4 * r * (1 - r)
        return x

    def sample(self, repetitions, eb=48, a=(1 / 10), peps=0.0001, kpow=5, ownlimit=False, limit=24):
        """


        Parameters
        ----------
        repetitions: int
            maximum number of function evaluations allowed during optimization
        eb: int
            number of employed bees (half of population size)
        a: float
            mutation factor
        peps: float
            convergence criterium    
        kpow: float
            exponent for power scaling method
        ownlimit: boolean
            determines if an userdefined limit is set or not
        limit: int
            sets the limit
        """
        # Initialize the progress bar
        starttime = time.time()
        intervaltime = starttime
        # Initialize FSCABC parameters:
        randompar = self.parameter()['random']
        self.nopt = randompar.size
        random.seed()
        if ownlimit == True:
            self.limit = limit
        else:
            self.limit = eb
        lb, ub = self.parameter()['minbound'], self.parameter()['maxbound']
        # Generate chaos
        r = 0.25
        while r == 0.25 or r == 0.5 or r == 0.75:
            r = random.random()
        # Initialization
        work = []
        firstcall = True
        # Calculate the objective function
        param_generator = (
            (rep, self.parameter()['random']) for rep in range(eb))
        for rep, randompar, simulations in self.repeat(param_generator):
            # Calculate fitness
            like = self.objectivefunction(
                evaluation=self.evaluation, simulation=simulations)
            self.status(rep, like, randompar)
            if firstcall == True:
                self.initialize_database(randompar, self.parameter()['name'], simulations, like)
                firstcall = False
            # Save everything in the database
            self.datawriter.save(like, randompar, simulations=simulations)
            c = 0
            p = 0
            # (fit_x,x,fit_v,v,limit,normalized fitness)
            work.append([like, randompar, like, randompar, c, p])
            # Progress bar
            acttime = time.time()
            # get str showing approximate timeleft to end of simulation in H,
            # M, S
            timestr = time.strftime("%H:%M:%S", time.gmtime(round(((acttime - starttime) /
                                                                   (rep + 1)) * (repetitions - (rep + 1)))))
            # Refresh progressbar every second
            if acttime - intervaltime >= 2:
                text = '%i of %i (best like=%g) est. time remaining: %s' % (rep, repetitions,
                                                                            self.status.objectivefunction, timestr)
                print(text)
                intervaltime = time.time()
        icall = 0
        gnrng = 1e100
        # and criter_change>pcento:
        while icall < repetitions and gnrng > peps:
            # Employed bee phase
            # Generate new input parameters
            for i, val in enumerate(work):
                k = i
                while k == i:
                    k = random.randint(0, (eb - 1))
                j = random.randint(0, (self.nopt - 1))
                work[i][3][j] = work[i][1][j] + \
                    random.uniform(-a, a) * (work[i][1][j] - work[k][1][j])
                if work[i][3][j] < lb[j]:
                    work[i][3][j] = lb[j]
                if work[i][3][j] > ub[j]:
                    work[i][3][j] = ub[j]
                '''
                #Scout bee phase
                if work[i][4] >= self.limit:
                    work[i][3]=self.parameter()['random']
                    work[i][4]=0
                '''
            # Calculate the objective function
            param_generator = ((rep, work[rep][3]) for rep in range(eb))
            for rep, randompar, simulations in self.repeat(param_generator):
                # Calculate fitness
                clike = self.objectivefunction(
                    evaluation=self.evaluation, simulation=simulations)
                if clike > work[rep][0]:
                    work[rep][1] = work[rep][3]
                    work[rep][0] = clike
                    work[rep][4] = 0
                else:
                    work[rep][4] = work[rep][4] + 1
                self.status(rep, work[rep][0], work[rep][1])
                self.datawriter.save(
                    clike, work[rep][3], simulations=simulations, chains=icall)
                icall += 1
            # Fitness scaling
            bn = []
            csum = 0
            work.sort(key=lambda item: item[0])
            for i, val in enumerate(work):
                work[i][5] = i**kpow
                csum = work[i][5] + csum
            for i, val in enumerate(work):
                work[i][5] = work[i][5] / csum
                bn.append(work[i][5])
            bounds = np.cumsum(bn)
        # Onlooker bee phase
            # Roulette wheel selection
            for i, val in enumerate(work):
                pn = random.uniform(0, 1)
                k = i
                while k == i:
                    k = random.randint(0, eb - 1)
                for t, vol in enumerate(bounds):
                    if bounds[t] - pn >= 0:
                        z = t
                        break
                j = random.randint(0, (self.nopt - 1))
            # Generate new input parameters
                work[i][3][j] = work[z][1][j] + \
                    random.uniform(-a, a) * (work[z][1][j] - work[k][1][j])
                if work[i][3][j] < lb[j]:
                    work[i][3][j] = lb[j]
                if work[i][3][j] > ub[j]:
                    work[i][3][j] = ub[j]
            # Calculate the objective function
            param_generator = ((rep, work[rep][3]) for rep in range(eb))
            for rep, randompar, simulations in self.repeat(param_generator):
                # Calculate fitness
                clike = self.objectivefunction(
                    evaluation=self.evaluation, simulation=simulations)
                if clike > work[rep][0]:
                    work[rep][1] = work[rep][3]
                    work[rep][0] = clike
                    work[rep][4] = 0
                else:
                    work[rep][4] = work[rep][4] + 1
                self.status(rep, work[rep][0], work[rep][1])
                self.datawriter.save(
                    clike, work[rep][3], simulations=simulations, chains=icall)
                icall += 1
        # Scout bee phase
            for i, val in enumerate(work):
                if work[i][4] >= self.limit:
                    for g, bound in enumerate(ub):
                        r = self.mutate(r)
                        work[i][1][g] = lb[g] + r * (ub[g] - lb[g])
                    work[i][4] = 0
                    t, work[i][0], simulations = self.simulate(
                        (icall, work[i][1]))
                    clike = self.objectivefunction(
                        evaluation=self.evaluation, simulation=simulations)
                    self.datawriter.save(
                        clike, work[rep][3], simulations=simulations, chains=icall)
                    work[i][0] = clike
                    icall += 1
            gnrng = -self.status.objectivefunction
            text = '%i of %i (best like=%g) est. time remaining: %s' % (
                icall, repetitions, self.status.objectivefunction, timestr)
            print(text)
            if icall >= repetitions:
                print('*** OPTIMIZATION SEARCH TERMINATED BECAUSE THE LIMIT')
                print('ON THE MAXIMUM NUMBER OF TRIALS ')
                print(repetitions)
                print('HAS BEEN EXCEEDED.')

            if gnrng < peps:
                print(
                    'THE POPULATION HAS CONVERGED TO A PRESPECIFIED SMALL PARAMETER SPACE')
        print('Best parameter set:')
        print(self.status.params)
        text = 'Duration:' + str(round((acttime - starttime), 2)) + ' s'
        print(-self.status.objectivefunction)
        print(icall)
        try:
            self.datawriter.finalize()
        except AttributeError:  # Happens if no database was assigned
            pass

