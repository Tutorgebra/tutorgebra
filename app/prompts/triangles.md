**3b. Triangles**
* **ADVANCED TRIANGLES (CRITICAL):**
  * **INCENTER OF TRIANGLES (CRITICAL):** There is NO 'Incenter' command. Use `incirc1 = Incircle(A, B, C)` to draw the inscribed circle, and then `Center(incirc1)` to plot the incenter point.
  * **CIRCUMCIRCLE OF TRIANGLES (CRITICAL):** There is NO 'Circumcenter' command. Do NOT hallucinate `Circumcenter(A,B,C)`. To draw a circumcircle, you MUST use `Circle(A, B, C)` with the 3 vertices. To find the circumcenter point, first draw the circle `circ1 = Circle(A, B, C)`, and then use `Center(circ1)`.
  * **CENTROID OF TRIANGLES (CRITICAL):** Centroid requires a Polygon object, NOT 3 points: `Centroid(Polygon(A, B, C))`.
  * **ORTHOCENTER OF TRIANGLES (CRITICAL):** There is NO 'Orthocenter' command. Use `OrthoH = TriangleCenter(A, B, C, 4)`. To draw an altitude use `PerpendicularLine(A, Line(B, C))`.
