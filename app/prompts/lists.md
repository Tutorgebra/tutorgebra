**9. Lists, Sequences and Loci**
* **LISTS (CRITICAL):** Lists use curly braces and a descriptive name: `dataList = {2, 4, 4, 5, 7}`.
* **SEQUENCES (CRITICAL):** `Sequence(expression, k, start, end)` (e.g. `Sequence((k, k^2), k, 1, 5)` creates a list of 5 points).
* **LOCUS (CRITICAL):** `Locus(Q, P)` draws the path of point `Q` when `P` moves. `P` MUST be a point created with `Point(object)` or a slider.
* **CONVEX HULL (CRITICAL):** `hull1 = ConvexHull(pointList)`, where `pointList` is a list of points (e.g. `pointList = {P1, P2, P3, P4, P5}`). NEVER choose the hull vertices by hand with `Polygon()`: interior points would end up as vertices. The result is ONLY an outline: NEVER use `Area()` or `SetFilling()` on it.
  - CORRECT: `hull1 = ConvexHull({P1, P2, P3, P4, P5})`
  - FATAL ERROR: `hull1 = Polygon(P4, P1, P5, P2, P3)`
