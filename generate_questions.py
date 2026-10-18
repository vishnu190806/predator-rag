import json

questions = [
    # Category A: NCERT Theory Questions (1-20)
    {
        "id": 1,
        "category": "NCERT Theory",
        "question": "State the Work-Energy Theorem for a variable force.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.2 NOTIONS OF WORK AND KINETIC ENERGY: THE WORK-ENERGY THEOREM",
        "ground_truth_answer": "The change in kinetic energy of a particle is equal to the work done on it by the net force: Kf - Ki = W = \\int_{x_i}^{x_f} F(x) dx.",
        "expected_formulas": ["K_f - K_i = W", "\\int F dx"]
    },
    {
        "id": 2,
        "category": "NCERT Theory",
        "question": "Define conservative and non-conservative forces with examples.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.5 CONSERVATIVE FORCES",
        "ground_truth_answer": "A force is conservative if the work done by it on a particle that moves between two points depends only on these points and not on the path taken, or if the work done in a closed path is zero (e.g., gravitational force, spring force). Otherwise, it is non-conservative (e.g., friction, viscous drag).",
        "expected_formulas": ["\\oint F \\cdot dr = 0"]
    },
    {
        "id": 3,
        "category": "NCERT Theory",
        "question": "State the law of conservation of mechanical energy.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.6 THE CONSERVATION OF MECHANICAL ENERGY",
        "ground_truth_answer": "The total mechanical energy (K + V) of a system remains constant if the forces doing work on it are conservative.",
        "expected_formulas": ["E = K + V", "K_i + V_i = K_f + V_f"]
    },
    {
        "id": 4,
        "category": "NCERT Theory",
        "question": "What is the relation between the torque and angular momentum of a rotating body?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS",
        "ground_truth_answer": "The rate of change of angular momentum of a system of particles about a point is equal to the sum of external torques acting on the system about that point: dL/dt = \\tau.",
        "expected_formulas": ["\\tau = \\frac{dL}{dt}"]
    },
    {
        "id": 5,
        "category": "NCERT Theory",
        "question": "State Kepler's three laws of planetary motion.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.2 KEPLER’S LAWS",
        "ground_truth_answer": "1. Law of Orbits: All planets move in elliptical orbits with the Sun at one focus. 2. Law of Areas: The line joining a planet to the Sun sweeps out equal areas in equal intervals of time (conservation of angular momentum). 3. Law of Periods: The square of the time period of revolution of a planet is proportional to the cube of the semi-major axis of its elliptical orbit (T^2 \\propto a^3).",
        "expected_formulas": ["T^2 \\propto a^3"]
    },
    {
        "id": 6,
        "category": "NCERT Theory",
        "question": "State the Universal Law of Gravitation.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.3 UNIVERSAL LAW OF GRAVITATION",
        "ground_truth_answer": "Every body in the universe attracts every other body with a force which is directly proportional to the product of their masses and inversely proportional to the square of the distance between them: F = G * m1 * m2 / r^2.",
        "expected_formulas": ["F = G \\frac{m_1 m_2}{r^2}"]
    },
    {
        "id": 7,
        "category": "NCERT Theory",
        "question": "Explain the physical significance of the moment of inertia.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.9 MOMENT OF INERTIA",
        "ground_truth_answer": "Moment of inertia (I) is the rotational analogue of mass in linear motion. It measures a body's resistance to change in its rotational motion and depends on the distribution of mass relative to the axis of rotation.",
        "expected_formulas": ["I = \\sum m_i r_i^2"]
    },
    {
        "id": 8,
        "category": "NCERT Theory",
        "question": "What is the escape speed of a body and how does it depend on the mass of the body?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ESCAPE SPEED",
        "ground_truth_answer": "Escape speed is the minimum speed required for a body to escape from the gravitational field of a planet: v_e = \\sqrt{2GM/R} = \\sqrt{2gR}. It depends on the mass and radius of the planet but is independent of the mass of the escaping body.",
        "expected_formulas": ["v_e = \\sqrt{\\frac{2GM}{R}}"]
    },
    {
        "id": 9,
        "category": "NCERT Theory",
        "question": "Define the coefficient of restitution in collisions.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2 Collisions in One Dimension**",
        "ground_truth_answer": "The coefficient of restitution (e) is the ratio of the relative velocity of separation to the relative velocity of approach after and before a collision: e = (v_2f - v_1f) / (v_1i - v_2i). For elastic collisions e = 1, for completely inelastic collisions e = 0.",
        "expected_formulas": ["e = \\frac{v_{2f} - v_{1f}}{v_{1i} - v_{2i}}"]
    },
    {
        "id": 10,
        "category": "NCERT Theory",
        "question": "What is the difference between elastic and inelastic collisions?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11 COLLISIONS**",
        "ground_truth_answer": "In an elastic collision, both total linear momentum and total kinetic energy are conserved. In an inelastic collision, total linear momentum is conserved but total kinetic energy is not conserved (part of it is converted to heat, deformation, etc.).",
        "expected_formulas": []
    },
    {
        "id": 11,
        "category": "NCERT Theory",
        "question": "Explain the center of mass of a system of particles.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.2 CENTER OF MASS**",
        "ground_truth_answer": "The center of mass of a system of particles is the average position of all parts of the system, weighted according to their masses. It represents the point where the entire mass of the system can be assumed to be concentrated for describing external translational motion: R = \\sum m_i r_i / M.",
        "expected_formulas": ["R = \\frac{\\sum m_i r_i}{M}"]
    },
    {
        "id": 12,
        "category": "NCERT Theory",
        "question": "State the perpendicular axes theorem for moment of inertia.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "The perpendicular axes theorem states that the moment of inertia of a planar body about an axis perpendicular to its plane (Iz) is equal to the sum of its moments of inertia about two mutually perpendicular axes in its plane (Ix and Iy) that intersect with the perpendicular axis: Iz = Ix + Iy.",
        "expected_formulas": ["I_z = I_x + I_y"]
    },
    {
        "id": 13,
        "category": "NCERT Theory",
        "question": "State the parallel axes theorem for moment of inertia.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "The parallel axes theorem states that the moment of inertia of a body about any axis (I) is equal to its moment of inertia about a parallel axis passing through its center of mass (I_cm) plus the product of the mass of the body (M) and the square of the distance (d) between the two parallel axes: I = I_cm + Md^2.",
        "expected_formulas": ["I = I_{com} + M d^2"]
    },
    {
        "id": 14,
        "category": "NCERT Theory",
        "question": "Define gravitational potential energy and write its expression.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "Gravitational potential energy of a system of two masses is the energy stored in the system due to their mutual gravitational attraction. It is equal to the work done in bringing the masses from infinity to their current positions: V(r) = -G M m / r.",
        "expected_formulas": ["V(r) = -\\frac{G M m}{r}"]
    },
    {
        "id": 15,
        "category": "NCERT Theory",
        "question": "What are geostationary satellites and what is their time period?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.8 GEOSTATIONARY AND POLAR SATELLITES",
        "ground_truth_answer": "Geostationary satellites are satellites orbiting the Earth in equatorial orbits with a time period of exactly 24 hours (matching Earth's rotation), so they appear stationary relative to any point on Earth.",
        "expected_formulas": ["T = 24 \\text{ hours}"]
    },
    {
        "id": 16,
        "category": "NCERT Theory",
        "question": "Define power and write its SI unit.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10 POWER",
        "ground_truth_answer": "Power is defined as the rate at which work is done or energy is transferred. SI unit of power is the watt (W), where 1 W = 1 J/s. Formula: P = dW/dt = F.v.",
        "expected_formulas": ["P = \\frac{dW}{dt}", "P = F \\cdot v"]
    },
    {
        "id": 17,
        "category": "NCERT Theory",
        "question": "What is a spring force and how is it related to displacement?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9 THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "A spring force is a restoring force exerted by a stretched or compressed spring. According to Hooke's Law, it is proportional to the displacement from the equilibrium position and acts in the opposite direction: F_s = -k x.",
        "expected_formulas": ["F_s = -k x"]
    },
    {
        "id": 18,
        "category": "NCERT Theory",
        "question": "Explain rolling motion as a combination of translation and rotation.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.11 KINEMATICS OF ROLLING MOTION",
        "ground_truth_answer": "Rolling motion without slipping is a combination of translation of the center of mass with velocity v_cm and rotation about the center of mass with angular velocity w, where the point of contact is instantaneously at rest: v_cm = R * w.",
        "expected_formulas": ["v_{cm} = R \\omega", "K = \\frac{1}{2} M v_{cm}^2 + \\frac{1}{2} I \\omega^2"]
    },
    {
        "id": 19,
        "category": "NCERT Theory",
        "question": "How does the acceleration due to gravity g vary with altitude above the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.1 Acceleration due to gravity above the Earth’s surface**",
        "ground_truth_answer": "The acceleration due to gravity g(h) at a height h above the Earth's surface decreases with height: g(h) = g_E / (1 + h/R_E)^2. For h << R_E, it approximates to g(h) \\approx g_E * (1 - 2h/R_E).",
        "expected_formulas": ["g(h) = g_E (1 - \\frac{2h}{R_E})"]
    },
    {
        "id": 20,
        "category": "NCERT Theory",
        "question": "How does the acceleration due to gravity g vary with depth below the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.2 Acceleration due to gravity below the Earth’s surface**",
        "ground_truth_answer": "The acceleration due to gravity g(d) at a depth d below the Earth's surface decreases linearly with depth: g(d) = g_E * (1 - d/R_E). At the center of the Earth (d = R_E), g becomes zero.",
        "expected_formulas": ["g(d) = g_E (1 - \\frac{d}{R_E})"]
    },

    # Category B: NCERT Exercise Questions (21-40)
    {
        "id": 21,
        "category": "NCERT Exercise",
        "question": "A body of mass 2 kg initially at rest moves under the action of an applied horizontal force of 7 N on a table with coefficient of kinetic friction = 0.1. Compute the work done by the applied force in 10 s.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "Frictional force f = \\mu * m * g = 0.1 * 2 * 9.8 = 1.96 N. Net acceleration a = (F - f) / m = (7 - 1.96) / 2 = 2.52 m/s^2. Displacement d = 0.5 * a * t^2 = 0.5 * 2.52 * 10^2 = 126 m. Work done by applied force W_F = F * d = 7 * 126 = 882 J (or 875 J if g=10).",
        "expected_formulas": ["f = \\mu m g", "d = \\frac{1}{2} a t^2", "W = F d"]
    },
    {
        "id": 22,
        "category": "NCERT Exercise",
        "question": "A pump on the ground floor of a building can pump up water to fill a tank of volume 30 m^3 in 15 min. If the tank is 40 m above the ground, and the efficiency of the pump is 30%, how much electric power is consumed by the pump?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "Mass of water m = V * density = 30 * 1000 = 30000 kg. Time t = 15 * 60 = 900 s. Useful work done W = m * g * h = 30000 * 9.8 * 40 = 1.176 * 10^7 J. Output Power P_out = W/t = 1.176 * 10^7 / 900 = 13.07 kW. Input Power P_in = P_out / efficiency = 13.07 / 0.3 = 43.6 kW (using g = 9.8). If using g = 10, P_in = 44.4 kW.",
        "expected_formulas": ["P_{out} = \\frac{mgh}{t}", "P_{in} = \\frac{P_{out}}{\\eta}"]
    },
    {
        "id": 23,
        "category": "NCERT Exercise",
        "question": "A bob of mass m is suspended by a light string of length L. It is imparted a horizontal velocity v0 at the lowest point. What is the minimum velocity v0 required for the bob to complete a full vertical circle?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7.1 Motion in a Vertical Circle**",
        "ground_truth_answer": "Minimum velocity required at the lowest point to complete a full vertical circle is v_0 = \\sqrt{5gL}.",
        "expected_formulas": ["v_0 = \\sqrt{5gL}"]
    },
    {
        "id": 24,
        "category": "NCERT Exercise",
        "question": "A particle of mass m is moving in a horizontal circle of radius r under a centripetal force equal to -k/r^2. What is the total energy of the particle?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "Centripetal force F_c = m v^2 / r = k / r^2 => m v^2 = k / r. Kinetic Energy K = 0.5 * m * v^2 = k / (2r). Potential Energy V = -\\int F dr = -\\int (k/r^2) dr = -k/r. Total Energy E = K + V = k/(2r) - k/r = -k/(2r).",
        "expected_formulas": ["K = \\frac{1}{2} m v^2 = \\frac{k}{2r}", "E = K + V = -\\frac{k}{2r}"]
    },
    {
        "id": 25,
        "category": "NCERT Exercise",
        "question": "Three identical spheres, each of mass M and radius R, are placed touching each other on a horizontal table. Find the position of the center of mass of the system.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 EXERCISES**",
        "ground_truth_answer": "Since the spheres are identical and touch each other, their centers form an equilateral triangle of side 2R. The center of mass lies at the centroid of this equilateral triangle formed by their centers.",
        "expected_formulas": []
    },
    {
        "id": 26,
        "category": "NCERT Exercise",
        "question": "A solid cylinder of mass 20 kg rotates about its axis with angular speed 100 rad/s. The radius of the cylinder is 0.25 m. What is the kinetic energy of rotation of the cylinder?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 EXERCISES**",
        "ground_truth_answer": "Moment of inertia of a solid cylinder I = 0.5 * M * R^2 = 0.5 * 20 * (0.25)^2 = 0.625 kg m^2. Rotational Kinetic Energy K = 0.5 * I * w^2 = 0.5 * 0.625 * 100^2 = 3125 J.",
        "expected_formulas": ["I = \\frac{1}{2} M R^2", "K = \\frac{1}{2} I \\omega^2"]
    },
    {
        "id": 27,
        "category": "NCERT Exercise",
        "question": "A child stands at the center of a turntable with his two arms outstretched. The turntable is set rotating with an angular speed of 40 rev/min. How much is the angular speed of the child if he folds his hands back and thereby reduces his moment of inertia to 2/5 times the initial value?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 EXERCISES**",
        "ground_truth_answer": "By conservation of angular momentum: I_1 * w_1 = I_2 * w_2. Since I_2 = (2/5) * I_1, we have w_2 = (I_1 / I_2) * w_1 = (5/2) * 40 = 100 rev/min.",
        "expected_formulas": ["I_1 \\omega_1 = I_2 \\omega_2"]
    },
    {
        "id": 28,
        "category": "NCERT Exercise",
        "question": "Find the moment of inertia of a ring of mass M and radius R about a tangent to the circle in the plane of the ring.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "Moment of inertia of a ring about a diameter axis in its plane is I_diameter = 0.5 * M * R^2. By parallel axes theorem, about a tangent in the plane of the ring: I_tangent = I_diameter + M * R^2 = 0.5 * M * R^2 + M * R^2 = 1.5 * M * R^2.",
        "expected_formulas": ["I_{tangent} = I_{dia} + M R^2", "I_{tangent} = \\frac{3}{2} M R^2"]
    },
    {
        "id": 29,
        "category": "NCERT Exercise",
        "question": "An artificial satellite is orbiting around the Earth in a circular orbit of radius r. If its time period is T, what is the relation between T and r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.7 EARTH SATELLITES",
        "ground_truth_answer": "According to Kepler's third law, the square of the time period T is proportional to the cube of the radius of the orbit r: T^2 \\propto r^3 (or T^2 = 4*pi^2*r^3 / (G*M_E)).",
        "expected_formulas": ["T^2 = \\frac{4 \\pi^2 r^3}{G M_E}"]
    },
    {
        "id": 30,
        "category": "NCERT Exercise",
        "question": "A satellite is placed in a circular orbit of radius R around the earth. What is the percentage change in the kinetic energy of the satellite if it is moved to a circular orbit of radius 2R?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "Kinetic energy of a satellite in circular orbit is K = G*M*m / (2r). K1 = G*M*m / (2R), K2 = G*M*m / (4R) = 0.5 * K1. Change in KE = K2 - K1 = -0.5 * K1, representing a 50% decrease.",
        "expected_formulas": ["K = \\frac{GMm}{2r}"]
    },
    {
        "id": 31,
        "category": "NCERT Exercise",
        "question": "A mass of 6 kg is suspended by a rope of length 2 m from the ceiling. A force of 50 N in the horizontal direction is applied at the midpoint of the rope. What is the angle the rope makes with the vertical in equilibrium? (g = 10 m/s^2)",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "At midpoint, horizontal force is 50 N, and weight of the lower part of the rope plus suspended mass is W = m * g = 6 * 10 = 60 N. For equilibrium, tan \\theta = F_horizontal / W = 50 / 60 = 5/6 => \\theta = tan^-1(5/6) \\approx 40 degrees.",
        "expected_formulas": ["\\tan \\theta = \\frac{F}{W}"]
    },
    {
        "id": 32,
        "category": "NCERT Exercise",
        "question": "A bullet of mass 0.012 kg and horizontal speed 70 m/s strikes a block of wood of mass 0.4 kg and instantly comes to rest with respect to the block. What is the common speed of the block and the bullet after the collision?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "By conservation of linear momentum: m * u = (m + M) * v. Here m = 0.012 kg, u = 70 m/s, M = 0.4 kg. v = (0.012 * 70) / (0.012 + 0.4) = 0.84 / 0.412 = 2.04 m/s.",
        "expected_formulas": ["m u = (m + M) v"]
    },
    {
        "id": 33,
        "category": "NCERT Exercise",
        "question": "A trolley of mass 300 kg carrying a sandbag of 25 kg is moving uniformly with a speed of 27 km/h on a frictionless track. After a while, sand starts leaking out of a hole on the trolley's floor at the rate of 0.05 kg/s. What is the speed of the trolley after the entire sandbag is empty?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "Since sand leaks vertically downwards relative to the trolley, it carries no horizontal force or momentum change for the trolley. Thus, no external horizontal force acts on the system, and the speed of the trolley remains constant at 27 km/h (or 7.5 m/s).",
        "expected_formulas": []
    },
    {
        "id": 34,
        "category": "NCERT Exercise",
        "question": "A body of mass 0.5 kg travels in a straight line with velocity v = a x^(3/2) where a = 5 m^(-1/2) s^(-1). What is the work done by the net force during its displacement from x = 0 to x = 2 m?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "At x = 0, v_i = 0. At x = 2 m, v_f = 5 * 2^(3/2) = 5 * 2.828 = 14.14 m/s. Work done W = \\Delta K = 0.5 * m * (v_f^2 - v_i^2) = 0.5 * 0.5 * (14.14^2 - 0) = 0.25 * 200 = 50 J.",
        "expected_formulas": ["W = \\frac{1}{2} m (v_f^2 - v_i^2)"]
    },
    {
        "id": 35,
        "category": "NCERT Exercise",
        "question": "A 1 kg block situated on a rough incline is connected to a spring of spring constant 100 N/m. The block is released from rest when the spring is unstretched. Find the maximum displacement of the block down the incline.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "By energy conservation: Loss in gravitational PE = Gain in elastic PE + Work done against friction. m g x sin\\theta = 0.5 k x^2 + \\mu m g x cos\\theta => x = 2 m g (sin\\theta - \\mu cos\\theta) / k.",
        "expected_formulas": ["\\Delta PE = \\Delta KE + W_f"]
    },
    {
        "id": 36,
        "category": "NCERT Exercise",
        "question": "What is the moment of inertia of a uniform thin rod of mass M and length L about an axis perpendicular to the rod and passing through one of its ends?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "Moment of inertia about center of mass is I_cm = M L^2 / 12. Using parallel axes theorem: I_end = I_cm + M * (L/2)^2 = M L^2 / 12 + M L^2 / 4 = M L^2 / 3.",
        "expected_formulas": ["I = I_{cm} + M d^2", "I_{end} = \\frac{1}{3} M L^2"]
    },
    {
        "id": 37,
        "category": "NCERT Exercise",
        "question": "A solid sphere rolls down two different inclined planes of the same heights but different angles of inclination. Will it reach the bottom with the same speed in each case?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.12 EXERCISES**",
        "ground_truth_answer": "Yes, by conservation of energy, the loss in potential energy m*g*h equals the gain in total kinetic energy (0.5 * M * v^2 + 0.5 * I * w^2). Since height h is same and it rolls without slipping, v = \\sqrt{10gh/7}, which is independent of the angle of inclination.",
        "expected_formulas": ["v = \\sqrt{\\frac{2gh}{1 + K^2/R^2}}"]
    },
    {
        "id": 38,
        "category": "NCERT Exercise",
        "question": "A disc of mass M and radius R is rolling without slipping on a horizontal surface with velocity v. What is its total kinetic energy?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.11 KINEMATICS OF ROLLING MOTION**",
        "ground_truth_answer": "Total KE = Translational KE + Rotational KE = 0.5 * M * v^2 + 0.5 * I * w^2. For a disc, I = 0.5 * M * R^2 and w = v/R. KE = 0.5 * M * v^2 + 0.25 * M * v^2 = 0.75 * M * v^2.",
        "expected_formulas": ["K = \\frac{1}{2} M v^2 + \\frac{1}{2} I \\omega^2", "K = \\frac{3}{4} M v^2"]
    },
    {
        "id": 39,
        "category": "NCERT Exercise",
        "question": "Find the potential energy of a system of four particles, each of mass m, placed at the vertices of a square of side l.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9 EXERCISES**",
        "ground_truth_answer": "There are 6 pairs of interactions. 4 side pairs of distance l, and 2 diagonal pairs of distance \\sqrt{2}*l. PE = -G * m^2 / l * (4 + 2/\\sqrt{2}) = -G * m^2 / l * (4 + \\sqrt{2}).",
        "expected_formulas": ["U = -\\sum \\frac{G m_i m_j}{r_{ij}}"]
    },
    {
        "id": 40,
        "category": "NCERT Exercise",
        "question": "A rocket is fired vertically with a speed of 5 km/s from the earth's surface. How far from the earth does the rocket go before coming to rest? (Radius of Earth = 6400 km)",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.9 EXERCISES**",
        "ground_truth_answer": "By energy conservation: E_initial = 0.5 * m * v^2 - G * M_E * m / R_E. E_final = -G * M_E * m / r. Equating the two: 0.5 * v^2 - g * R_E = -g * R_E^2 / r => r = R_E / (1 - v^2 / (2 * g * R_E)). Max height h = r - R_E = R_E * (v^2 / (2gR_E - v^2)). For v = 5 km/s, h \\approx 1600 km.",
        "expected_formulas": ["\\frac{1}{2} m v^2 - \\frac{G M_E m}{R_E} = -\\frac{G M_E m}{R_E + h}"]
    },

    # Category C: JEE Main Style (41-60)
    {
        "id": 41,
        "category": "JEE Main",
        "question": "A block of mass m is projected up a rough inclined plane of inclination 30 degrees with a kinetic energy K. If the coefficient of friction is 0.2, the work done against friction before it comes to rest is?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.12 EXERCISES**",
        "ground_truth_answer": "Force of friction f = \\mu * m * g * cos 30. Net retarding force down the plane F = m*g*sin 30 + f. Distance traveled s = K / F. Work done against friction W_f = f * s = K * (\\mu * cos 30) / (sin 30 + \\mu * cos 30) = K * (0.2 * \\sqrt{3}/2) / (0.5 + 0.2 * \\sqrt{3}/2) \\approx 0.257 * K.",
        "expected_formulas": ["f = \\mu m g \\cos \\theta", "W_f = f s"]
    },
    {
        "id": 42,
        "category": "JEE Main",
        "question": "A body of mass 2 kg is driven by a constant power of 1 W. If it starts from rest, what is the distance covered by the body in 9 seconds?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10 POWER",
        "ground_truth_answer": "P = F * v = m * v * dv/dt = 1 W. Integrating: 0.5 * m * v^2 = P * t => v = \\sqrt{2 P t / m}. For m=2, P=1: v = \\sqrt{t}. Distance s = \\int v dt = \\int t^(1/2) dt = (2/3) * t^(3/2). In t = 9 s, s = (2/3) * 9^(3/2) = (2/3) * 27 = 18 m.",
        "expected_formulas": ["v = \\sqrt{\\frac{2Pt}{m}}", "s = \\frac{2}{3} \\sqrt{\\frac{2P}{m}} t^{3/2}"]
    },
    {
        "id": 43,
        "category": "JEE Main",
        "question": "A particle of mass m is attached to a string of length l and is projected horizontally with velocity sqrt(3gl) from the bottom-most point. Find the maximum height reached by the particle above the bottom-most point.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.7.1 Motion in a Vertical Circle**",
        "ground_truth_answer": "Since v_0 = \\sqrt{3gl} is between \\sqrt{2gl} and \\sqrt{5gl}, the string will slacken at a height h above the lowest point where tension T = 0. T = m*(v^2/l) + m*g*cos\\theta = 0 => v^2 = -g*l*cos\\theta. By conservation of energy, 0.5 * m * v_0^2 = 0.5 * m * v^2 + m * g * l * (1 - cos\\theta). Solved: cos\\theta = -1/3. Height at slackening = l * (1 - cos\\theta) = 4/3 * l. Velocity at slackening v = \\sqrt{gl/3}. Maximum height including projectile motion after slacking is H_max = 4/3*l + (v_x)^2 / (2g) = 4/3*l + (v*sin\\theta)^2 / (2g) = 4/3*l + (gl/3 * 8/9) / (2g) = 4/3*l + 4/27 * l = 40/27 * l.",
        "expected_formulas": ["T = \\frac{m v^2}{l} + m g \\cos \\theta"]
    },
    {
        "id": 44,
        "category": "JEE Main",
        "question": "Two bodies of masses m1 and m2 are connected by a light spring of force constant k. They are placed on a smooth horizontal surface. If they are pulled apart and released, find the frequency of oscillation of the system.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9 THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "The system oscillates with a reduced mass \\mu = (m1 * m2) / (m1 + m2). The frequency of oscillation is f = 1 / (2*pi) * \\sqrt{k/\\mu} = 1 / (2*pi) * \\sqrt{k*(m1 + m2) / (m1 * m2)}.",
        "expected_formulas": ["\\mu = \\frac{m_1 m_2}{m_1 + m_2}", "f = \\frac{1}{2\\pi}\\sqrt{\\frac{k}{\\mu}}"]
    },
    {
        "id": 45,
        "category": "JEE Main",
        "question": "The center of mass of three particles of masses 1 kg, 2 kg, and 3 kg lies at the point (1, 2, 3). If another particle of mass 4 kg is placed at the origin, find the coordinates of the new center of mass.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.2 CENTER OF MASS**",
        "ground_truth_answer": "Initial center of mass R_1 = (1, 2, 3) for mass M_1 = 1 + 2 + 3 = 6 kg. Mass M_2 = 4 kg at R_2 = (0, 0, 0). New center of mass R = (M1*R1 + M2*R2) / (M1 + M2) = (6 * (1, 2, 3) + 4 * (0,0,0)) / 10 = (0.6, 1.2, 1.8).",
        "expected_formulas": ["R = \\frac{M_1 R_1 + M_2 R_2}{M_1 + M_2}"]
    },
    {
        "id": 46,
        "category": "JEE Main",
        "question": "A thin uniform rod of length L and mass M is bent at its midpoint to form a L-shape. Find the moment of inertia of this bent rod about an axis passing through the bend and perpendicular to the plane of the L-shape.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "The bent rod consists of two rods of mass M/2 and length L/2 connected at the bend. The moment of inertia of each half about one end is I_half = (M/2) * (L/2)^2 / 3 = M * L^2 / 24. Since they share the axis: I_total = 2 * I_half = M L^2 / 12.",
        "expected_formulas": ["I_{end} = \\frac{1}{3} M L^2", "I_{total} = I_1 + I_2"]
    },
    {
        "id": 47,
        "category": "JEE Main",
        "question": "A solid sphere and a hollow sphere of the same mass and outer radius roll down the same inclined plane without slipping. What is the ratio of their accelerations?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.11 KINEMATICS OF ROLLING MOTION",
        "ground_truth_answer": "Acceleration of a rolling body: a = g*sin\\theta / (1 + I / (MR^2)). For solid sphere: I = 2/5 * M * R^2 => a_solid = 5/7 * g*sin\\theta. For hollow sphere: I = 2/3 * M * R^2 => a_hollow = 3/5 * g*sin\\theta. Ratio a_solid / a_hollow = (5/7) / (3/5) = 25 / 21.",
        "expected_formulas": ["a = \\frac{g \\sin \\theta}{1 + I/MR^2}"]
    },
    {
        "id": 48,
        "category": "JEE Main",
        "question": "A particle of mass m is moving with constant velocity v parallel to the x-axis at a distance y = d. What is the angular momentum of the particle about the origin as a function of time?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS**",
        "ground_truth_answer": "Angular momentum L = r x p. Position vector r = v*t i + d j. Linear momentum p = m*v i. L = (v*t i + d j) x (m*v i) = -m * v * d k. The magnitude is constant and equal to m * v * d, directed along the negative z-axis.",
        "expected_formulas": ["L = r \\times p", "L = m v d"]
    },
    {
        "id": 49,
        "category": "JEE Main",
        "question": "If the distance between the Earth and the Sun were halved, what would be the duration of the year in days?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.2 KEPLER’S LAWS",
        "ground_truth_answer": "T1 = 365 days, R1. R2 = 0.5 * R1. T2^2 / T1^2 = (R2/R1)^3 = (1/2)^3 = 1/8. T2 = T1 / \\sqrt{8} = 365 / 2.828 = 129 days.",
        "expected_formulas": ["T^2 \\propto R^3"]
    },
    {
        "id": 50,
        "category": "JEE Main",
        "question": "The gravitational potential energy of a body at a distance r from the center of Earth is U. Find the gravitational force acting on the body at that point.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "F = -dU/dr. For U = -G*M*m/r, F = -d/dr(-G*M*m/r) = -G*M*m/r^2 (directed towards the center).",
        "expected_formulas": ["F = -\\frac{dU}{dr}"]
    },
    {
        "id": 51,
        "category": "JEE Main",
        "question": "An elastic collision occurs between a moving body of mass M and a stationary body of mass m. What is the fraction of kinetic energy transferred to the stationary body if M = 3m?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2 Collisions in One Dimension**",
        "ground_truth_answer": "Fraction of energy transferred \\Delta K/K = 4 * M * m / (M + m)^2. For M = 3m, \\Delta K/K = 4 * 3 * m^2 / (4m)^2 = 12 / 16 = 3/4 or 75%.",
        "expected_formulas": ["\\frac{\\Delta K}{K} = \\frac{4 M m}{(M+m)^2}"]
    },
    {
        "id": 52,
        "category": "JEE Main",
        "question": "A spring of force constant k is cut into two equal halves. What is the force constant of each half?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9 THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "The stiffness of a spring is inversely proportional to its length: k * L = constant. When cut into two equal halves, the length becomes L/2, so the force constant of each half becomes 2k.",
        "expected_formulas": ["k \\propto \\frac{1}{L}"]
    },
    {
        "id": 53,
        "category": "JEE Main",
        "question": "A body of mass m is thrown vertically upwards with a velocity equal to half the escape velocity from the surface of the Earth. What is the maximum height attained by the body?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ESCAPE SPEED",
        "ground_truth_answer": "Escape velocity v_e = \\sqrt{2gR}. Launch velocity v = 0.5 * v_e = \\sqrt{gR/2}. By energy conservation: 0.5 * m * v^2 - G * M * m / R = -G * M * m / (R + h). v^2 / 2 - g * R = -g * R^2 / (R+h) => g*R/4 - g*R = -g*R^2 / (R+h) => -3/4 * g*R = -g*R^2 / (R+h) => R+h = 4/3 * R => h = R/3.",
        "expected_formulas": ["\\frac{1}{2} m v^2 - \\frac{GMm}{R} = -\\frac{GMm}{R+h}"]
    },
    {
        "id": 54,
        "category": "JEE Main",
        "question": "Find the moment of inertia of a uniform circular disc of mass M and radius R about an axis passing through its center and perpendicular to its plane, using integration.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9 MOMENT OF INERTIA**",
        "ground_truth_answer": "For an element ring of radius r and width dr: dm = M / (pi*R^2) * 2*pi*r*dr = (2M/R^2)*r*dr. dI = dm * r^2 = (2M/R^2)*r^3*dr. Integrating from 0 to R: I = \\int_0^R (2M/R^2)*r^3*dr = (2M/R^2) * [R^4 / 4] = 0.5 * M * R^2.",
        "expected_formulas": ["I = \\int r^2 dm", "I = \\frac{1}{2} M R^2"]
    },
    {
        "id": 55,
        "category": "JEE Main",
        "question": "A sphere of mass M and radius R collides elastically with another identical sphere at rest, such that the collision is oblique. What is the angle between their velocities after the collision?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.3 Collisions in Two Dimensions**",
        "ground_truth_answer": "By conservation of momentum: u_1 = v_1 + v_2 => u_1^2 = v_1^2 + v_2^2 + 2 * v_1 . v_2. By conservation of KE (elastic): u_1^2 = v_1^2 + v_2^2. Comparing gives v_1 . v_2 = 0, which means the angle between their velocities after collision is 90 degrees (or pi/2).",
        "expected_formulas": ["\\vec{v}_1 \\cdot \\vec{v}_2 = 0"]
    },
    {
        "id": 56,
        "category": "JEE Main",
        "question": "A planet orbits the Sun in an elliptical path. If the ratio of maximum to minimum distance of the planet from the Sun is 3, what is the ratio of maximum to minimum speed of the planet?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.2 KEPLER’S LAWS",
        "ground_truth_answer": "By conservation of angular momentum (Kepler's second law): m * v_max * r_min = m * v_min * r_max => v_max / v_min = r_max / r_min. Since r_max / r_min = 3, the ratio of maximum to minimum speed is 3.",
        "expected_formulas": ["v_{max} r_{min} = v_{min} r_{max}"]
    },
    {
        "id": 57,
        "category": "JEE Main",
        "question": "If the acceleration due to gravity at a height h above the Earth's surface is same as that at a depth d below the surface (with h and d being small compared to Earth's radius R), what is the relation between h and d?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.2 Acceleration due to gravity below the Earth’s surface**",
        "ground_truth_answer": "g(h) = g * (1 - 2h/R). g(d) = g * (1 - d/R). Equating the two gives: 1 - 2h/R = 1 - d/R => d = 2h.",
        "expected_formulas": ["d = 2h"]
    },
    {
        "id": 58,
        "category": "JEE Main",
        "question": "A solid sphere of mass M and radius R is rolling without slipping on a horizontal surface with speed v. It then rolls up an inclined plane. What is the maximum height reached by the sphere?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.11 KINEMATICS OF ROLLING MOTION",
        "ground_truth_answer": "Total initial KE = 0.5 * M * v^2 + 0.5 * I * w^2 = 0.5 * M * v^2 + 0.5 * (2/5 * M * R^2) * (v/R)^2 = 0.7 * M * v^2. Equating this to potential energy at max height: M * g * h = 0.7 * M * v^2 => h = 0.7 * v^2 / g = 7 * v^2 / (10 * g).",
        "expected_formulas": ["M g h = \\frac{7}{10} M v^2"]
    },
    {
        "id": 59,
        "category": "JEE Main",
        "question": "Find the gravitational potential at the center of a thin uniform semi-circular ring of mass M and radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "Since every point on the semi-circular ring is at the same distance R from the center, the gravitational potential V is simply the sum of potentials of all small elements: V = -G * M / R.",
        "expected_formulas": ["V = -\\frac{G M}{R}"]
    },
    {
        "id": 60,
        "category": "JEE Main",
        "question": "A uniform disc of mass M and radius R is rotating with angular velocity w. If another identical disc is placed coaxially and gently on top of it, what is the common angular velocity of the two discs after they start rotating together?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS",
        "ground_truth_answer": "By conservation of angular momentum about the rotation axis: I_1 * w = (I_1 + I_2) * w_common. Since the discs are identical, I_1 = I_2 = I. I * w = 2I * w_common => w_common = w / 2.",
        "expected_formulas": ["I_1 \\omega_1 + I_2 \\omega_2 = (I_1 + I_2) \\omega"]
    },

    # Category D: NEET Style (61-80)
    {
        "id": 61,
        "category": "NEET",
        "question": "Under what condition is the work done by a force zero?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3 WORK",
        "ground_truth_answer": "Work done W = F * d * cos\\theta is zero when: 1. Applied force F = 0. 2. Displacement d = 0. 3. The angle \\theta between force and displacement is 90 degrees (perpendicular, e.g. centripetal force).",
        "expected_formulas": ["W = F d \\cos \\theta"]
    },
    {
        "id": 62,
        "category": "NEET",
        "question": "What is the angle between the force and displacement for maximum work done?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3 WORK",
        "ground_truth_answer": "Work done W = F * d * cos\\theta is maximum when cos\\theta = 1, which means the angle \\theta between the force and displacement is 0 degrees (i.e. force and displacement are in the same direction).",
        "expected_formulas": ["W = F d \\cos \\theta"]
    },
    {
        "id": 63,
        "category": "NEET",
        "question": "A body of mass 5 kg is raised through a height of 10 m. What is the work done by the gravitational force? (g = 10 m/s^2)",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.3 WORK",
        "ground_truth_answer": "Gravitational force acts downwards while displacement is upwards (angle = 180 degrees). Work done W_g = F_g * h * cos 180 = m * g * h * (-1) = 5 * 10 * 10 * (-1) = -500 J.",
        "expected_formulas": ["W = -mgh"]
    },
    {
        "id": 64,
        "category": "NEET",
        "question": "If the kinetic energy of a body is increased by 300%, what is the percentage increase in its linear momentum?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.2 NOTIONS OF WORK AND KINETIC ENERGY: THE WORK-ENERGY THEOREM",
        "ground_truth_answer": "Relation between KE and momentum: K = p^2 / 2m => p = \\sqrt{2mK}. K2 = K1 + 300% of K1 = 4 * K1. p2 = \\sqrt{2m * 4K1} = 2 * p1. Percentage increase in momentum = (p2 - p1)/p1 * 100% = 100%.",
        "expected_formulas": ["p = \\sqrt{2mK}"]
    },
    {
        "id": 65,
        "category": "NEET",
        "question": "A body is moving with a uniform speed in a circle. Is its angular momentum conserved about the center of the circle?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS",
        "ground_truth_answer": "Yes, because the torque acting on it about the center of the circle is zero (the force is centripetal and directed towards the center, so position vector and force are collinear, leading to \\tau = r x F = 0).",
        "expected_formulas": ["\\tau = r \\times F = 0"]
    },
    {
        "id": 66,
        "category": "NEET",
        "question": "Which physical quantity is represented by the product of moment of inertia and angular velocity?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS",
        "ground_truth_answer": "The product of moment of inertia (I) and angular velocity (w) represents the angular momentum (L) of a rotating body: L = I * w.",
        "expected_formulas": ["L = I \\omega"]
    },
    {
        "id": 67,
        "category": "NEET",
        "question": "What is the torque acting on a particle of mass m moving with constant velocity?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.6 TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "Since velocity is constant, the acceleration and net force acting on the particle are zero. Therefore, the torque \\tau = r x F is also zero.",
        "expected_formulas": ["\\tau = r \\times F"]
    },
    {
        "id": 68,
        "category": "NEET",
        "question": "Where does the center of mass of a uniform ring of mass M and radius R lie?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.2 CENTER OF MASS**",
        "ground_truth_answer": "The center of mass of a uniform ring lies at its geometric center, which is a point where no mass actually exists.",
        "expected_formulas": []
    },
    {
        "id": 69,
        "category": "NEET",
        "question": "How does the acceleration due to gravity g at the equator compare to that at the poles of the Earth?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.2 Acceleration due to gravity below the Earth’s surface**",
        "ground_truth_answer": "The acceleration due to gravity g is minimum at the equator and maximum at the poles, because of Earth's equatorial bulge (radius is larger at equator) and centrifugal force from rotation.",
        "expected_formulas": []
    },
    {
        "id": 70,
        "category": "NEET",
        "question": "What is the value of gravitational potential at infinity?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "By convention, the gravitational potential at infinity is taken to be zero, which is the maximum value.",
        "expected_formulas": []
    },
    {
        "id": 71,
        "category": "NEET",
        "question": "What is the relation between escape velocity and orbital velocity of a satellite near the Earth's surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ESCAPE SPEED",
        "ground_truth_answer": "The escape velocity v_e and orbital velocity v_o near the surface of the Earth are related by v_e = \\sqrt{2} * v_o.",
        "expected_formulas": ["v_e = \\sqrt{2} v_o"]
    },
    {
        "id": 72,
        "category": "NEET",
        "question": "If a satellite is orbiting very close to the Earth's surface, what is its approximate orbital time period?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.7 EARTH SATELLITES",
        "ground_truth_answer": "T = 2 * pi * \\sqrt{R_E/g} \\approx 2 * 3.14 * \\sqrt{6.4*10^6 / 9.8} \\approx 5078 s \\approx 84.6 minutes (or 1.4 hours).",
        "expected_formulas": ["T = 2 \\pi \\sqrt{\\frac{R_E}{g}}"]
    },
    {
        "id": 73,
        "category": "NEET",
        "question": "A ball is dropped from a height of 10 m. If the coefficient of restitution is 0.6, to what height will the ball rebound after the first collision with the floor?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2 Collisions in One Dimension**",
        "ground_truth_answer": "Rebound height h' = e^2 * h = 0.6^2 * 10 = 0.36 * 10 = 3.6 m.",
        "expected_formulas": ["h' = e^2 h"]
    },
    {
        "id": 74,
        "category": "NEET",
        "question": "What is the unit of gravitational potential?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "The SI unit of gravitational potential is joule per kilogram (J/kg).",
        "expected_formulas": []
    },
    {
        "id": 75,
        "category": "NEET",
        "question": "What is the rotational analog of mass in rotational motion?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.9 MOMENT OF INERTIA",
        "ground_truth_answer": "The rotational analog of mass is the moment of inertia (I).",
        "expected_formulas": []
    },
    {
        "id": 76,
        "category": "NEET",
        "question": "Why does a skater spin faster when they fold their arms?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.8 CONSERVATION OF ANGULAR MOMENTUM**",
        "ground_truth_answer": "Folding arms reduces the distribution of mass from the axis of rotation, decreasing the moment of inertia (I). Since angular momentum L = I * w is conserved (no external torque), the angular velocity w must increase, causing the skater to spin faster.",
        "expected_formulas": ["L = I \\omega"]
    },
    {
        "id": 77,
        "category": "NEET",
        "question": "If the radius of Earth shrinks by 1% without changing its mass, how will the acceleration due to gravity at the surface change?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.3 UNIVERSAL LAW OF GRAVITATION",
        "ground_truth_answer": "g = G * M / R^2. Differentiating: dg/g = -2 * dR/R. If radius decreases by 1%, g increases by 2%.",
        "expected_formulas": ["g = \\frac{GM}{R^2}"]
    },
    {
        "id": 78,
        "category": "NEET",
        "question": "What is the work done in moving a body of mass m along a closed path in a conservative gravitational field?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.5 CONSERVATIVE FORCES",
        "ground_truth_answer": "The work done in moving a body along a closed path in a conservative field (like gravity) is exactly zero.",
        "expected_formulas": ["W = 0", "\\oint F \\cdot dr = 0"]
    },
    {
        "id": 79,
        "category": "NEET",
        "question": "A body of mass m is at a height R (Radius of Earth) above the Earth's surface. What is its weight at this height compared to its weight on the surface?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.1 Acceleration due to gravity above the Earth’s surface**",
        "ground_truth_answer": "g(h) = g / (1 + h/R)^2. For h = R, g(R) = g / 4. Thus, weight at this height is 1/4th (or 25%) of its weight on the Earth's surface.",
        "expected_formulas": ["g(h) = g_E (\\frac{R_E}{R_E+h})^2"]
    },
    {
        "id": 80,
        "category": "NEET",
        "question": "If the kinetic energy of a rotating body is rotational KE = 1/2 I w^2, and I is doubled while w is halved, what is the new rotational KE?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.9 MOMENT OF INERTIA",
        "ground_truth_answer": "KE_new = 0.5 * (2I) * (w/2)^2 = 0.5 * 2I * w^2 / 4 = 0.5 * (0.5 * I * w^2) = 0.5 * KE_old. The new kinetic energy is halved (50% of the original).",
        "expected_formulas": ["K = \\frac{1}{2} I \\omega^2"]
    },

    # Category E: Formula-Based Questions (81-100)
    {
        "id": 81,
        "category": "Formula-Based",
        "question": "Write the formula for the work-energy theorem for a variable force.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.2 NOTIONS OF WORK AND KINETIC ENERGY: THE WORK-ENERGY THEOREM",
        "ground_truth_answer": "K_f - K_i = \\int_{x_i}^{x_f} F(x) dx.",
        "expected_formulas": ["K_f - K_i = \\int_{x_i}^{x_f} F(x) dx"]
    },
    {
        "id": 82,
        "category": "Formula-Based",
        "question": "What is the mathematical formula for the gravitational potential energy of two point masses m1 and m2 separated by a distance r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.5 GRAVITATIONAL POTENTIAL ENERGY",
        "ground_truth_answer": "V(r) = -G * m1 * m2 / r.",
        "expected_formulas": ["V(r) = -\\frac{G m_1 m_2}{r}"]
    },
    {
        "id": 83,
        "category": "Formula-Based",
        "question": "Write the formula for the moment of inertia of a uniform solid sphere about its diameter.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.9 MOMENT OF INERTIA**",
        "ground_truth_answer": "I = (2/5) * M * R^2.",
        "expected_formulas": ["I = \\frac{2}{5} M R^2"]
    },
    {
        "id": 84,
        "category": "Formula-Based",
        "question": "Write the formula for the escape velocity from the surface of a planet of mass M and radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.6 ESCAPE SPEED",
        "ground_truth_answer": "v_e = \\sqrt{2GM/R}.",
        "expected_formulas": ["v_e = \\sqrt{\\frac{2GM}{R}}"]
    },
    {
        "id": 85,
        "category": "Formula-Based",
        "question": "What is the formula for the potential energy stored in a spring stretched by a distance x?",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.9 THE POTENTIAL ENERGY OF A SPRING",
        "ground_truth_answer": "V(x) = (1/2) * k * x^2.",
        "expected_formulas": ["V(x) = \\frac{1}{2} k x^2"]
    },
    {
        "id": 86,
        "category": "Formula-Based",
        "question": "Write the relation between linear velocity v and angular velocity w of a particle in rotational motion.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.4 LINEAR VELOCITY OF A ROTATING BODY**",
        "ground_truth_answer": "v = \\vec{\\omega} \\times \\vec{r} (or in magnitude v = \\omega * r).",
        "expected_formulas": ["v = \\omega r", "\\vec{v} = \\vec{\\omega} \\times \\vec{r}"]
    },
    {
        "id": 87,
        "category": "Formula-Based",
        "question": "What is the mathematical expression for the law of universal gravitation?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.3 UNIVERSAL LAW OF GRAVITATION",
        "ground_truth_answer": "F = G * m1 * m2 / r^2.",
        "expected_formulas": ["F = G \\frac{m_1 m_2}{r^2}"]
    },
    {
        "id": 88,
        "category": "Formula-Based",
        "question": "Write the formula for the moment of inertia of a thin circular disc of mass M and radius R about its diameter.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.10 THEOREMS OF PERPENDICULAR AND PARALLEL AXES**",
        "ground_truth_answer": "I = (1/4) * M * R^2.",
        "expected_formulas": ["I = \\frac{1}{4} M R^2"]
    },
    {
        "id": 89,
        "category": "Formula-Based",
        "question": "Write the formula for the torque in terms of position vector r and force F.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.6 TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "\\vec{\\tau} = \\vec{r} \\times \\vec{F}.",
        "expected_formulas": ["\\vec{\\tau} = \\vec{r} \\times \\vec{F}"]
    },
    {
        "id": 90,
        "category": "Formula-Based",
        "question": "What is the formula for the center of mass of a two-particle system?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.2 CENTER OF MASS**",
        "ground_truth_answer": "R = (m1 * r1 + m2 * r2) / (m1 + m2).",
        "expected_formulas": ["R = \\frac{m_1 r_1 + m_2 r_2}{m_1 + m_2}"]
    },
    {
        "id": 91,
        "category": "Formula-Based",
        "question": "Write the formula for the angular momentum in terms of position vector r and linear momentum p.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.6 TORQUE AND ANGULAR MOMENTUM**",
        "ground_truth_answer": "\\vec{l} = \\vec{r} \\times \\vec{p}.",
        "expected_formulas": ["\\vec{l} = \\vec{r} \\times \\vec{p}"]
    },
    {
        "id": 92,
        "category": "Formula-Based",
        "question": "Write the relation between power, force, and velocity.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## 5.10 POWER",
        "ground_truth_answer": "P = \\vec{F} \\cdot \\vec{v}.",
        "expected_formulas": ["P = \\vec{F} \\cdot \\vec{v}"]
    },
    {
        "id": 93,
        "category": "Formula-Based",
        "question": "What is the formula for the work done by a constant torque?",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## **6.7 ANGULAR MOMENTUM IN CASE OF ROTATION ABOUT A FIXED AXIS**",
        "ground_truth_answer": "W = \\tau * \\theta.",
        "expected_formulas": ["W = \\tau \\theta"]
    },
    {
        "id": 94,
        "category": "Formula-Based",
        "question": "Write the formula for the acceleration due to gravity g at a height h above the Earth's surface (for h << R).",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.1 Acceleration due to gravity above the Earth’s surface**",
        "ground_truth_answer": "g(h) \\approx g_E * (1 - 2h/R_E).",
        "expected_formulas": ["g(h) = g_E (1 - \\frac{2h}{R_E})"]
    },
    {
        "id": 95,
        "category": "Formula-Based",
        "question": "Write the formula for the acceleration due to gravity g at a depth d below the Earth's surface.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## **7.4.2 Acceleration due to gravity below the Earth’s surface**",
        "ground_truth_answer": "g(d) = g_E * (1 - d/R_E).",
        "expected_formulas": ["g(d) = g_E (1 - \\frac{d}{R_E})"]
    },
    {
        "id": 96,
        "category": "Formula-Based",
        "question": "What is the mathematical formulation of Kepler's third law?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.2 KEPLER’S LAWS",
        "ground_truth_answer": "T^2 = k * R^3, where k = 4 * pi^2 / (G * M_S).",
        "expected_formulas": ["T^2 = \\frac{4 \\pi^2 R^3}{G M_S}", "T^2 \\propto R^3"]
    },
    {
        "id": 97,
        "category": "Formula-Based",
        "question": "Write the expression for the total kinetic energy of a body in rolling motion without slipping.",
        "reference_chapter": "## **CHAPTER SIX**",
        "reference_section": "## 6.11 KINEMATICS OF ROLLING MOTION",
        "ground_truth_answer": "K = (1/2) * M * v_cm^2 + (1/2) * I * w^2.",
        "expected_formulas": ["K = \\frac{1}{2} M v_{cm}^2 + \\frac{1}{2} I \\omega^2"]
    },
    {
        "id": 98,
        "category": "Formula-Based",
        "question": "Write the formula for the coefficient of restitution e for a direct collision between two bodies.",
        "reference_chapter": "## **CHAPTER FIVE**",
        "reference_section": "## **5.11.2 Collisions in One Dimension**",
        "ground_truth_answer": "e = (v_2f - v_1f) / (v_1i - v_2i).",
        "expected_formulas": ["e = \\frac{v_{2f} - v_{1f}}{v_{1i} - v_{2i}}"]
    },
    {
        "id": 99,
        "category": "Formula-Based",
        "question": "Write the formula for the orbital speed of a satellite orbiting at a height h above the Earth of radius R.",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.7 EARTH SATELLITES",
        "ground_truth_answer": "v_o = \\sqrt{GM / (R + h)}.",
        "expected_formulas": ["v_o = \\sqrt{\\frac{GM}{R+h}}"]
    },
    {
        "id": 100,
        "category": "Formula-Based",
        "question": "What is the formula for the gravitational field intensity due to a point mass M at a distance r?",
        "reference_chapter": "## **CHAPTER SEVEN**",
        "reference_section": "## 7.3 UNIVERSAL LAW OF GRAVITATION",
        "ground_truth_answer": "E = G * M / r^2 (or vector form E = -G * M / r^2 * r_hat).",
        "expected_formulas": ["E = \\frac{GM}{r^2}"]
    }
]

with open("benchmark_questions.json", "w") as f:
    json.dump(questions, f, indent=2)

print("Created benchmark_questions.json with 100 questions.")
