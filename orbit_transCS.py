# -*- coding: utf-8 -*-
"""
Created on Mon Aug 11 13:04:55 2014

@author: hmendoza, jl
"""

from casadi import *
from casadi.tools import *
from pylab import *
import matplotlib.pyplot as plt


N = 50
nx = 4 # State size
nu = 2 # Control size

u = SX.sym("u",nu) # Thrust Controls
x = SX.sym("x",nx) # States [x,theta, x_dot, theta_dot]

# Create TPV as equal bounds
x0 = array([7000,0,0,1.0781e-3]) # Initial State
u0 = array([0,0])
xN = array([8000,2*pi,0,8.82337e-4]) # Final State (Stable?)

#System dynamics
G = 6.67384e-11
mu =  3.986012e5
#m1 = 0 # Planet's mass
#m2 = 0 # Satellite mass

A = SX.zeros((nx,nx))
B = SX.zeros((nx,nu))

A[0,2] = 1; A[1,3] = 1;
A[2,0] = -mu/(x[0]**3);
A[2,3] = x[0]*x[3];
A[3,2] = -(2.*x[3])/x[0];

B[2,0] = 1; B[3,1] = 1./x[0]

xdot = mul(A,x) + mul(B,u)
qdot = u[0]**2 + u[1]**2

orbODE = SXFunction([x,u],[xdot,qdot])
orbODE.setOption("name","orbODE")
orbODE.init()

#Simulation of Orbit with r = R1
U = MX.sym("U",nu)
X0 = MX.sym("X",nx)
T0 = MX.sym("T")

# Define NLP variables
W = struct_symMX([
      (
        entry("X",shape=(nx,1),repeat=N+1),
        entry("U",shape=(2,1),repeat=N)
      ),
      entry("T")
])

DT = T0
XF = X0
QF = 0
R_terms = []
for j in range(N):
    [k1, k1q] = orbODE([XF,             U])
    [k2, k2q] = orbODE([XF + DT/2 * k1, U])
    [k3, k3q] = orbODE([XF + DT/2 * k2, U])
    [k4, k4q] = orbODE([XF + DT   * k3, U])
    XF += DT/6*(k1   + 2*k2   + 2*k3   + k4)
    QF += DT/6*(k1q  + 2*k2q  + 2*k3q  + k4q)
    #R_terms.append(XF)
    #R_terms.append(U)
    
#R_terms = vertcat(R_terms) # Concatenate terms
orbSim = MXFunction([X0,U,T0],[XF,QF])
orbSim.setOption("name","orbSim")
orbSim.init()


# NLP constraints
g = []

J = 0

# Terms in the Gauss-Newton objective
#R = []

# Build up a graph of integrator calls
for k in range(N):
    # Call the integrator
    [x_next_k, qF] = orbSim([W["X",k], W["U",k], W["T"]/float(N)])

    # Append continuity constraints
    g.append(x_next_k - W["X",k+1])

    # Append Terminal Cost
    J += qF
    # Append Gauss-Newton objective terms
    #R.append(R_terms)

# Concatenate constraints
g = vertcat(g)

# Create "Upper and Lower" Boundaries for Constraints
gmin = zeros(g.shape)
gmax = zeros(g.shape)

# Concatenate terms in Gauss-Newton objective
#R = vertcat(R)

# Objective function
#obj = mul(R.T,R)/2

# Construct and populate the vectors with
# upper and lower simple bounds
w_min = W(-inf)
w_max = W(inf)

# Control bounds
w_min["U",:] = array([-1000,-1000])
w_max["U",:] = array([1000, 1000])

# Initial Guess - Simulation
w0 = W(0); w0["X",0] = x0; w0["U",0] = u0
w0["T"] = 39.0
orbSim.setInput(w0["U",0],1)
orbSim.setInput(w0["T"]/float(N),2)

for l in range(N):
    orbSim.setInput(w0["X",l],0)
    orbSim.evaluate()
    w0["X",l+1] = orbSim.getOutput(0)

#Time Optimality
f = W["T"] + J

# Initial Conditions
w_min["X",:,0] = 6999.5
w_max["X",:,0] = 8000.5
w_min["T"] = -0.01 # Dummy Value - I have no idea what I'm doing

w_min["X",0] = w_max["X",0] = x0
w_max["T"] = 500.0

# Terminal Conditions
w_min["X",-1] = w_max["X",-1] = xN
w_min["X",-1,1] = 0
w_max["X",-1,1] = 6*pi

# Create an NLP solver object
nlp = MXFunction(nlpIn(x=W),nlpOut(f=f,g=g))
nlp_solver = NlpSolver("ipopt", nlp)
nlp_solver.setOption("linear_solver", "mumps")
nlp_solver.setOption("max_iter",200)
nlp_solver.init()
nlp_solver.setInput(w0,"x0")
nlp_solver.setInput(w_max,"ubx")
nlp_solver.setInput(w_min,"lbx")
nlp_solver.setInput(gmin,"ubg")
nlp_solver.setInput(gmax,"lbg")

# Solve the Problem
nlp_solver.evaluate()

# Retrieve to plot
sol_W = W(nlp_solver.getOutput("x"))
u_opt_r = sol_W["U",:,0]
u_opt_t = sol_W["U",:,1]
r_opt = sol_W["X",:,0]
theta_opt = sol_W["X",:,1]
px_opt = r_opt * cos(theta_opt)
py_opt = r_opt * sin(theta_opt)
tf = sol_W["T"]; print tf
fig1 = plt.figure(1)
plt.clf()
plt.step(linspace(0,tf,N),u_opt_r,'b-.',linspace(0,tf,N),u_opt_t,'r-.')
plt.title("Orbit Transfer Control - multiple shooting")
plt.xlabel('time')
plt.legend(['u_r','u_t'])
plt.grid()
plt.show()
fig1.savefig('Orbit_Control_TJ.jpg')
fig2 = plt.figure(2)
plt.plot(linspace(0,tf,N+1),r_opt,'r.-')
plt.title("Orbit - Trajectory")
plt.xlabel('time')
plt.ylabel('r [m]')
plt.grid()
plt.show()
fig2.savefig('Orbit_Radius_TJ.jpg')
fig3 = plt.figure(3)
plt.plot(px_opt, py_opt,'g.-')
plt.title("Orbit - Trajectory in x vs y")
plt.xlabel('Position in x [m]')
plt.ylabel('Position in y [m]')
plt.grid()
plt.show()
fig3.savefig('Orbit_XY_TJ.jpg')