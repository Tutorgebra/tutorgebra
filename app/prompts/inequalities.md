**2b. Inequalities & Linear Programming**
* **INEQUALITIES & LINEAR PROGRAMMING (CRITICAL):** If a user asks for inequalities or a feasible region, DO NOT try to use `Intersect()`, `Vertex()`, or `Focus()` on the inequality areas. You CANNOT intersect inequalities in GeoGebra. Instead, follow these exact steps: 
  1. Define the inequality areas (e.g. `2x + 3y <= 120`) to shade the region.
  2. DO NOT use `Intersect(ineq1, ineq2)`. Instead, define each boundary as a LINE equation (e.g. `lineA: 2*x + 3*y = 120`, `lineB: x + y = 50`).
  3. Get each vertex of the feasible region by intersecting two boundary lines and assigning it a name (e.g. `V1 = Intersect(lineA, lineB)`, `V2 = Intersect(lineA, xAxis)`). NEVER calculate vertex coordinates by hand.
  4. Finally, draw the region using `Polygon(V1, V2, V3)` in sequential order.
