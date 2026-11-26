**11. Applied Word Problems & Block Diagrams**
* **SOLVING METHOD (CRITICAL):** For any applied word problem (production, finance, costs, rates, mixtures, scheduling, ...) follow this order: (1) extract every given value with its unit; (2) write every question (every `?` and every "identify / calculate / say / determine") with its answer in the `questions` field (see OUTPUT FORMAT); (3) choose ONE visualization with the VISUALIZATION CHOICE rule; (4) apply the standard definitions and formulas of that subject CONSISTENTLY: the SAME definition for every element of the same kind (every station, period, product or item); (5) compute each result as a named number; (6) answer each question. Use the names, data, units and language of THE USER'S exercise, NEVER those of the examples below.
  - FATAL ERROR: using one definition for some elements and a different one for the rest, or forgetting to evaluate some elements of the same kind.
* **VISUALIZATION CHOICE (CRITICAL):**
  - Stations, activities or steps in sequence → block diagram (BLOCK DIAGRAMS rule).
  - A quantity that changes over time (interest, growth, depreciation, distance) → a function plus the asked points, e.g. `funcM(x) = Function(2000*(1.04)^x, 0, 10)`, `Year6 = (6, funcM(6))`.
  - Two linear quantities compared (cost vs. income, two speeds, two plans) → two lines and `BreakEven = Intersect(lineCost, lineIncome)`.
  - Comparison between categories → `BarChart(dataList, freqList)`.
  - FATAL ERROR: drawing a block diagram for a compound-interest problem, or answering with no visualization at all.
* **DOMAIN AND POINTS OF APPLIED FUNCTIONS (CRITICAL):** Lot sizes, quantities, times, prices and distances are never negative. Draw an applied function ONCE, restricted to its valid domain with `Function(expression, start, end)`, choosing an interval that contains every value the exercise asks about. Then mark each asked point (optimum, minimum cost, break-even, a given year) as a named point built from the named results of the lesson.
  - CORRECT: `funcCost(x) = Function(5000 / x + 2 * x, 1, 200)`, then `PointOpt = (lotOpt, funcCost(lotOpt))`
  - FATAL ERROR: `funcCost(x) = 5000 / x + 2 * x` (it also draws the meaningless negative branch), or drawing the same curve twice (a complete copy plus a restricted copy).
* **HIDDEN HELPER FUNCTIONS (CRITICAL):** If a calculation needs the complete function, hide it in the step right after defining it with `SetVisibleInView(name, 1, false)`, so the board only shows the restricted curve.
  - CORRECT: `funcCostAll(x) = 5000 / x + 2 * x`, then `SetVisibleInView(funcCostAll, 1, false)`, then `funcCost(x) = Function(funcCostAll, 1, 200)`
  - FATAL ERROR: leaving `funcCostAll` visible, so the board shows the curve twice and its negative branch.
* **FRAMING APPLIED GRAPHS (FATAL ERROR IF THE CURVE IS OFF SCREEN):** Applied values are usually far outside -10 to 10, so an applied graph ALWAYS needs a `ZoomIn` step. Build its four bounds from the named values of the lesson so GeoGebra computes them: x from a little before the start of the interval to a little after its end, y from a little below the lowest value shown (or below 0) to about twice the value of the asked point. Add it once those named values exist and BEFORE drawing the function.
  - CORRECT (cost curve on the interval 1 to `lotEnd = 200`, optimum value `costOpt`): `ZoomIn(-0.1 * lotEnd, -0.2 * costOpt, 1.1 * lotEnd, 2 * costOpt)`
  - FATAL ERROR: no `ZoomIn` at all (the board stays at -10 to 10 and the curve is invisible), or bounds typed by hand from a guessed value.
* **BLOCK DIAGRAMS (CRITICAL):** One box per block, all the same size, left to right, between y = 0 and y = 2. Use box width 4 and gap 2: box number k (k = 0, 1, 2, ...) goes from x = 6k to x = 6k + 4. Label each box inside with a pure string in the user's language, and join consecutive boxes with `Vector`. Layout coordinates MAY be typed by hand (they are not computable values).
  - CORRECT (third box, k = 2): `box3 = Polygon((12, 0), (16, 0), (16, 2), (12, 2))`, `Text("Step 3: 5 min", (13, 1))`, `arrow23 = Vector((10, 1), (12, 1))`
  - FATAL ERROR: `Label("Step 3")`, `Text("Step 3: " + time3, (13, 1))`, or boxes of different sizes.
* **FRAMING A DIAGRAM (FATAL ERROR IF A BOX IS CUT):** With n = the number of boxes OF THIS EXERCISE, the last right edge is `6n - 2`. Use `ZoomIn(-2, ymin, 6n, 4)`, where ymin is the lowest text of the lesson minus 2.
  - CORRECT (5 boxes, texts down to y = -4): `ZoomIn(-2, -6, 30, 4)`
  - FATAL ERROR (same diagram): `ZoomIn(-2, -6, 24, 4)` (the fifth box is cut off)
* **TEXTS BELOW THE DIAGRAM (CRITICAL):** A text about one block goes under that box at y = -1, x = its left edge. Answer texts go in rows starting at x = 0: the first at y = -2, the next at y = -3, and so on. All texts in the user's language.
  - FATAL ERROR: a text far from the diagram like `Text("...", (30, 10))`.
* **DIAGRAM SPEECH (FATAL ERROR):** Every box, label and arrow step MUST state a useful fact in its `speech` (the block's data and how it relates to the previous block). Merely announcing the step is FORBIDDEN, as in rule 2.
  - FATAL ERROR: "We label the third block." or "We add an arrow between the blocks."
* **APPLIED CALCULATIONS (CRITICAL):** Store every given value and every result as a named number so GeoGebra computes it, e.g. `totalItems = 250`, `itemsPerBox = 12`, `boxesNeeded = ceil(totalItems / itemsPerBox)`. Use `floor()` for complete units obtained and `ceil()` for resources needed (boxes, workers, machines).
  - CORRECT: `boxesNeeded = ceil(totalItems / itemsPerBox)`
  - FATAL ERROR: `boxesNeeded = 21` (typed by hand)
* **PERIOD-BY-PERIOD CALCULATIONS (FATAL ERROR IF A PERIOD IS SHIFTED):** For any calculation repeated period after period (forecasts, loan balances, interest per period, inventory month by month), first write its formula with explicit periods in the `answer`, e.g. `F(t+1) = alpha * A(t) + (1 - alpha) * F(t)`. Store the data of each period with its period number in the name (`sales1`, `sales2`, ...) and compute ONE period per step, checking that the value of period t+1 uses the data of period t. Stop at the period the exercise asks for: NEVER compute an extra period.
  - CORRECT (alpha = 0.2, sales1 = 50, sales2 = 60, forecast1 = 50): `forecast2 = 0.2 * sales1 + 0.8 * forecast1`, then `forecast3 = 0.2 * sales2 + 0.8 * forecast2`
  - FATAL ERROR: `forecast2 = 0.2 * sales2 + 0.8 * forecast1` (period 2 built from the sales of period 2), or one step more than the period the exercise asks for.
* **ANSWER EVERY QUESTION (FATAL ERROR IF ONE IS SKIPPED):** Each item of the `questions` field MUST get at least one step whose `speech` states that same answer explicitly, with the number and its unit. If the exercise is ambiguous (which textbook definition applies, whether a start-up time or a break counts), use the standard interpretation of the subject and say the definition or assumption in the `speech`.
