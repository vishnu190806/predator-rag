import json

questions = [
    # Category A: NCERT Theory Questions (1-20)
    {
        "id": 1,
        "category": "NCERT Theory",
        "question": "State the Work-Energy Theorem for a variable force.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.6 THE WORK-ENERGY THEOREM FOR A VARIABLE FORCE",
        "ground_truth_answer": "The change in kinetic energy of a particle is equal to the work done on it by the net force: Kf - Ki = W = \\int_{x_i}^{x_f} F(x) dx.",
        "expected_formulas": ["K_f - K_i = W", "\\int F dx"]
    },
    {
        "id": 2,
        "category": "NCERT Theory",
        "question": "Define conservative and non-conservative forces with examples.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "A force is conservative if the work done by it on a particle that moves between two points depends only on these points and not on the path taken, or if the work done in a closed path is zero (e.g., gravitational force, spring force). Otherwise, it is non-conservative (e.g., friction, viscous drag).",
        "expected_formulas": []
    },
    {
        "id": 3,
        "category": "NCERT Theory",
        "question": "State the law of conservation of mechanical energy.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "The total mechanical energy (K + V) of a system remains constant if the forces doing work on it are conservative.",
        "expected_formulas": ["E = K + V", "K_i + V_i = K_f + V_f"]
    },
    {
        "id": 4,
        "category": "NCERT Theory",
        "question": "What is the relation between the torque and angular momentum of a rotating body?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7  TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "The rate of change of angular momentum of a system of particles about a point is equal to the sum of external torques acting on the system about that point: dL/dt = \\tau.",
        "expected_formulas": ["\\tau = \\frac{dL}{dt}"]
    },
    {
        "id": 5,
        "category": "NCERT Theory",
        "question": "State Kepler's three laws of planetary motion.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.2  KEPLER’S LAWS**",
        "ground_truth_answer": "1. Law of Orbits: All planets move in elliptical orbits with the Sun at one focus. 2. Law of Areas: The line joining a planet to the Sun sweeps out equal areas in equal intervals of time (conservation of angular momentum). 3. Law of Periods: The square of the time period of revolution of a planet is proportional to the cube of the semi-major axis of its elliptical orbit (T^2 \\propto a^3).",
        "expected_formulas": ["T^2 \\propto a^3"]
    },
    {
        "id": 6,
        "category": "NCERT Theory",
        "question": "State the Universal Law of Gravitation.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.3  UNIVERSAL LAW OF GRAVITATION**",
        "ground_truth_answer": "Every body in the universe attracts every other body with a force which is directly proportional to the product of their masses and inversely proportional to the square of the distance between them: F = G * m1 * m2 / r^2.",
        "expected_formulas": ["F = G \\frac{m_1 m_2}{r^2}"]
    },
    {
        "id": 7,
        "category": "NCERT Theory",
        "question": "Explain the physical significance of the moment of inertia.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "Moment of inertia (I) is the rotational analogue of mass in linear motion. It measures a body's resistance to change in its rotational motion and depends on the distribution of mass relative to the axis of rotation.",
        "expected_formulas": ["I = \\sum m_i r_i^2"]
    },
    {
        "id": 8,
        "category": "NCERT Theory",
        "question": "What is the escape speed of a body and how does it depend on the mass of the body?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.8  ESCAPE SPEED",
        "ground_truth_answer": "Escape speed is the minimum speed required for a body to escape from the gravitational field of a planet: v_e = \\sqrt{2GM/R} = \\sqrt{2gR}. It depends on the mass and radius of the planet but is independent of the mass of the escaping body.",
        "expected_formulas": ["v_e = \\sqrt{\\frac{2GM}{R}}"]
    },
    {
        "id": 9,
        "category": "NCERT Theory",
        "question": "Define the coefficient of restitution in collisions.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2  Collisions in One Dimension**",
        "ground_truth_answer": "The coefficient of restitution (e) is the ratio of the relative velocity of separation to the relative velocity of approach after and before a collision: e = (v_2f - v_1f) / (v_1i - v_2i). For elastic collisions e = 1, for completely inelastic collisions e = 0.",
        "expected_formulas": ["e = \\frac{v_{2f} - v_{1f}}{v_{1i} - v_{2i}}"]
    },
    {
        "id": 10,
        "category": "NCERT Theory",
        "question": "What is the difference between elastic and inelastic collisions?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.11  COLLISIONS",
        "ground_truth_answer": "In an elastic collision, both total linear momentum and total kinetic energy are conserved. In an inelastic collision, total linear momentum is conserved but total kinetic energy is not conserved (part of it is converted to heat, deformation, etc.).",
        "expected_formulas": []
    },
    {
        "id": 11,
        "category": "NCERT Theory",
        "question": "Explain the center of mass of a system of particles.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "The center of mass of a system of particles is the average position of all parts of the system, weighted according to their masses. It represents the point where the entire mass of the system can be assumed to be concentrated for describing external translational motion: R = \\sum m_i r_i / M.",
        "expected_formulas": ["R = \\frac{\\sum m_i r_i}{M}"]
    },
    {
        "id": 12,
        "category": "NCERT Theory",
        "question": "Explain the vector product of two vectors and write its properties.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.5  VECTOR PRODUCT OF TWO VECTORS**",
        "ground_truth_answer": "The vector product (or cross product) of two vectors A and B is a vector C perpendicular to both, with magnitude C = A*B*sin\\theta. It is non-commutative (A x B = -B x A) and distributive over addition.",
        "expected_formulas": ["\\vec{A} \\times \\vec{B} = A B \\sin \\theta \\hat{n}"]
    },
    {
        "id": 13,
        "category": "NCERT Theory",
        "question": "Explain angular acceleration and how it relates to linear acceleration.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.6.1 Angular acceleration**",
        "ground_truth_answer": "Angular acceleration (alpha) is the rate of change of angular velocity: alpha = dw/dt. For rotation about a fixed axis, the tangential component of linear acceleration is related to angular acceleration by a_t = r * alpha.",
        "expected_formulas": ["\\alpha = \\frac{d\\omega}{dt}", "a_t = r \\alpha"]
    },
    {
        "id": 14,
        "category": "NCERT Theory",
        "question": "Define gravitational potential energy and write its expression.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "Gravitational potential energy of a system of two masses is the energy stored in the system due to their mutual gravitational attraction. It is equal to the work done in bringing the masses from infinity to their current positions: V(r) = -G M m / r.",
        "expected_formulas": ["V(r) = -\\frac{G M m}{r}"]
    },
    {
        "id": 15,
        "category": "NCERT Theory",
        "question": "What are geostationary satellites and what is their time period?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9  EARTH SATELLITES**",
        "ground_truth_answer": "Geostationary satellites are satellites orbiting the Earth in equatorial orbits with a time period of exactly 24 hours (matching Earth's rotation), so they appear stationary relative to any point on Earth.",
        "expected_formulas": ["T = 24 \\text{ hours}"]
    },
    {
        "id": 16,
        "category": "NCERT Theory",
        "question": "Define power and write its SI unit.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10  POWER",
        "ground_truth_answer": "Power is defined as the rate at which work is done or energy is transferred. SI unit of power is the watt (W), where 1 W = 1 J/s. Formula: P = dW/dt = F.v.",
        "expected_formulas": ["P = \\frac{dW}{dt}", "P = F \\cdot v"]
    },
    {
        "id": 17,
        "category": "NCERT Theory",
        "question": "What is a spring force and how is it related to displacement?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9  THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "A spring force is a restoring force exerted by a stretched or compressed spring. According to Hooke's Law, it is proportional to the displacement from the equilibrium position and acts in the opposite direction: F_s = -k x.",
        "expected_formulas": ["F_s = -k x"]
    },
    {
        "id": 18,
        "category": "NCERT Theory",
        "question": "Define the energy of an orbiting satellite and write its expression.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.10  ENERGY OF AN ORBITING SATELLITE**",
        "ground_truth_answer": "The total energy of an orbiting satellite is the sum of its kinetic and potential energies: E = K + V = G M m / (2r) - G M m / r = -G M m / (2r).",
        "expected_formulas": ["E = -\\frac{G M m}{2r}"]
    },
    {
        "id": 19,
        "category": "NCERT Theory",
        "question": "How does the acceleration due to gravity g vary with altitude above the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "The acceleration due to gravity g(h) at a height h above the Earth's surface decreases with height: g(h) = g_E / (1 + h/R_E)^2. For h << R_E, it approximates to g(h) \\approx g_E * (1 - 2h/R_E).",
        "expected_formulas": ["g(h) = g_E (1 - \\frac{2h}{R_E})"]
    },
    {
        "id": 20,
        "category": "NCERT Theory",
        "question": "How does the acceleration due to gravity g vary with depth below the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "The acceleration due to gravity g(d) at a depth d below the Earth's surface decreases linearly with depth: g(d) = g_E * (1 - d/R_E). At the center of the Earth (d = R_E), g becomes zero.",
        "expected_formulas": ["g(d) = g_E (1 - \\frac{d}{R_E})"]
    },

    # Category B: NCERT Exercise Questions (21-40)
    {
        "id": 21,
        "category": "NCERT Exercise",
        "question": "A body of mass 2 kg initially at rest moves under the action of an applied horizontal force of 7 N on a table with coefficient of kinetic friction = 0.1. Compute the work done by the applied force in 10 s.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "Frictional force f = \\mu * m * g = 0.1 * 2 * 9.8 = 1.96 N. Net acceleration a = (F - f) / m = (7 - 1.96) / 2 = 2.52 m/s^2. Displacement d = 0.5 * a * t^2 = 0.5 * 2.52 * 10^2 = 126 m. Work done by applied force W_F = F * d = 7 * 126 = 882 J.",
        "expected_formulas": ["f = \\mu m g", "d = \\frac{1}{2} a t^2", "W = F d"]
    },
    {
        "id": 22,
        "category": "NCERT Exercise",
        "question": "A pump on the ground floor of a building can pump up water to fill a tank of volume 30 m^3 in 15 min. If the tank is 40 m above the ground, and the efficiency of the pump is 30%, how much electric power is consumed by the pump?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10  POWER",
        "ground_truth_answer": "Mass of water m = V * density = 30 * 1000 = 30000 kg. Time t = 15 * 60 = 900 s. Useful work done W = m * g * h = 30000 * 9.8 * 40 = 1.176 * 10^7 J. Output Power P_out = W/t = 1.176 * 10^7 / 900 = 13.07 kW. Input Power P_in = P_out / efficiency = 13.07 / 0.3 = 43.6 kW.",
        "expected_formulas": ["P_{out} = \\frac{mgh}{t}", "P_{in} = \\frac{P_{out}}{\\eta}"]
    },
    {
        "id": 23,
        "category": "NCERT Exercise",
        "question": "A bob of mass m is suspended by a light string of length L. It is imparted a horizontal velocity v0 at the lowest point. What is the minimum velocity v0 required for the bob to complete a full vertical circle?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "Minimum velocity required at the lowest point to complete a full vertical circle is v_0 = \\sqrt{5gL}.",
        "expected_formulas": ["v_0 = \\sqrt{5gL}"]
    },
    {
        "id": 24,
        "category": "NCERT Exercise",
        "question": "A particle of mass m is moving in a horizontal circle of radius r under a centripetal force equal to -k/r^2. What is the total energy of the particle?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "Centripetal force F_c = m v^2 / r = k / r^2 => m v^2 = k / r. Kinetic Energy K = 0.5 * m * v^2 = k / (2r). Potential Energy V = -k/r. Total Energy E = K + V = k/(2r) - k/r = -k/(2r).",
        "expected_formulas": ["K = \\frac{1}{2} m v^2", "E = K + V"]
    },
    {
        "id": 25,
        "category": "NCERT Exercise",
        "question": "Three identical spheres, each of mass M and radius R, are placed touching each other on a horizontal table. Find the position of the center of mass of the system.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "Since the spheres are identical and touch each other, their centers form an equilateral triangle of side 2R. The center of mass lies at the centroid of this equilateral triangle formed by their centers.",
        "expected_formulas": []
    },
    {
        "id": 26,
        "category": "NCERT Exercise",
        "question": "A solid cylinder of mass 20 kg rotates about its axis with angular speed 100 rad/s. The radius of the cylinder is 0.25 m. What is the kinetic energy of rotation of the cylinder?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "Moment of inertia of a solid cylinder I = 0.5 * M * R^2 = 0.5 * 20 * (0.25)^2 = 0.625 kg m^2. Rotational Kinetic Energy K = 0.5 * I * w^2 = 0.5 * 0.625 * 100^2 = 3125 J.",
        "expected_formulas": ["I = \\frac{1}{2} M R^2", "K = \\frac{1}{2} I \\omega^2"]
    },
    {
        "id": 27,
        "category": "NCERT Exercise",
        "question": "A child stands at the center of a turntable with his two arms outstretched. The turntable is set rotating with an angular speed of 40 rev/min. How much is the angular speed of the child if he folds his hands back and thereby reduces his moment of inertia to 2/5 times the initial value?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12.1 Conservation of angular momentum**",
        "ground_truth_answer": "By conservation of angular momentum: I_1 * w_1 = I_2 * w_2. Since I_2 = (2/5) * I_1, we have w_2 = (I_1 / I_2) * w_1 = (5/2) * 40 = 100 rev/min.",
        "expected_formulas": ["I_1 \\omega_1 = I_2 \\omega_2"]
    },
    {
        "id": 28,
        "category": "NCERT Exercise",
        "question": "Find the center of mass of a system of two particles separated by distance d.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "If the first mass m1 is at x=0, the second mass m2 is at x=d. Center of mass X = (m2 * d) / (m1 + m2) from m1.",
        "expected_formulas": ["X = \\frac{m_2 d}{m_1 + m_2}"]
    },
    {
        "id": 29,
        "category": "NCERT Exercise",
        "question": "An artificial satellite is orbiting around the Earth in a circular orbit of radius r. If its time period is T, what is the relation between T and r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9  EARTH SATELLITES**",
        "ground_truth_answer": "According to Kepler's third law, the square of the time period T is proportional to the cube of the radius of the orbit r: T^2 \\propto r^3.",
        "expected_formulas": ["T^2 \\propto r^3"]
    },
    {
        "id": 30,
        "category": "NCERT Exercise",
        "question": "A satellite is placed in a circular orbit of radius R around the earth. What is the percentage change in the kinetic energy of the satellite if it is moved to a circular orbit of radius 2R?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.10  ENERGY OF AN ORBITING SATELLITE**",
        "ground_truth_answer": "Kinetic energy of a satellite in circular orbit is K = G*M*m / (2r). K1 = G*M*m / (2R), K2 = G*M*m / (4R) = 0.5 * K1. Change in KE = K2 - K1 = -0.5 * K1, representing a 50% decrease.",
        "expected_formulas": ["K = \\frac{GMm}{2r}"]
    },
    {
        "id": 31,
        "category": "NCERT Exercise",
        "question": "A mass of 6 kg is suspended by a rope of length 2 m from the ceiling. A force of 50 N in the horizontal direction is applied at the midpoint of the rope. What is the angle the rope makes with the vertical in equilibrium? (g = 10 m/s^2)",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "At midpoint, horizontal force is 50 N, and weight of lower part of rope + mass is 60 N. For equilibrium, tan \\theta = F_horizontal / W = 50 / 60 = 5/6 => \\theta = tan^-1(5/6) \\approx 40 degrees.",
        "expected_formulas": ["\\tan \\theta = \\frac{F}{W}"]
    },
    {
        "id": 32,
        "category": "NCERT Exercise",
        "question": "A bullet of mass 0.012 kg and horizontal speed 70 m/s strikes a block of wood of mass 0.4 kg and instantly comes to rest with respect to the block. What is the common speed of the block and the bullet after the collision?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2  Collisions in One Dimension**",
        "ground_truth_answer": "By conservation of linear momentum: m * u = (m + M) * v. Here m = 0.012 kg, u = 70 m/s, M = 0.4 kg. v = (0.012 * 70) / (0.012 + 0.4) = 2.04 m/s.",
        "expected_formulas": ["m u = (m + M) v"]
    },
    {
        "id": 33,
        "category": "NCERT Exercise",
        "question": "A trolley of mass 300 kg carrying a sandbag of 25 kg is moving uniformly with a speed of 27 km/h on a frictionless track. After a while, sand starts leaking out of a hole on the trolley's floor at the rate of 0.05 kg/s. What is the speed of the trolley after the entire sandbag is empty?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.11  COLLISIONS",
        "ground_truth_answer": "Since sand leaks vertically downwards relative to the trolley, it carries no horizontal force or momentum change for the trolley. Thus, no external horizontal force acts on the system, and the speed of the trolley remains constant at 27 km/h (or 7.5 m/s).",
        "expected_formulas": []
    },
    {
        "id": 34,
        "category": "NCERT Exercise",
        "question": "A body of mass 0.5 kg travels in a straight line with velocity v = a x^(3/2) where a = 5 m^(-1/2) s^(-1). What is the work done by the net force during its displacement from x = 0 to x = 2 m?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "At x = 0, v_i = 0. At x = 2 m, v_f = 5 * 2^(3/2) = 14.14 m/s. Work done W = \\Delta K = 0.5 * m * (v_f^2 - v_i^2) = 0.5 * 0.5 * 200 = 50 J.",
        "expected_formulas": ["W = \\frac{1}{2} m (v_f^2 - v_i^2)"]
    },
    {
        "id": 35,
        "category": "NCERT Exercise",
        "question": "A 1 kg block situated on a rough incline is connected to a spring of spring constant 100 N/m. The block is released from rest when the spring is unstretched. Find the maximum displacement of the block down the incline.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9  THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "By energy conservation: Loss in gravitational PE = Gain in elastic PE + Work done against friction. m g x sin\\theta = 0.5 k x^2 + \\mu m g x cos\\theta => x = 2 m g (sin\\theta - \\mu cos\\theta) / k.",
        "expected_formulas": ["V_s = \\frac{1}{2} k x^2"]
    },
    {
        "id": 36,
        "category": "NCERT Exercise",
        "question": "What is the moment of inertia of a uniform thin rod of mass M and length L about an axis perpendicular to the rod and passing through one of its ends?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "Using standard results and parallel axis theorem: I_end = M L^2 / 3.",
        "expected_formulas": ["I = \\frac{1}{3} M L^2"]
    },
    {
        "id": 37,
        "category": "NCERT Exercise",
        "question": "State the law of conservation of angular momentum with an example.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12.1 Conservation of angular momentum**",
        "ground_truth_answer": "If the net external torque acting on a system is zero, its total angular momentum remains constant: L = constant (or I1 w1 = I2 w2). Example: A figure skater spins faster when they pull in their arms.",
        "expected_formulas": ["I_1 \\omega_1 = I_2 \\omega_2"]
    },
    {
        "id": 38,
        "category": "NCERT Exercise",
        "question": "A particle of mass m is moving with constant angular speed w in a circle of radius r. What is its kinetic energy in terms of moment of inertia?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "Moment of inertia I = m * r^2. Rotational Kinetic energy K = 0.5 * I * w^2.",
        "expected_formulas": ["K = \\frac{1}{2} I \\omega^2"]
    },
    {
        "id": 39,
        "category": "NCERT Exercise",
        "question": "Find the potential energy of a system of four particles, each of mass m, placed at the vertices of a square of side l.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "There are 6 pairs. PE = -G * m^2 / l * (4 + \\sqrt{2}).",
        "expected_formulas": ["U = -\\sum \\frac{G m_i m_j}{r_{ij}}"]
    },
    {
        "id": 40,
        "category": "NCERT Exercise",
        "question": "A rocket is fired vertically with a speed of 5 km/s from the earth's surface. How far from the earth does the rocket go before coming to rest? (Radius of Earth = 6400 km)",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "By energy conservation: 0.5 * m * v^2 - G * M_E * m / R_E = -G * M_E * m / (R_E + h). Height h = R_E * (v^2 / (2gR_E - v^2)) \\approx 1600 km.",
        "expected_formulas": ["\\frac{1}{2} m v^2 - \\frac{G M_E m}{R_E} = -\\frac{G M_E m}{R_E + h}"]
    },

    # Category C: JEE Main Style (41-60)
    {
        "id": 41,
        "category": "JEE Main",
        "question": "A block of mass m is projected up a rough inclined plane of inclination 30 degrees with a kinetic energy K. If the coefficient of friction is 0.2, the work done against friction before it comes to rest is?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "Force of friction f = \\mu * m * g * cos 30. Distance s = K / (m*g*sin 30 + f). Work done against friction W_f = f * s = K * (\\mu * cos 30) / (sin 30 + \\mu * cos 30) \\approx 0.257 * K.",
        "expected_formulas": ["f = \\mu m g \\cos \\theta", "W_f = f s"]
    },
    {
        "id": 42,
        "category": "JEE Main",
        "question": "A body of mass 2 kg is driven by a constant power of 1 W. If it starts from rest, what is the distance covered by the body in 9 seconds?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10  POWER",
        "ground_truth_answer": "0.5 * m * v^2 = P * t => v = \\sqrt{2 P t / m}. Distance s = \\int v dt = (2/3) * t^(3/2) * \\sqrt{2P/m}. For m=2, P=1, t=9: s = 18 m.",
        "expected_formulas": ["v = \\sqrt{\\frac{2Pt}{m}}", "s = \\frac{2}{3} \\sqrt{\\frac{2P}{m}} t^{3/2}"]
    },
    {
        "id": 43,
        "category": "JEE Main",
        "question": "A particle of mass m is attached to a string of length l and is projected horizontally with velocity sqrt(3gl) from the bottom-most point. Find the maximum height reached by the particle above the bottom-most point.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "The string slacks when tension T = 0, which occurs at height h = 4/3 * l (where cos\\theta = -1/3). Velocity at this point is v = \\sqrt{gl/3}. Projectile motion: H_max = 4/3*l + (v*sin\\theta)^2 / (2g) = 40/27 * l.",
        "expected_formulas": ["T = \\frac{m v^2}{l} + m g \\cos \\theta"]
    },
    {
        "id": 44,
        "category": "JEE Main",
        "question": "Two bodies of masses m1 and m2 are connected by a light spring of force constant k. They are placed on a smooth horizontal surface. If they are pulled apart and released, find the frequency of oscillation of the system.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9  THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "Oscillation with reduced mass \\mu = (m1 * m2) / (m1 + m2). Frequency f = 1 / (2*pi) * \\sqrt{k/\\mu}.",
        "expected_formulas": ["f = \\frac{1}{2\\pi}\\sqrt{\\frac{k}{\\mu}}"]
    },
    {
        "id": 45,
        "category": "JEE Main",
        "question": "The center of mass of three particles of masses 1 kg, 2 kg, and 3 kg lies at the point (1, 2, 3). If another particle of mass 4 kg is placed at the origin, find the coordinates of the new center of mass.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "R = (M1*R1 + M2*R2) / (M1 + M2) = (6 * (1, 2, 3) + 4 * (0,0,0)) / 10 = (0.6, 1.2, 1.8).",
        "expected_formulas": ["R = \\frac{M_1 R_1 + M_2 R_2}{M_1 + M_2}"]
    },
    {
        "id": 46,
        "category": "JEE Main",
        "question": "Calculate the center of mass of three particles of equal mass placed at the corners of an equilateral triangle.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "By symmetry, the center of mass of three equal masses placed at the vertices of an equilateral triangle lies at the centroid of the triangle.",
        "expected_formulas": []
    },
    {
        "id": 47,
        "category": "JEE Main",
        "question": "A constant torque of 20 N m is applied to a wheel of moment of inertia 2 kg m^2. Find its angular acceleration.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.11 DYNAMICS OF ROTATIONAL MOTION ABOUT A FIXED AXIS**",
        "ground_truth_answer": "\\tau = I * alpha => alpha = \\tau / I = 20 / 2 = 10 rad/s^2.",
        "expected_formulas": ["\\tau = I \\alpha"]
    },
    {
        "id": 48,
        "category": "JEE Main",
        "question": "A particle of mass m is moving with constant velocity v parallel to the x-axis at a distance y = d. What is the angular momentum of the particle about the origin as a function of time?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7  TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "L = r x p. Magnitude is constant: L = m * v * d directed along the negative z-axis.",
        "expected_formulas": ["L = r \\times p", "L = m v d"]
    },
    {
        "id": 49,
        "category": "JEE Main",
        "question": "If the distance between the Earth and the Sun were halved, what would be the duration of the year in days?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.2  KEPLER’S LAWS**",
        "ground_truth_answer": "T2 = T1 / \\sqrt{8} \\approx 129 days.",
        "expected_formulas": ["T^2 \\propto R^3"]
    },
    {
        "id": 50,
        "category": "JEE Main",
        "question": "The gravitational potential energy of a body at a distance r from the center of Earth is U. Find the gravitational force acting on the body at that point.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "F = -dU/dr = -G * M * m / r^2.",
        "expected_formulas": ["F = -\\frac{dU}{dr}"]
    },
    {
        "id": 51,
        "category": "JEE Main",
        "question": "An elastic collision occurs between a moving body of mass M and a stationary body of mass m. What is the fraction of kinetic energy transferred to the stationary body if M = 3m?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2  Collisions in One Dimension**",
        "ground_truth_answer": "Fraction transferred = 4 * M * m / (M + m)^2 = 4 * 3 * m^2 / 16m^2 = 75%.",
        "expected_formulas": ["\\frac{\\Delta K}{K} = \\frac{4 M m}{(M+m)^2}"]
    },
    {
        "id": 52,
        "category": "JEE Main",
        "question": "A spring of force constant k is cut into two equal halves. What is the force constant of each half?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9  THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "Stiffness is inversely proportional to length, so k_half = 2k.",
        "expected_formulas": ["k \\propto \\frac{1}{L}"]
    },
    {
        "id": 53,
        "category": "JEE Main",
        "question": "A body of mass m is thrown vertically upwards with a velocity equal to half the escape velocity from the surface of the Earth. What is the maximum height attained by the body?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "Using energy conservation: 0.5 * m * v^2 - G * M * m / R = -G * M * m / (R + h) with v = 0.5 * \\sqrt{2gR}. Height h = R/3.",
        "expected_formulas": ["\\frac{1}{2} m v^2 - \\frac{GMm}{R} = -\\frac{GMm}{R+h}"]
    },
    {
        "id": 54,
        "category": "JEE Main",
        "question": "Find the moment of inertia of a uniform circular disc of mass M and radius R about an axis passing through its center and perpendicular to its plane.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "I = 0.5 * M * R^2.",
        "expected_formulas": ["I = \\frac{1}{2} M R^2"]
    },
    {
        "id": 55,
        "category": "JEE Main",
        "question": "A sphere of mass M collides elastically with another identical sphere at rest, such that the collision is oblique. What is the angle between their velocities after the collision?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.3  Collisions in Two Dimensions**",
        "ground_truth_answer": "For an elastic oblique collision of identical masses where one is initially at rest, the velocities are perpendicular after collision (90 degrees).",
        "expected_formulas": ["\\vec{v}_1 \\cdot \\vec{v}_2 = 0"]
    },
    {
        "id": 56,
        "category": "JEE Main",
        "question": "A planet orbits the Sun in an elliptical path. If the ratio of maximum to minimum distance of the planet from the Sun is 3, what is the ratio of maximum to minimum speed of the planet?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.2  KEPLER’S LAWS**",
        "ground_truth_answer": "By conservation of angular momentum: v_max / v_min = r_max / r_min = 3.",
        "expected_formulas": ["v_{max} r_{min} = v_{min} r_{max}"]
    },
    {
        "id": 57,
        "category": "JEE Main",
        "question": "If the acceleration due to gravity at a height h above the Earth's surface is same as that at a depth d below the surface (for small h and d), what is the relation between h and d?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "g(h) = g * (1 - 2h/R), g(d) = g * (1 - d/R). Equating gives d = 2h.",
        "expected_formulas": ["d = 2h"]
    },
    {
        "id": 58,
        "category": "JEE Main",
        "question": "Define the principle of moments for a lever in equilibrium.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.8.1 Principle of moments**",
        "ground_truth_answer": "For rotational equilibrium of a lever, the sum of clockwise moments equals the sum of anticlockwise moments: Load * Load Arm = Effort * Effort Arm.",
        "expected_formulas": ["F_1 d_1 = F_2 d_2"]
    },
    {
        "id": 59,
        "category": "JEE Main",
        "question": "Find the gravitational potential at the center of a thin uniform semi-circular ring of mass M and radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "V = -G * M / R.",
        "expected_formulas": ["V = -\\frac{G M}{R}"]
    },
    {
        "id": 60,
        "category": "JEE Main",
        "question": "A uniform disc of mass M and radius R is rotating with angular velocity w. If another identical disc is placed coaxially and gently on top of it, what is the common angular velocity of the two discs after they start rotating together?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12.1 Conservation of angular momentum**",
        "ground_truth_answer": "By conservation of angular momentum: I * w = (I + I) * w_common => w_common = w / 2.",
        "expected_formulas": ["I_1 \\omega_1 + I_2 \\omega_2 = (I_1 + I_2) \\omega"]
    },

    # Category D: NEET Style (61-80)
    {
        "id": 61,
        "category": "NEET",
        "question": "Under what condition is the work done by a force zero?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "Work done is zero when force is zero, displacement is zero, or the angle between force and displacement is 90 degrees.",
        "expected_formulas": ["W = F d \\cos \\theta"]
    },
    {
        "id": 62,
        "category": "NEET",
        "question": "What is the angle between the force and displacement for maximum work done?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "Maximum work occurs when the angle between force and displacement is 0 degrees.",
        "expected_formulas": ["W = F d \\cos \\theta"]
    },
    {
        "id": 63,
        "category": "NEET",
        "question": "A body of mass 5 kg is raised through a height of 10 m. What is the work done by the gravitational force? (g = 10 m/s^2)",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3  WORK",
        "ground_truth_answer": "Work done by gravity = -m * g * h = -5 * 10 * 10 = -500 J.",
        "expected_formulas": ["W = -mgh"]
    },
    {
        "id": 64,
        "category": "NEET",
        "question": "If the kinetic energy of a body is increased by 300%, what is the percentage increase in its linear momentum?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.4  KINETIC ENERGY**",
        "ground_truth_answer": "p = \\sqrt{2mK}. K2 = 4*K1 => p2 = 2*p1. Increase is 100%.",
        "expected_formulas": ["p = \\sqrt{2mK}"]
    },
    {
        "id": 65,
        "category": "NEET",
        "question": "A body is moving with a uniform speed in a circle. Is its angular momentum conserved about the center of the circle?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7  TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "Yes, because the torque about the center of the circle is zero.",
        "expected_formulas": ["\\tau = r \\times F = 0"]
    },
    {
        "id": 66,
        "category": "NEET",
        "question": "Which physical quantity is represented by the product of moment of inertia and angular velocity?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS**",
        "ground_truth_answer": "L = I * w represents Angular Momentum.",
        "expected_formulas": ["L = I \\omega"]
    },
    {
        "id": 67,
        "category": "NEET",
        "question": "What is the torque acting on a particle of mass m moving with constant velocity?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7  TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "Since velocity is constant, force is zero, so the torque is zero.",
        "expected_formulas": ["\\tau = r \\times F"]
    },
    {
        "id": 68,
        "category": "NEET",
        "question": "Where does the center of mass of a uniform ring of mass M and radius R lie?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "At the geometric center of the ring.",
        "expected_formulas": []
    },
    {
        "id": 69,
        "category": "NEET",
        "question": "How does the acceleration due to gravity g at the equator compare to that at the poles of the Earth?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "g is minimum at the equator and maximum at the poles.",
        "expected_formulas": []
    },
    {
        "id": 70,
        "category": "NEET",
        "question": "What is the value of gravitational potential at infinity?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "It is defined as zero.",
        "expected_formulas": []
    },
    {
        "id": 71,
        "category": "NEET",
        "question": "What is the relation between escape velocity and orbital velocity of a satellite near the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9  EARTH SATELLITES**",
        "ground_truth_answer": "v_e = \\sqrt{2} * v_o.",
        "expected_formulas": ["v_e = \\sqrt{2} v_o"]
    },
    {
        "id": 72,
        "category": "NEET",
        "question": "If a satellite is orbiting very close to the Earth's surface, what is its approximate orbital time period?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9  EARTH SATELLITES**",
        "ground_truth_answer": "T \\approx 84.6 minutes.",
        "expected_formulas": ["T = 2 \\pi \\sqrt{\\frac{R_E}{g}}"]
    },
    {
        "id": 73,
        "category": "NEET",
        "question": "A ball is dropped from a height of 10 m. If the coefficient of restitution is 0.6, to what height will the ball rebound after the first collision with the floor?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2  Collisions in One Dimension**",
        "ground_truth_answer": "h' = e^2 * h = 0.36 * 10 = 3.6 m.",
        "expected_formulas": ["h' = e^2 h"]
    },
    {
        "id": 74,
        "category": "NEET",
        "question": "What is the unit of gravitational potential?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "J/kg.",
        "expected_formulas": []
    },
    {
        "id": 75,
        "category": "NEET",
        "question": "What is the rotational analog of mass in rotational motion?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "Moment of inertia (I).",
        "expected_formulas": []
    },
    {
        "id": 76,
        "category": "NEET",
        "question": "Why does a skater spin faster when they fold their arms?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12.1 Conservation of angular momentum**",
        "ground_truth_answer": "Folding arms reduces I, which increases w since L = I w is conserved.",
        "expected_formulas": ["L = I \\omega"]
    },
    {
        "id": 77,
        "category": "NEET",
        "question": "If the radius of Earth shrinks by 1% without changing its mass, how will the acceleration due to gravity at the surface change?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.3  UNIVERSAL LAW OF GRAVITATION**",
        "ground_truth_answer": "g increases by 2%.",
        "expected_formulas": ["g = \\frac{GM}{R^2}"]
    },
    {
        "id": 78,
        "category": "NEET",
        "question": "What is the work done in moving a body of mass m along a closed path in a conservative gravitational field?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7  THE CONCEPT OF POTENTIAL ENERGY**",
        "ground_truth_answer": "Zero.",
        "expected_formulas": ["W = 0"]
    },
    {
        "id": 79,
        "category": "NEET",
        "question": "A body of mass m is at a height R (Radius of Earth) above the Earth's surface. What is its weight at this height compared to its weight on the surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "g' = g / (1+1)^2 = g/4. Weight is 25% of surface weight.",
        "expected_formulas": ["g(h) = g_E (\\frac{R_E}{R_E+h})^2"]
    },
    {
        "id": 80,
        "category": "NEET",
        "question": "If the kinetic energy of a rotating body is rotational KE = 1/2 I w^2, and I is doubled while w is halved, what is the new rotational KE?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "KE_new = 0.5 * (2I) * (w/2)^2 = 0.5 * KE_old. Halved.",
        "expected_formulas": ["K = \\frac{1}{2} I \\omega^2"]
    },

    # Category E: Formula-Based Questions (81-100)
    {
        "id": 81,
        "category": "Formula-Based",
        "question": "Write the formula for the work-energy theorem for a variable force.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.6 THE WORK-ENERGY THEOREM FOR A VARIABLE FORCE",
        "ground_truth_answer": "K_f - K_i = \\int_{x_i}^{x_f} F(x) dx.",
        "expected_formulas": ["K_f - K_i = \\int_{x_i}^{x_f} F(x) dx"]
    },
    {
        "id": 82,
        "category": "Formula-Based",
        "question": "What is the mathematical formula for the gravitational potential energy of two point masses m1 and m2 separated by a distance r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.7  GRAVITATIONAL POTENTIAL ENERGY**",
        "ground_truth_answer": "V(r) = -G * m1 * m2 / r.",
        "expected_formulas": ["V(r) = -\\frac{G m_1 m_2}{r}"]
    },
    {
        "id": 83,
        "category": "Formula-Based",
        "question": "Write the formula for the moment of inertia of a uniform solid sphere about its diameter.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "I = (2/5) * M * R^2.",
        "expected_formulas": ["I = \\frac{2}{5} M R^2"]
    },
    {
        "id": 84,
        "category": "Formula-Based",
        "question": "Write the formula for the escape velocity from the surface of a planet of mass M and radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.8  ESCAPE SPEED",
        "ground_truth_answer": "v_e = \\sqrt{2GM/R}.",
        "expected_formulas": ["v_e = \\sqrt{\\frac{2GM}{R}}"]
    },
    {
        "id": 85,
        "category": "Formula-Based",
        "question": "What is the formula for the potential energy stored in a spring stretched by a distance x?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9  THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "V(x) = (1/2) * k * x^2.",
        "expected_formulas": ["V(x) = \\frac{1}{2} k x^2"]
    },
    {
        "id": 86,
        "category": "Formula-Based",
        "question": "Write the relation between linear velocity v and angular velocity w of a particle in rotational motion.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.6 ANGULAR VELOCITY AND ITS RELATION WITH LINEAR VELOCITY**",
        "ground_truth_answer": "v = \\omega * r.",
        "expected_formulas": ["v = \\omega r"]
    },
    {
        "id": 87,
        "category": "Formula-Based",
        "question": "What is the mathematical expression for the law of universal gravitation?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.3  UNIVERSAL LAW OF GRAVITATION**",
        "ground_truth_answer": "F = G * m1 * m2 / r^2.",
        "expected_formulas": ["F = G \\frac{m_1 m_2}{r^2}"]
    },
    {
        "id": 88,
        "category": "Formula-Based",
        "question": "Write the formula for the moment of inertia of a thin circular disc of mass M and radius R about its diameter.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9  MOMENT OF INERTIA**",
        "ground_truth_answer": "I = (1/4) * M * R^2.",
        "expected_formulas": ["I = \\frac{1}{4} M R^2"]
    },
    {
        "id": 90,
        "category": "Formula-Based",
        "question": "What is the formula for the center of mass of a two-particle system?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.2  CENTRE OF MASS",
        "ground_truth_answer": "R = (m1 * r1 + m2 * r2) / (m1 + m2).",
        "expected_formulas": ["R = \\frac{m_1 r_1 + m_2 r_2}{m_1 + m_2}"]
    },
    {
        "id": 91,
        "category": "Formula-Based",
        "question": "Write the formula for the angular momentum of a particle.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7.2 Angular momentum of a particle**",
        "ground_truth_answer": "\\vec{l} = \\vec{r} \\times \\vec{p}.",
        "expected_formulas": ["\\vec{l} = \\vec{r} \\times \\vec{p}"]
    },
    {
        "id": 92,
        "category": "Formula-Based",
        "question": "Write the relation between power, force, and velocity.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10  POWER",
        "ground_truth_answer": "P = \\vec{F} \\cdot \\vec{v}.",
        "expected_formulas": ["P = \\vec{F} \\cdot \\vec{v}"]
    },
    {
        "id": 93,
        "category": "Formula-Based",
        "question": "What is the formula for the work done by a constant torque?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS**",
        "ground_truth_answer": "W = \\tau * \\theta.",
        "expected_formulas": ["W = \\tau \\theta"]
    },
    {
        "id": 94,
        "category": "Formula-Based",
        "question": "Write the formula for the acceleration due to gravity g at a height h above the Earth's surface (for h << R).",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "g(h) \\approx g_E * (1 - 2h/R_E).",
        "expected_formulas": ["g(h) = g_E (1 - \\frac{2h}{R_E})"]
    },
    {
        "id": 95,
        "category": "Formula-Based",
        "question": "Write the formula for the acceleration due to gravity g at a depth d below the Earth's surface.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ACCELERATION DUE TO GRAVITY BELOW AND ABOVE THE SURFACE OF EARTH",
        "ground_truth_answer": "g(d) = g_E * (1 - d/R_E).",
        "expected_formulas": ["g(d) = g_E (1 - \\frac{d}{R_E})"]
    },
    {
        "id": 96,
        "category": "Formula-Based",
        "question": "What is the mathematical formulation of Kepler's third law?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.2  KEPLER’S LAWS**",
        "ground_truth_answer": "T^2 \\propto R^3.",
        "expected_formulas": ["T^2 \\propto R^3"]
    },
    {
        "id": 97,
        "category": "Formula-Based",
        "question": "Write the expression for the energy of an orbiting satellite.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.10  ENERGY OF AN ORBITING SATELLITE**",
        "ground_truth_answer": "E = -G * M * m / (2r).",
        "expected_formulas": ["E = -\\frac{G M m}{2r}"]
    },
    {
        "id": 98,
        "category": "Formula-Based",
        "question": "Write the formula for the coefficient of restitution e for a direct collision between two bodies.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2  Collisions in One Dimension**",
        "ground_truth_answer": "e = (v_2f - v_1f) / (v_1i - v_2i).",
        "expected_formulas": ["e = \\frac{v_{2f} - v_{1f}}{v_{1i} - v_{2i}}"]
    },
    {
        "id": 99,
        "category": "Formula-Based",
        "question": "Write the formula for the orbital speed of a satellite orbiting at a height h above the Earth of radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9  EARTH SATELLITES**",
        "ground_truth_answer": "v_o = \\sqrt{GM / (R + h)}.",
        "expected_formulas": ["v_o = \\sqrt{\\frac{GM}{R+h}}"]
    },
    {
        "id": 100,
        "category": "Formula-Based",
        "question": "What is the formula for the gravitational field intensity due to a point mass M at a distance r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.3  UNIVERSAL LAW OF GRAVITATION**",
        "ground_truth_answer": "E = G * M / r^2.",
        "expected_formulas": ["E = \\frac{GM}{r^2}"]
    }
]

# Write to json
with open("benchmark_questions.json", "w") as f:
    json.dump(questions, f, indent=2)

print("Regenerated benchmark_questions.json with 100 correctly mapped questions.")
