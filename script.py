# BSD 2-Clause License

# Copyright (c) 2023, Hannes Van Overloop
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.

# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from CORBA import Any, TC_long, TC_float
from hpp.corbaserver import wrap_delete as wd
from hpp.corbaserver.manipulation import createContext, ProblemSolver, ConstraintGraph, Rule, Constraints, loadServerPlugin
from hpp.gepetto.manipulation import ViewerFactory
from hpp_idl.hpp import Error as HppError
from hpp.corbaserver.task_sequencing import Client as SolverClient
import pinocchio
from agimus_demos import InStatePlanner
import sys, argparse, numpy as np, time

from robot import Robot
from constraints import *
from resolution import *
from gtsp import *

# PARSE ARGUMENTS
defaultContext = "corbaserver"
p = argparse.ArgumentParser (description=
                             'Initialize demo of Pyrene manipulating a box')
p.add_argument ('--context', type=str, metavar='context',
                default=defaultContext,
                help="identifier of ProblemSolver instance")
p.add_argument ('--n-random-handles', type=int, default=None,
                help="Generate a random model with N handles.")
args = p.parse_args ()
if args.context != defaultContext:
    createContext (args.context)
isSimulation = args.context == "simulation"

# DEFINE CLASSES FOR THE PARTS
class Driller:
    urdfFilename = "package://gerard_bauzil/urdf/driller_with_qr_drill.urdf"
    srdfFilename = "package://gerard_bauzil/srdf/driller.srdf"
    rootJointType = "freeflyer"

class PartP72:
    urdfFilename = "package://agimus_demos/urdf/P72-with-table.urdf"
    srdfFilename = "package://agimus_demos/srdf/P72.srdf"
    rootJointType = "freeflyer"

class Airfoil:
    urdfFilename = "package://agimus_demos/tiago/deburring/urdf/airfoil.urdf"
    srdfFilename = "package://agimus_demos/tiago/deburring/srdf/airfoil.srdf"
    rootJointType = "freeflyer"

# THE ROBOT
robot = Robot('./tiago.urdf', args) # CREATE THE ROBOT
robot.setNeutralPosition() # SET ITS NEUTRAL POSITION

# PROBLEM SOLVER
print("Loading model")
ps = ProblemSolver(robot)
ps.loadPlugin("manipulation-spline-gradient-based.so")

# LOAD THE ROBOT INTO THE GUI
vf = ViewerFactory(ps)
vf.loadRobotModel (Driller, "driller")
# vf.loadRobotModel (PartP72, "part")
vf.loadRobotModel (Airfoil, "part")

robot.readSRDF() # LOAD SRDF DATA AND SET SOME JOINT BOUNDS
robot.disableCollisions() # DISABLE COLLISIONS

### GENERATE VIRTUAL HANDLES
# ps.robot.client.manipulation.robot.addGripper
# ps.robot.client.manipulation.robot.addHandle

# GET REAL HANDLES
all_handles = ps.getAvailable('handle')
part_handles = part_handles = list(filter(lambda x: x.startswith("part/"), all_handles))
holeCoords = robot.getHandlesCoords(part_handles)

# CLUSTER THEM
iso_c = 4 # expected nb of clusters
iso_nc = 5 # initial nb of clusters
iso_tn = 1 # min nb of points per cluster
iso_te = 1. # max variance
iso_tc = .75 # min distance between centroids
iso_nt = 5 # max merges per iteration
iso_ns = 500 # max iterations
iso_k = 100 # influence of the angle on the task distance
loadServerPlugin("corbaserver", "task-sequencing.so")
s = SolverClient()
print("Clustering tasks")
clusters = s.solver.testIsoData(holeCoords, len(holeCoords), len(holeCoords[0]), iso_c, iso_nc, iso_tn, iso_te, iso_tc, iso_nt, iso_ns, iso_k)

# GET COORDINATES OF VIRTUAL ONES
virtualHandles = list()
for c in clusters:
    normQ = pinocchio.Quaternion(c.centroid[3], c.centroid[4], c.centroid[5], c.centroid[6]).normalized()
    virtualHandles.append([c.centroid[0], c.centroid[1], c.centroid[2], normQ[0], normQ[1], normQ[2], normQ[3]])

# PROJECT THEM ON THE MESH
print("Projecting virtual handles")
# virtualHandlesOnSurface = list()
# p = 0
# closest = -1
# for vh in virtualHandles:
#     dist = s.tools.distanceToMesh(vh, p, closest)

# n = len(virtualHandles)
# s.solver.create(n)
# s.solver.setErrorThreshold(1e-6)
# s.solver.setMaxIterations(30)
# for i in range(n):
#     s.solver.addConstraint('tiago/gripper grasps driller/handle', i)
#     s.solver.addConstraint('part/root_joint', i)
#     if i != 0:
#         s.solver.addEqualityConstraint('tiago/root_joint', i, 0)

# q0 = [robot.q0[i] for i in range(len(robot.q0))]
# q0[:4] = [0, 1, 0, -1]
# e1 = 'driller/drill_tip pregrasps part/handle_0004'
# res, q1, err = graph.generateTargetConfig(e1, q0, q0)
# assert(res)
# e2 = 'driller/drill_tip pregrasps part/handle_0330'
# q0[:4] = [-0.1, 1, 0, -1]
# res, q2, err = graph.generateTargetConfig(e2, q0, q0)
# assert(res)

# s.solver.addConstraint('driller/drill_tip pregrasps part/handle_0004', 0)
# s.solver.addConstraint('driller/drill_tip pregrasps part/handle_0330', 1)
# q = q1 + q2
# s.solver.setRightHandSideFromVector(q)
# res, q3, err = s.solver.solve(q)
# dist, closest = s.tools.distanceToMesh(q0, [0,0,0])

# ADD THEM TO THE MODEL
robot.addVirtualHandles(len(clusters), virtualHandles) # to become virtualHandlesOnSurface

try:
    v = vf.createViewer()
except:
    print("Did not find viewer")


### SETTING A FEW VARIABLES AND PARAMETERS
print("Setting some parameters")

# SETTING JOINT BOUNDS
robot.defineVariousJointBounds()

# HPP PARAMETERS
ps.selectPathValidation("Graph-Discretized", 0.05)
#ps.selectPathValidation("Graph-Dichotomy", 0)
#ps.selectPathValidation("Graph-Progressive", 0.02)
ps.selectPathProjector("Progressive", 0.2)
ps.addPathOptimizer("EnforceTransitionSemantic")
ps.addPathOptimizer("SimpleTimeParameterization")
ps.setParameter("SimpleTimeParameterization/safety", 0.25)
ps.setParameter("SimpleTimeParameterization/order", 2)
ps.setParameter("SimpleTimeParameterization/maxAcceleration", 1.0)
ps.setParameter("ManipulationPlanner/extendStep", 0.7)
ps.setParameter("SteeringMethod/Carlike/turningRadius", 0.05)

# STARTING POSITION
robot.setStartingPosition()


### DEFINING CONSTRAINTS
ljs, lock_arm, lock_head, look_at_gripper, tool_gripper = createConstraints(ps, robot)


### BUILDING THE CONSTRAINT GRAPH

# ADDING VIRTUAL HANDLES
print("Adding virtual handles")
virtual_handles = []
for hole in range(len(clusters)):
    part_handles.append("part/virtual_{}".format(str(hole)))
    all_handles.append("part/virtual_{}".format(str(hole)))
    virtual_handles.append("part/virtual_{}".format(str(hole)))

# CONSTRAINT GRAPH FACTORY
print("Building graph")
graph = ConsGraphFactory(robot, ps, all_handles, part_handles,
                         ljs, lock_arm, lock_head, look_at_gripper, tool_gripper)
# INITIALIZATION
cproblem = ps.hppcorba.problem.getProblem()
cgraph = cproblem.getConstraintGraph()
graph.initialize()
# a little test
res, robot.q0, err = graph.generateTargetConfig('move_base', robot.q0, robot.q0)
assert(res)
# GRAPH VALIDATION
print("Validating graph")
ConsGraphValidation(ps, cgraph)


### PROBLEM RESOLUTION

# FOV FILTER
res, q, err = graph.applyNodeConstraints(robot.free, robot.q0)
assert res
robot.setCurrentConfig(q)
oMh, oMd = robot.hppcorba.robot.getJointsPosition(q, ["tiago/hand_tool_link", "driller/base_link"])

# INSTATEPLANNER
armPlanner = createArmPlanner(ps, graph, robot)
basePlanner = createBasePlanner(ps, graph, robot)

# LOAD (OR CREATE) MOBILE BASE ROADMAP
basePlannerUsePrecomputedRoadmap = False
if basePlannerUsePrecomputedRoadmap:
    getMobileBaseRoadmap(basePlanner)


n = 2 # len(virtualHandles)
s.solver.create(n)
s.solver.setErrorThreshold(1e-6)
s.solver.setMaxIterations(30)
for i in range(n):
    s.solver.addConstraint('tiago/gripper grasps driller/handle', i)
    s.solver.addConstraint('part/root_joint', i)
    if i != 0:
        s.solver.addEqualityConstraint('tiago/root_joint', i, 0)

q0 = [robot.q0[i] for i in range(len(robot.q0))]
# q0[:4] = [0, 1, 0, -1]
e1 = 'driller/drill_tip pregrasps part/handle_0004'
res, q1, err = graph.generateTargetConfig(e1, q0, q0)
assert(res)
e2 = 'driller/drill_tip pregrasps part/handle_0330'
q0[:4] = [-0.1, 1, 0, -1]
res, q2, err = graph.generateTargetConfig(e2, q0, q0)
assert(res)

s.solver.addConstraint('driller/drill_tip pregrasps part/handle_0004', 0)
s.solver.addConstraint('driller/drill_tip pregrasps part/handle_0330', 1)
q = q1 + q2
s.solver.setRightHandSideFromVector(q)
res, q3, err = s.solver.solve(q)
dist, closest = s.tools.distanceToMesh(q0, [0,0,0])
















### SOME BASIC INSTRUCTIONS ###

from typing import List, Dict
configType = Dict[str, List[float]]
configListType = List[configType]


### CONFIGURATION GENERATION

# \goal get a collision-free pregrasp configuration for the given handle
# \param handle name of the handle: should be "part/handle_i" or "part/virtual_i" where i is an
#        integer,
# \param restConfig rest configuration of the robot
# \rval q configuration pregrasping handle
def shootPregraspConfig(handle: str, restConfig: List[float]) -> configType:
    res = False
    tries = 0
    while (not res) and (tries<20):
        try: # get a config
            tries+=1
            if tries%10==0:
                print("attempt ", tries)
            q = robot.shootRandomConfig()
            res, q, err = graph.generateTargetConfig("driller/drill_tip pregrasps "+handle, restConfig, q)
            if (res) and (robot.isConfigValid(q)[0] is False): # check it is collision-free
                # print("config not valid")
                res = False
        except Exception as exc:
            print(exc)
            res = False
            pass
    # if res and tries<=100:
    #     print("config generation successfull")
    return {"name": handle+"_pregrasp", "config": q}

# \goal get multiple collision-free pregrasp configurations for the given handle
# \param handle name of the handle: should be "part/handle_i" or "part/virtual_i" where i is an
#        integer,
# \param restConfig rest configuration of the robot
# \param nbConfigs nb of configurations to be generated
# \param configList list where the generated configurations are to be stored
def shootPregraspConfigs(handle: str, restConfig: List[float], nbConfigs: int, configList: configListType) -> None:
    for i in range(nbConfigs):
        configList.append(shootPregraspConfig(handle, restConfig))

print("Shooting configurations on virtual handles")
configsOnVirtual = list()
for handle in virtual_handles:
    # shootPregraspConfigs(handle, robot.q0, 10, configsOnVirtual)
    shootPregraspConfigs(handle, robot.q0, 2, configsOnVirtual)
id = 0
for config in configsOnVirtual:
    config["name"] = "qOnVirtual_"+str(id)
    id+=1


### CHECK REACHABILITY OF REAL HANDLES

# \goal check if a handle can be reached from a configuration, if so the generated configuration is stored
# \param handle name of the handle: should be "part/handle_i" or "part/virtual_i" where i is an
#        integer,
# \param q configuration to start from
# \param qName name of the base configuration
# \param reachMatrix handle reachability matrix of the configurations
# \rval whether handle can be reached from q
def configReachesHandle(handle: str, q: List[float], qName: str, reachMatrix) -> None:
    try:
        res, qh, err = graph.generateTargetConfig("driller/drill_tip > "+handle+" | 0-0_01", q, q)
        if res and robot.isConfigValid(qh)[0]:
            # print("from  ", q, "  to  ", qh)
            reachMatrix[handle][qName] = qh
        else:
            reachMatrix[handle][qName] = None
    except:
        reachMatrix[handle][qName] = None

print("Checking reachability")
reachesHandle = dict()
real_handles = list(filter(lambda x : not x.startswith("part/virtual"), part_handles))
for handle in real_handles:
    reachesHandle[handle] = {}
    for config in configsOnVirtual:
        # configReachesHandle(handle, config["config"], config["name"], reachesHandle)
        reachesHandle[handle][config["name"]] = None

# STRUCTURING THE DATA
print("Structuring all the data")
configHandles = []
handleConfigs = dict()
configClusters = []
nbConfig = -1
for h in real_handles:
    handleConfigs[h] = list()
    for c in configsOnVirtual:
        if reachesHandle[h][c["name"]] is not None:
            nbConfig+=1
            configHandles.append({"hole":h, "q":reachesHandle[h][c["name"]]})
            handleConfigs[h].append(nbConfig)
    configClusters.append(handleConfigs[h])

# MANAGING UNREACHED TASKS
# get handles that are not reached yet
unreached_handles = list()
for h in range(len(configClusters)):
    if configClusters[h]==[]:
        unreached_handles.append(real_handles[h])
# reach them with a new configuration
print("Shooting configurations on unreached handles")
configsOnUnreached = list()
for handle in unreached_handles:
    data = shootPregraspConfig(str(handle), robot.q0)
    data["name"] = str(handle)
    configsOnUnreached.append(data)
# check if the new configurations reach other handles
print("Checking reachability for new configurations")
reachesHandle_bis = dict()
handlesReached = [int(0) for _ in range(len(configsOnUnreached))]
for handle in real_handles:
    reachesHandle_bis[handle] = {}
    for c in range(len(configsOnUnreached)):
        config = configsOnUnreached[c]
        configReachesHandle(handle, config["config"], config["name"], reachesHandle_bis)
        if reachesHandle_bis[handle][config["name"]] is not None:
            handlesReached[c]+=1
# removing configurations that are not versatile enough
print("Removing not useful enough configs")
for _ in range (len(configsOnUnreached)//4):
    toRemove = np.argmin(handlesReached)
    handlesReached.pop(toRemove)
    configsOnUnreached.pop(toRemove)
# adding the obtained configurations to those already generated
print("Structuring the new data")
for h in range(len(real_handles)):
    handle = real_handles[h]
    for c in configsOnUnreached:
        if reachesHandle_bis[handle][c["name"]] is not None:
            nbConfig+=1
            configHandles.append({"hole":handle, "q":reachesHandle_bis[handle][c["name"]]})
            handleConfigs[handle].append(nbConfig)
    configClusters[h] = handleConfigs[handle]
from copy import deepcopy
from math import nan
clustersForDistances = deepcopy(configClusters)
maxClusterSizeIdx = np.argmax([len(c) for c in clustersForDistances])
maxClusterSize = len(clustersForDistances[maxClusterSizeIdx])
for c in clustersForDistances:
    while len(c)<maxClusterSize:
        c.append(-1)


# print("storing clusters and configurations")
# f = open("/home/hvanoverlo/devel/clusters.txt", "w")
# for task in configClusters:
#     for config in task:
#         f.write(str(config)+" ")
#     f.write("\n")
# f.close()
f = open("/tmp/configurations.txt", "w")
for config in configHandles:
    for val in config['q']:
        f.write(str(val)+" ")
    f.write("\n")
f.close()



### GTSP

import yaml
with open("/home/hvanoverlo/devel/jointVelocities.yaml", "r") as stream:
    try:
        jointSpeedsYAML = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        print(exc)
jointSpeeds = list()
for elt in jointSpeedsYAML:
    jointSpeeds.append(float(jointSpeedsYAML[elt]))

print("Computing the distance matrix")
armJoints = list(filter(lambda s:s.startswith("tiago/arm"), robot.jointNames))
armIndices = list(map(lambda j:robot.rankInConfiguration[j], armJoints))
armIndices.append(robot.rankInConfiguration['tiago/torso_lift_joint'])
s.solver.setRobotArmIndices(int(np.min(armIndices)),int(np.max(armIndices)-np.min(armIndices)+1))
# configs = [c['q'] for c in configHandles]
# distances = s.solver.computeDistances(configs, configClusters, jointSpeeds, robot.q0)
# distances = s.solver.computeDistances("/tmp/configurations.txt", clustersForDistances,
#                                       jointSpeeds, robot.q0)
distMatFile = s.solver.computeDistances("/tmp/configurations.txt", clustersForDistances,
                                      jointSpeeds, robot.q0)
distances = list()
with open(distMatFile, 'r') as f:
    distances = [[int(float(num)) for num in line.split(',')] for line in f]

# ROUTING MODEL
print("solving the first GTSP")
# data0 = create_data_model_bis(configHandles, configClusters, jointSpeeds)
# sol0 = list()
# for c in configClusters:
#     sol0+=c
# # data1, sol1 = GTSPiteration(data0, sol0)
# gtspData, firstSol = firstGTSPround(configHandles, configClusters, jointSpeeds, distances)
gtspData, firstSol = firstGTSPround(distances)
# print("second GTSP")
gtspData2, secondSol = GTSPiteration(gtspData, firstSol)
# print("updating arc costs")
# updateGTSP(gtspData2, secondSol, configClusters, configHandles, armPlanner, basePlanner, graph, ps)
# # updateGTSP(data1, sol1, configClusters, configHandles, armPlanner, basePlanner, graph, ps)


# ### MANIPULATE SOLUTION

def getGTSPsol(sol, clusters, configs, f):
    # RETRIEVE GTSP ROUTE
    print("retrieve gtsp sol from tsp one")
    gtspSol = list()
    clustersOrder = list()
    idx = 0
    clusId = nodeIsInCluster(sol[idx], clusters)
    solValid = True
    while solValid and len(gtspSol)<len(clusters):
        if sol[idx+len(clusters[clusId])-1] in clusters[clusId]:
            gtspSol.append(sol[idx])
            clustersOrder.append(clusId)
            idx = idx+len(clusters[clusId])
            clusId = nodeIsInCluster(sol[idx], clusters)
        else:
            print("UNVALID SOLUTION")
            solValid = False
            return
    if solValid:
        gtspSol.append(gtspSol[0])
        clustersOrder.append(clustersOrder[0])
    # WRITE IT TO A FILE
    for i in range(len(gtspSol)):
        f.write(str(clustersOrder[i])+"\n")
        line = "["
        for v in configs[gtspSol[i]]['q']:
            line+=str(v)
            line+=", "
        f.write(line+"]\n")
    return gtspSol, clustersOrder




# USELESS ???
# \param fullConfigs list of the configurations to get the base part of
# \param restConfig rest configuration of the robot
# \rval baseConfigs list of the configurations where the arm is set to its retracted position
def getBaseConfigs(fullConfigs: configListType, restConfig: configType) -> configListType:
    baseConfigs = [restConfig.copy()]*len(fullConfigs)
    for q in baseConfigs:
        for i in range(4):
            q[i] = fullConfigs[i]
    return baseConfigs


# generating a path starting from q0 and pregrasping every hole
# print("directly generating a pregrasp config and going to it")
def generatePathToHandle(handle, paths, initRest, initPregrasp):
    res, q2, err = graph.generateTargetConfig('driller/drill_tip > '+handle+' | 0-0_01', initPregrasp, initPregrasp)
    if res:
        try:
            p1 = wd(armPlanner.computePath(initPregrasp,[q2]))
        except:
            res = False
            # raise Exception("collision during path planning")
        else:
            print("collision-free paths found")
            paths.append(p1)
            return initRest, q2
    else:
        tries = 0
        while res is False and tries<100:
            try:
                tries+=1
                if tries%10==0:
                    print("attempt ", tries)
                q2 = robot.shootRandomConfig()
                res, q2, err = graph.generateTargetConfig("driller/drill_tip pregrasps "+handle, initRest, q2)
                if res:
                    # get the base configuration of the pregrasp configuration
                    q1 = initRest[:]
                    for i in range(4):
                        q1[i] = q2[i]
                    res, q1, err = graph.generateTargetConfig('move_base', initRest, q1)
                    # ps.addConfigToRoadmap(q1)
                    try:
                        p1 = wd(armPlanner.computePath(initPregrasp,[initRest]))
                        p2 = wd(basePlanner.computePath(initRest,[q1]))
                        p3 = wd(armPlanner.computePath(q1,[q2]))
                    except:
                        res = False
                        raise Exception("collision during path planning")
                    else:
                        print("collision-free paths found")
            except:
                res = False
                pass
            else:
                print("path generation successfull")
                paths.append(p1)
                paths.append(p2)
                paths.append(p3)
                return q1, q2

def generateFirstPath(paths, handle, initRest):
    res = False
    tries = 0
    while res is False and tries<100:
        try:
            tries+=1
            if tries%10==0:
                print("attempt ", tries)
            q2 = robot.shootRandomConfig()
            res, q2, err = graph.generateTargetConfig("driller/drill_tip pregrasps "+handle, initRest, q2)
            if res:
                # get the base configuration of the pregrasp configuration
                q1 = initRest[:]
                for i in range(4):
                    q1[i] = q2[i]
                res, q1, err = graph.generateTargetConfig('move_base', initRest, q1)
                # ps.addConfigToRoadmap(q1)
                try:
                    p1 = wd(basePlanner.computePath(initRest,[q1]))
                    p2 = wd(armPlanner.computePath(q1,[q2]))
                    p3 = wd(armPlanner.computePath(q2,[q1]))
                except:
                    res = False
                    raise Exception("collision during path planning")
                else:
                    print("collision-free paths found")
        except:
            res = False
            pass
        else:
            print("path generation successfull")
    paths.append(p1)
    paths.append(p2)
    paths.append(p3)
    return q1, q2

# p = []
# q1, q2 = generateFirstPath(p, part_handles[0], q0)
# for handle in part_handles[1:]: # generate the paths
#     q1, q2 = generatePathToHandle(handle, p, q1, q2)
# ps.client.basic.problem.addPath(p[0]) # display the paths
# for path in p[1:]:
#     ps.client.basic.problem.addPath(path)
#     ps.concatenatePath(0,1)
#     ps.erasePath(1)


# ### PARSE JOINT SPEEDS
# from xml.dom import minidom
# import yaml
# # names of the joints
# robotJoints = robot.jointNames
# robotJoints = robotJoints[:-2]
# for j in range (len(robotJoints)):
#     robotJoints[j] = robotJoints[j][6:]
# # parse the urdf
# tiago = minidom.parse("tiago.urdf")
# data = tiago.documentElement
# # get the max velocities
# maxVelocities = {}
# for joint in data.getElementsByTagName("joint"):
#     if joint.attributes['name'].value in robotJoints:
#         limits = joint.getElementsByTagName('limit')
#         limits = limits[0] if len(limits) > 0 else None
#         if limits is not None and limits.hasAttribute('velocity'):
#             vmax = limits.getAttribute('velocity')
#             maxVelocities.update({joint.attributes['name'].value : vmax})
# # put them in a yaml
# with open('/home/hvanoverlo/devel/jointVelocities.yaml', 'w') as file:
#     documents = yaml.dump(maxVelocities, file)



# ### SOME MORE STUFF
# print(graph.displayEdgeConstraints(name of edge))
# pour recuperer l'erreur sur chaque composante entre q et la feuille souhaitee
# graph.getConfigErrorForEdgeLeaf(edgeId, leafConfig, q)

# InStatePlanner is at devel/hpp/src/agimus-demos/src/agimus_demos
# ccs = basePlanner.croadmap.getConnectedComponents()
