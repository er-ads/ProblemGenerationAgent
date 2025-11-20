
sys_call1 = """
You are a physics problem analyzer. Your task is to analyze a physics question and its solution, then extract key information.

INPUT:
- Chapter Dictionary: {chapters_json}
- Physics Question: {question}
- Solution: {solution}

TASK:
Analyze the question and solution, then provide:

1. RELEVANT CHAPTERS: Identify exactly 2 chapters from the provided description in Chapter Dictionary that are most relevant to solving this problem.

2. VARIABLES: List all physical quantities (variables) involved in the problem. For each variable, specify:
   - A reasonable range of values [minimum, maximum]
   - The SI unit of measurement

3. ALTERNATE SCENARIOS: Generate 3 different real-world scenarios that could be used to create similar physics problems using the same concepts. Each scenario should be 1-2 sentences.

OUTPUT FORMAT (JSON):
{{
  "relevant_chapters": ["chapter_name_1", "chapter_name_2"],
  "variables": {{
    "variable_name": {{
      "range": [min_value, max_value],
      "unit": "unit_string"
    }}
  }},
  "alternate_scenarios": [
    "scenario description 1",
    "scenario description 2",
    "scenario description 3"
  ]
}}

Provide only the Strictly JSON output, no additional explanation, not any other characters preceding or following the JSON.
"""

sys_call1a = '''
You are a physics formula verifier. Your task is to check if a given set of formulas is sufficient to solve a physics problem.

INPUT:
- Original Solution: {solution}
- Identified Chapters: {identified_chapters}
- All Formulas Chapterwise: {all_chapters_json}

TASK:
"Check if the solution can be fully solved using only the formulas available in the chapters listed in Identified Chapters."
1. For each step in the original solution, attempt to map it carefully and thoroughly to one or more formulas from the chapters whose names appear in Identified Chapters.
- Ensure you do not incorrectly return “NO” if a valid mapping actually exists.
2. If all steps can be matched with these formulas, output YES.
3. If any step cannot be mapped, output NO and identify a missing chapter from the complete chapter list.
- The missing chapter must be distinct from those already present in Identified Chapters.
- Choose the most relevant chapter that contains the formula or concept needed for the unmapped step.

OUTPUT FORMAT (JSON):
If formulas are sufficient:
{{
  "status": "YES"
}}

If formulas are NOT sufficient:
{{
  "status": "NO",
  "missing_chapter": "chapter_name",
  "reason": "2-line explanation of what formula/concept is missing"
}}

Provide only the Strictly JSON output, no additional explanation, not any other characters preceding or following the JSON.
'''

sys_call2 = '''
You are a physics problem generator. Your task is to create a new physics word problem based on provided scenarios and formulas.

INPUT:
- Available Formulas: {available_formulas}
- Alternate Scenarios: {alternate_scenarios}
- Variables and Ranges: {variables}
- Previous Problems (avoid duplicates): {previous_problems}

TASK:
Generate a NEW physics word problem following these rules:

1.Pick one scenario from the alternate scenarios list.
2.Select 3-5 formulas from the available formulas (use their formula_ids).
- The most important requirement is that the physical situation described in the word problem maps correctly to the selected formulas. 
There must be no conceptual mismatch between the scenario and the equations used.
- The chosen formulas do not all need to come from the same chapter — you may select any formulas from the available_formulas list.
3.Create a word problem fully based on the chosen formulas and scenario.
4.The problem must be solvable using only the selected formulas — no additional equations should be needed.
5.Assign specific numerical values to all variables:
- Each value must fall within its allowed range.
- Mark exactly one variable as "NaN" (the unknown to be solved).
6. Ensure the new problem is meaningfully different from previous ones.

OUTPUT FORMAT (JSON):
{{
  "word_problem": "Complete problem statement as text",
  "formula_ids": ["formula_id_1", "formula_id_2"],
  "variables": {{
    "variable_name_1": {{
      "value": numerical_value,
      "unit": "unit_string"
    }},
    "unknown_variable": {{
      "value": "NaN",
      "unit": "unit_string"
    }}
  }}
}}

IMPORTANT:
- The word problem should be a complete, standalone problem that a student could solve
- Include all necessary context and information in the problem statement
- Use clear, simple language
- Exactly ONE variable must have value "NaN"

Provide only the Strictly JSON output, no additional explanation, not any other characters preceding or following the JSON.
'''

sys_call2a = '''
You are a physics problem generator. Your previous attempt had an issue. Generate a corrected physics word problem.

PREVIOUS ERROR: {error_message}

INPUT:
- Available Formulas: {available_formulas}
- Alternate Scenarios: {alternate_scenarios}
- Variables and Ranges: {variables}
- Previous Problems (avoid duplicates): {previous_problems}

TASK:
Generate a new physics word problem that corrects the previous mistake.

Guidelines:
1.Pick one scenario from the alternate scenarios list.
2.Select 2-4 formulas from the available formulas (use their formula_ids).
- The selected formulas must logically match the chosen scenario 
- there should be no mismatch between the physical situation and the equations used.
3.Create a word problem fully based on the chosen formulas and scenario.
- Difficulty level: The problem should be at least JEE Mains level, requiring clear conceptual understanding and 1-3 steps of reasoning.
4.The problem must be solvable using only the selected formulas — no additional equations should be needed.
- Optionally state direction/sign convention (downward positive) to avoid sign ambiguity.
5.Assign specific numerical values to all variables:
- Each value must fall within its allowed range.
- Mark exactly one variable as "NaN" (the unknown to be solved).
6. Ensure the new problem is meaningfully different from previous ones.
7. Explicitly fix the error from the last version.

Clarity Requirement:
Avoid any ambiguity regarding: Which variable is being asked for, and Which variable corresponds to each given numerical value.
However, do not spoon-feed the answer — the problem may still include a small element of inference or interpretation, as in real exam-style questions.

OUTPUT FORMAT (JSON):
{{
  "word_problem": "Complete problem statement as text",
  "formula_ids": ["formula_id_1", "formula_id_2"],
  "variables": {{
    "variable_name_1": {{
      "value": numerical_value,
      "unit": "unit_string"
    }},
    "unknown_variable": {{
      "value": "NaN",
      "unit": "unit_string"
    }}
  }}
}}

Provide only the Strictly JSON output, no additional explanation, not any other characters preceding or following the JSON.
'''

sys_call3 = '''
You are a Python code generator for physics problems. Your task is to write code that solves a physics word problem.

INPUT:
- Word Problem: {word_problem}
- IDs for Allowed Formulas: {formula_ids}
- Variables: {variables_dict}
- All Available Formulas: {available_formulas}

TASK:
Write Python code that solves for the unknown variable in the problem.

REQUIREMENTS:
1. Import only: math, numpy (if needed)
2. Define all known variables from the variables dictionary
3. Use ONLY the formulas whose formula_ids are specified in the input
4. For each of mentioned Formula IDs, while accessing, directly copy their corresponding "python_code" from available_formulas
5. Use these copied functions by calling them inside the solve() function
6. Solve for the unknown variable (the one with value "NaN")
7. Return a single float value as the answer
8. Include try-except error handling
9. Define everything inside a function called solve()

CODE STRUCTURE:
```
import math
# import numpy as np  # only if needed

# As-it-is Copied functions from available_formulas based on the given formula_ids

def solve():
    try:
        # Define known variables
        variable_1 = value_1
        variable_2 = value_2

        # Use the provided formula functions
        # result = formula_function(...)

        # Return the computed answer
        return answer
    except Exception as e:
        return None
```

OUTPUT:
Provide ONLY the complete Python code. No explanations, no markdown formatting, just the raw code.
'''

sys_call3a = '''
You are a Python code generator for physics problems. Your previous code failed. Generate corrected code.

PREVIOUS ERROR: {error_message}

INPUT:
- Word Problem: {word_problem}
- IDs for Allowed Formulas: {formula_ids}
- Variables: {variables_dict}
- All Available Formulas: {available_formulas}

TASK:
Write Python code that solves for the unknown variable in the problem.

REQUIREMENTS:
1. Import only: math, numpy (if needed)
2. Define all known variables from the variables dictionary
3. Use ONLY the formulas whose formula_ids are specified in the input
4. For each of mentioned Formula IDs, while accessing, directly copy their corresponding "python_code" from available_formulas
5. Use these copied functions by calling them inside the solve() function
6. Solve for the unknown variable (the one with value "NaN")
7. Return a single float value as the answer
8. Include try-except error handling
9. Define everything inside a function called solve()
8. FIX THE PREVIOUS ERROR: {error_message}

CODE STRUCTURE:
```
import math
# import numpy as np  # only if needed

# As-it-is Copied functions from available_formulas based on the given formula_ids

def solve():
    try:
        # Define known variables
        variable_1 = value_1
        variable_2 = value_2

        # Use the provided formula functions
        # result = formula_function(...)

        # Return the computed answer
        return answer
    except Exception as e:
        return None
```

OUTPUT:
Provide ONLY the complete Python code. No explanations, no markdown formatting, just the raw code.
'''
##################################################################################
# Chpaterwise Q-Soln for Testing
##################################################################################

# 1A - Friction (Tougher)
question1a = """
## Problem Statement

A block of mass m1 = 4.0 kg rests on a rough inclined plane of angle 30°. It is connected by a light string over a frictionless pulley to a hanging mass m2 = 6.0 kg. Coefficient of kinetic friction between m1 and plane is μ_k = 0.20. The system is released from rest. Find (a) the acceleration of the system, (b) the tension in the string, and (c) the speed of the heavier mass after 3.0 s. (Take g = 9.81 m/s²)
"""

solution1a = """
## Solution

1. Resolve forces on m1 along plane: downslope component of weight = m1 g sin30 = 4×9.81×0.5 = 19.62 N.
   Normal on m1: N = m1 g cos30 = 4×9.81×0.8660 = 33.98 N. Kinetic friction f_k = μ_k N = 0.20×33.98 = 6.796 N (opposes motion).

2. For m2 (hanging): weight = m2 g = 6×9.81 = 58.86 N.

3. Assume m2 goes down, m1 goes up the plane. Net driving force = m2 g − (m1 g sin30 + f_k) 
   = 58.86 − (19.62 + 6.796) = 32.444 N.

4. Acceleration: a = Net / (m1 + m2) = 32.444 / (4 + 6) = 32.444 / 10 = 3.2444 m/s².

5. Tension from m1 equation: T − m1 g sin30 − f_k = m1 a ⇒ T = m1 a + m1 g sin30 + f_k
   But since friction was included in net above taken opposite to motion, using m1 a + (m1 g sin30) + (−f_k) is redundant;
   easier: For m1 along plane (up positive): T = m1 a + m1 g sin30 + f_k = 4×3.2444 + 19.62 + 6.796 = 32.60 N (approx).

6. Speed of m2 after t = 3.0 s (from rest): v = a t = 3.2444 × 3.0 = 9.733 m/s.

**Final Answers:**  
(a) a ≈ 3.244 m/s², (b) T ≈ 32.60 N, (c) v ≈ 9.73 m/s.
"""

# 1B - Friction (Alternate)
question1b = """
## Problem Statement

A 10 kg block on a horizontal floor is attached to a smaller block m = 3 kg by a light string passing over a smooth pulley. The contact between the 10 kg block and floor has μ_s = 0.35 and μ_k = 0.28. A horizontal force F is applied to the 10 kg block toward the pulley. Determine the minimum F required to start motion of the system, and if F = 120 N, find the acceleration magnitude and direction. (g = 9.81 m/s²)
"""

solution1b = """
## Solution

1. When motion is imminent, compare tensions and static friction. Let T be tension in string due to m hanging (downward).
   If system tends to move so that smaller mass lifts or lowers, check directions. Here applied F pulls 10 kg toward pulley, increasing tendency of 3 kg to lift.

2. Normal on 10 kg is N = 10×9.81 = 98.1 N. Max static friction f_s(max) = μ_s N = 0.35×98.1 = 34.335 N.

3. For impending motion, analyze limiting case: If F barely causes the 3 kg block to lift, tension T equals weight of 3 kg = 3×9.81 = 29.43 N.
   Net horizontal on 10 kg at threshold: F - T = f_s(max) ⇒ F_min = f_s(max) + T = 34.335 + 29.43 = 63.765 N.

4. If F = 120 N > F_min, kinetic friction acts: f_k = μ_k N = 0.28×98.1 = 27.468 N.
   Net horizontal force on 10 kg: F - T - f_k = 120 - T - 27.468.
   For 3 kg (vertical): up positive: T - 3g = 3 a (if block accelerates up). For 10 kg: (120 - T - 27.468) = 10 a.
   Solve the two equations: From vertical: T = 3g + 3a = 29.43 + 3a.
   Substitute: 120 - (29.43 + 3a) - 27.468 = 10 a ⇒ 120 - 29.43 - 27.468 = 13 a ⇒ 63.102 = 13 a ⇒ a = 4.854 m/s².

5. Direction: positive (3 kg moves up; 10 kg moves toward pulley).

**Final Answers:**  
F_min ≈ 63.77 N. For F = 120 N, a ≈ 4.85 m/s² (3 kg upward).
"""

# 2A - Work, Power, Energy (Tougher)
question2a = """
## Problem Statement

A block of mass 2.0 kg starts from rest at the top of a smooth wedge of height 4.0 m and angle 37°. The block slides down a distance along the wedge to reach the horizontal table and then compresses a spring (k = 800 N/m) by x before momentarily stopping. Coefficient of kinetic friction on the horizontal table is μ_k = 0.12. Find the compression x of the spring. (Take g = 9.81 m/s²; sin37≈0.6, cos37≈0.8)
"""

solution2a = """
## Solution

1. Mechanical energy at top: E_top = m g h = 2×9.81×4 = 78.48 J.

2. When it reaches the table, height is zero; convert potential to kinetic minus work done by friction on table region before spring.
   Let distance traveled on table before fully compressing spring be d = x_spring_travel (equal to spring compression x).
   Work done by kinetic friction on table: W_f = −μ_k m g × d = −(0.12×2×9.81)×x = −(2.3544) x J.

3. At the instant block compresses spring by x and stops, kinetic energy becomes zero. Energy balance:
   Initial energy 78.48 = Energy stored in spring (½ k x²) + work lost to friction on table (2.3544 x).

   So: 0.5×800×x² + 2.3544 x − 78.48 = 0
   → 400 x² + 2.3544 x − 78.48 = 0

4. Solve quadratic: x = [−2.3544 ± sqrt(2.3544² + 4×400×78.48)] / (2×400)
   Discriminant ≈ 5.5446 + 125,568 = 125,573.5
   sqrt ≈ 354.37
   Positive root: x ≈ (−2.3544 + 354.37) / 800 ≈ 352.0156 / 800 ≈ 0.4400 m.

**Final Answer:**  
Compression x ≈ 0.44 m.
"""

# 2B - Work, Power, Energy (Alternate)
question2b = """
## Problem Statement

An electric motor delivers a constant power of 600 W to pull a 40 kg sled up a uniform incline of angle 20°. The rope is parallel to the plane and the system overcomes kinetic friction μ_k = 0.10. Find (a) the steady speed of the sled when power just balances resistive forces, and (b) the time to raise the sled by 50 m at that speed. (g = 9.81 m/s²)
"""

solution2b = """
## Solution

1. Resistive power needed to overcome gravity and friction at steady speed v:
   Resistive force along plane = m g sin20 + μ_k m g cos20.

   Compute: sin20 ≈ 0.3420, cos20 ≈ 0.9397.
   m g sin20 = 40×9.81×0.3420 = 134.33 N.
   Normal = 40×9.81×0.9397 = 368.64 N. Friction = μ_k × Normal = 0.10×368.64 = 36.864 N.
   Total resistive force = 134.33 + 36.864 = 171.194 N.

2. Power P = F_resistive × v ⇒ v = P / F_resistive = 600 / 171.194 ≈ 3.505 m/s.

3. Time to raise by s = 50 m along plane: t = s / v = 50 / 3.505 ≈ 14.27 s.

**Final Answers:**  
(a) v ≈ 3.51 m/s, (b) t ≈ 14.3 s.
"""

# 3A - Circular Motion (Tougher)
question3a = """
## Problem Statement

A small mass m = 0.5 kg is attached to a string of length L = 0.80 m and executes uniform circular motion in a horizontal circle of radius r = 0.60 m (a conical pendulum). The period of revolution is T = 1.20 s. Find (a) the speed of the mass, (b) the tension in the string, and (c) the angle the string makes with the vertical. (g = 9.81 m/s²)
"""

solution3a = """
## Solution

1. Speed: v = 2π r / T = 2π×0.60 / 1.20 = π ≈ 3.1416 m/s.

2. Centripetal force required: F_c = m v² / r = 0.5 × (3.1416)² / 0.60 ≈ 8.2247 N.

3. Vertical component of tension balances weight: T cosθ = m g = 0.5×9.81 = 4.905 N.
   Horizontal component provides centripetal force: T sinθ = F_c = 8.2247 N.

   So tanθ = (T sinθ)/(T cosθ) = F_c / (m g) = 8.2247 / 4.905 ≈ 1.676 ⇒ θ ≈ 59.6°.

4. Tension: T = m g / cosθ = 4.905 / cos59.6°; cos59.6° ≈ 0.5079 ⇒ T ≈ 4.905 / 0.5079 ≈ 9.58 N.

**Final Answers:**  
(a) v ≈ 3.14 m/s, (b) T ≈ 9.58 N, (c) θ ≈ 59.6° from vertical.
"""

# 3B - Circular Motion (Alternate)
question3b = """
## Problem Statement

A car negotiates a circular turn of radius 80 m on a flat road at speed 18 m/s. If the coefficient of static friction is μ_s = 0.22, determine whether the car will skid. If not, find the maximum safe speed. (g = 9.81 m/s²)
"""

solution3b = """
## Solution

1. Maximum centripetal force without skidding: F_c(max) = μ_s m g.

   For safe turning: m v² / r ≤ μ_s m g ⇒ v_max = sqrt(μ_s g r).

2. Compute v_max = sqrt(0.22 × 9.81 × 80) = sqrt(172.584) ≈ 13.14 m/s.

3. Given speed 18 m/s > 13.14 m/s ⇒ car will skid.

**Final Answers:**  
v_max ≈ 13.14 m/s. At 18 m/s skidding occurs.
"""

# 4A - Centre of Mass (Tougher)
question4a = """
## Problem Statement

Three particles lie in the plane: m1 = 2.0 kg at (0, 0), m2 = 3.0 kg at (4.0 m, 0), and m3 = 5.0 kg at (1.0 m, 3.0 m). Find (a) the coordinates of the centre of mass, and (b) the distance of the centre of mass from the origin.
"""

solution4a = """
## Solution

1. x_cm = (m1 x1 + m2 x2 + m3 x3) / (m1 + m2 + m3) = (2×0 + 3×4 + 5×1) / 10 = (0 + 12 + 5) / 10 = 17 / 10 = 1.7 m.

2. y_cm = (m1 y1 + m2 y2 + m3 y3) / total = (2×0 + 3×0 + 5×3) / 10 = 15 / 10 = 1.5 m.

3. Distance from origin: r = sqrt(x_cm² + y_cm²) = sqrt(1.7² + 1.5²) = sqrt(2.89 + 2.25) = sqrt(5.14) ≈ 2.267 m.

**Final Answers:**  
(a) (x_cm, y_cm) = (1.70 m, 1.50 m), (b) r ≈ 2.27 m.
"""

# 4B - Centre of Mass (Alternate)
question4b = """
## Problem Statement

A uniform thin rod of length 2.0 m and mass 6.0 kg lies along the x-axis from x = -1.0 m to x = +1.0 m. Two point masses, 2.0 kg and 4.0 kg, are attached at x = 2.0 m and x = -2.0 m respectively. Find the x-coordinate of the combined centre of mass.
"""

solution4b = """
## Solution

1. Rod's mass m_rod = 6.0 kg; its centre is at x = 0 (because symmetric).

2. Total mass = 6 + 2 + 4 = 12 kg.

3. x_cm = (m_rod×0 + 2×2.0 + 4×(-2.0)) / 12 = (0 + 4 − 8) / 12 = −4 / 12 = −0.333... m.

**Final Answer:**  
x_cm ≈ −0.333 m (i.e., 0.333 m left of origin).
"""

# 5A - Rigid Body Dynamics (Tougher)
question5a = """
## Problem Statement

A uniform rod of length L = 1.5 m and mass M = 4.0 kg is pivoted frictionlessly at one end and held horizontal. It is released from rest. (a) Find the angular acceleration α of the rod just after release, and (b) the linear acceleration of the free end just after release. (g = 9.81 m/s²)
"""

solution5a = """
## Solution

1. Torque about pivot due to gravity on rod: τ = M g (L/2) = 4×9.81×0.75 = 29.43 N·m.

2. Moment of inertia about pivot for uniform rod: I = (1/3) M L² = (1/3)×4×(1.5)² = (4/3)×2.25 = 3.0 kg·m².

3. Angular acceleration: α = τ / I = 29.43 / 3.0 = 9.81 rad/s².

4. Linear acceleration of free end: a_tip = α × L = 9.81 × 1.5 = 14.715 m/s².

**Final Answers:**  
(a) α = 9.81 rad/s², (b) a_tip ≈ 14.72 m/s².
"""

# 5B - Rigid Body Dynamics (Alternate)
question5b = """
## Problem Statement

A solid cylinder of mass 6.0 kg and radius 0.20 m rolls without slipping down an incline of angle 30°. Determine the linear acceleration of its centre of mass. (g = 9.81 m/s²)
"""

solution5b = """
## Solution

1. For rolling without slipping, a = g sinθ / (1 + I/(m r²)). For solid cylinder I = (1/2) m r² ⇒ I/(m r²) = 1/2.

2. So a = g sinθ / (1 + 1/2) = (2/3) g sinθ.

3. For θ = 30°, sin30 = 0.5 ⇒ a = (2/3) × 9.81 × 0.5 = (2/3) × 4.905 = 3.27 m/s².

**Final Answer:**  
Acceleration of centre of mass ≈ 3.27 m/s².
"""



##################################################################################
# Basic Q-Soln used for Prototyping
##################################################################################

question = """
## Problem Statement\n\nTwo blocks of masses m 1
=4kg and m 2​ =2 kg are connected by a light, inextensible string. The string passes over a smooth, massless pulley. The block m 
1 is placed on a smooth horizontal surface, while the block m 2 hangs vertically. Find the acceleration of the blocks and the tension in the string. (Assume g=10 m/s 
2 )
"""

solution = """
## Solution\n\n### 1. Identifying Forces and Drawing Free-Body Diagrams (FBDs)\n\nFirst, we analyze the forces acting on each block separately.\n\nFor block m 1
(on the horizontal surface):\n* Weight (W1 ): Acts vertically downwards. W 1 =m 1 g\n* Normal Reaction (N): Acts vertically upwards, perpendicular to the surface.\n* Tension (T): Acts horizontally to the right, along the string.\n\nSince the surface is smooth, there is no friction.\nThe block only moves horizontally, so the vertical forces are balanced (N=W 
1 ) and the net horizontal force causes acceleration.\n\nFor block m 2(hanging vertically):\n* Weight (W2
 ): Acts vertically downwards. W 2 =m2 g\n* Tension (T): Acts vertically upwards, along the string.\n\nThis block accelerates downwards.\n\n### 2. Applying Newton's Second Law (F 
net =ma)\n\nLet 'a' be the acceleration of the system. Since the string is inextensible, both blocks move with the same magnitude of acceleration.\n\nEquation for block m 
1 \nThe only horizontal force is the tension T. \n T=m 1 a...(1)\n\nEquation for block m 2​ :\nThe net force is the difference between its weight (acting down) and the tension (acting up). The block accelerates downwards, so we take the downward direction as positive.\n
W 2 −T=m 
2
​
 a
\n

m 
2
​
 g−T=m 
2
​
 a
...
(2)
\n\n### 3. Solving the Equations\n\nWe now have a system of two linear equations with two variables, a and T.\n\nStep 1: Find the acceleration (a)\n\nSubstitute the value of T from equation (1) into equation (2):\n

m 
2
​
 g−(m 
1
​
 a)=m 
2
​
 a
\n\nNow, rearrange the equation to solve for a:\n

m 
2
​
 g=m 
1
​
 a+m 
2
​
 a
\n

m 
2
​
 g=(m 
1
​
 +m 
2
​
 )a
\n

a= 
m 
1
​
 +m 
2
​
 
m 
2
​
 g
​
 
\n\nPlugging in the given values:\n

a= 
4 kg+2 kg
(2 kg)(10 m/s 
2
 )
​
 = 
6
20
​
  m/s 
2
 
\n

a≈3.33 m/s 
2
 
\n\nStep 2: Find the tension (T)\n\nNow substitute the value of a back into equation (1):\n

T=m 
1
​
 a
\n

T=(4 kg)×( 
6
20
​
  m/s 
2
 )= 
6
80
​
  N
\n

T≈13.33 N
\n\n***\n\n## Final Answer\n\nThe acceleration of the system is a=3.33 m/s 
2
 .\nThe tension in the string is T=13.33 N.\n
"""