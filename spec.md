# Concrete Pour Planner

## Purpose

A Python desktop planning tool for a concrete pour. The user outlines a slab on satellite imagery or enters rectangular dimensions, and the app calculates:

- Slab area and concrete volume to order
- Number of truckloads
- Number of trucks required in rotation
- Planned truck arrivals
- Pour duration and finish time
- Concrete cost estimate
- Whether the pour fits within available working time

The app is intended for construction management students, superintendents, and project engineers preparing an order for a batch plant.

## Platform and Architecture

- Build as a native Python desktop application using the standard-library `tkinter` toolkit.
- Use the standard `ttk` widgets for a consistent, accessible interface.
- Use no web server and no browser runtime.
- Package dependencies should be minimized. A third-party map widget may be used only if it supports Esri World Imagery tiles and is optional to run offline. If no compatible map package is available, provide a clear map-unavailable state rather than substituting fake results.
- The map tile source is Esri World Imagery:

  `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`

- Display the required Esri attribution in the application.
- Do not require API keys or server-side services.
- Store the application source in a normal Python package layout unless a later implementation spec says otherwise.
- Do not use HTML, JavaScript, Leaflet, or browser-only APIs.

## Window Layout

Use one resizable main window with a two-column layout on wide screens:

- Left column: map and slab controls
- Right column: summary cards, concrete cost, set-time checker, truck timeline, and batch-plant order

On narrow windows, stack the sections vertically in this order:

1. Map and slab controls
2. Summary cards
3. Concrete cost estimate
4. Set-time checker
5. Truck timeline
6. Batch-plant order

Use a clean construction-app style:

- White or light-neutral cards with subtle shadows or borders
- One contrasting accent color for primary controls and active states
- A modern system font; do not require a downloaded font
- Clear labels, consistent spacing, and visible keyboard focus indicators
- Scrollable input and detail areas when needed

## Initial State

- Open with an example slab already drawn near the center of the map.
- The example must not change the default input values.
- Use a 40 ft by 60 ft typed slab as the immediate example when the map and dimensions are available.
- The example may be deleted or replaced using the Draw Slab and typed-dimension controls.
- All numeric input fields show their default values.

## Slab-Mode Inputs

Provide separate Draw Slab and typed-dimension controls. The drawing mode and typed-dimension mode are alternate ways to define the same slab.

### Drawn Mode

- A **Draw Slab** button starts a drawing session.
- The user adds corners by clicking on the map.
- A polygon requires at least three corners and must not self-intersect.
- Finish by double-clicking or clicking the first point.
- Selecting **Draw Slab** again, starting a new drawing, or canceling discards only the unfinished polygon.
- A completed slab remains visible after canceling.
- Completed corners may be dragged. Dragging immediately updates the area and every dependent result.
- A completed polygon must remain a valid simple polygon.
- Keyboard users must be able to activate Draw Slab and Cancel Drawing with named buttons or shortcuts.

### Typed-Dimension Mode

- Provide separate **Length** and **Width** fields in feet.
- Switching to typed mode replaces the current outline with a rectangle centered at the current map center.
- The typed rectangle has north-south and east-west edges.
- Switching to draw mode clears the typed rectangle and starts a new drawing session.
- Each mode retains no separate slab state; the slab comes from the active mode only.
- Length and Width must be finite decimal values greater than `0`.
- Do not impose a maximum dimension.
- Negative, zero, empty, and nonnumeric values are invalid.
- Invalid values show an inline message near the field and clear or withhold calculated results derived from the invalid slab.

## Other Inputs

All numeric inputs permit decimal values unless stated otherwise.

| Input | Default | Validation |
| --- | ---: | --- |
| Slab thickness | `6` inches | Finite decimal greater than `0` |
| Concrete mix | Blank | Optional text name or designation |
| Waste allowance | `5` percent | Finite decimal greater than or equal to `0`; no upper limit |
| Truck capacity | `10` cubic yards | Finite decimal greater than `0` |
| One-way travel time | `20` minutes | Finite decimal greater than `0` |
| Placement rate | `30` cubic yards/hour | Finite decimal greater than `0` |
| Washout and reload time | `10` minutes/truck | Finite decimal greater than or equal to `0` |
| First-truck arrival | `7:00 AM` | Valid local time |
| Price per cubic yard | Blank | Finite decimal greater than or equal to `0`; required for cost estimate |
| Optional short-load fee | Blank | Finite decimal greater than or equal to `0`; blank means no fee |
| Available working time | Blank | Finite decimal greater than `0` when entered |

For the arrival time, accept a 12-hour time with AM/PM and a suitable local 24-hour or Tkinter control value. A valid schedule must continue across midnight.

Every valid input change must update the app immediately without reloading or restarting it.

## Validation Behavior

- Invalid or empty core values show a clear inline validation message.
- A core value invalidity must not overwrite valid results with a misleading result derived from stale or invalid values.
- Invalid cost inputs clear only the cost estimate.
- An invalid set-time value clears or withholds only the set-time result.
- A short next-step hint reflects the current state, for example:
  - “Choose Draw Slab and click at least three corners.”
  - “Drag a corner or enter dimensions.”
  - “Correct the highlighted input.”
  - “Enter a concrete price to calculate the cost.”
- The summary and timeline must retain no calculated values until all required core values are valid.

## Calculations

### Slab Area

For a drawn polygon, calculate area in square feet using:

`A = R² × |sum over edges of (lon2 - lon1) × (2 + sin lat1 + sin lat2)| / 2`

- Angles are in radians.
- `R = 6,378,137 m`.
- `1 m² = 10.7639 ft²`.

For a typed rectangle, use:

`area = length × width`

Display area to practical precision, but never use a rounded display value for later calculations.

### Volume

`unwasted_volume = area × thickness / 12 / 27`

`volume_with_waste = unwasted_volume × (1 + waste / 100)`

Round the volume with waste up to the next `0.5 cubic yards`:

`ordered_volume = ceil(volume_with_waste × 2) / 2`

Keep the unrounded ordered-volume calculation separate from display rounding.

### Truckloads

`truckloads = ceil(ordered_volume / truck_capacity)`

Every load is full truck capacity except the final load. For example, 47 cubic yards with 10-cubic-yard trucks produces loads of `10, 10, 10, 10, 7`.

Use the full capacity of every load except the final remainder.

### Unload Times

- Full-truck unload time in hours: `truck_capacity / placement_rate`
- Convert this value to minutes for schedules.
- Partial final-load unload time: `final_load_volume / placement_rate` hours
- Convert partial unload time to minutes.
- The partial final load must not use the full-truck unload duration.

### Truck Arrivals

- Truck 1 arrives at the first-truck arrival time.
- Truck `k` arrives at `start + (k - 1) × full_truck_unload_minutes`.
- Arrival times wrap across midnight and display as local clock times.
- The partial final load's unload time does not change the spacing of earlier arrivals.

### Round Trip

`round_trip_minutes = 2 × one_way_travel + full_truck_unload_minutes + washout_minutes`

Use the full-truck unload time even when the final load is partial.

### Trucks in Rotation

`trucks_in_rotation = ceil(round_trip_minutes / full_truck_unload_minutes)`

Limit the result to the number of truckloads. The result is at least `1`.

Truck assignments repeat cyclically:

- Load 1 uses truck 1
- Load 2 uses truck 2
- Continue until truck N
- The next load returns to truck 1

### Pour Duration and Finish Time

`pour_duration = (truckloads - 1) × full_truck_unload_minutes + final_load_unload_minutes`

- Use the full-truck unload time for the final load only when the final load is full.
- Finish time is the first arrival plus the pour duration.
- Wrap finish time across midnight.
- Do not include later plant return trips or washout after the pour finishes.

## Outputs

### Map

- Keep the completed slab outline visible.
- Show a map label containing area and ordered volume, for example:

  `2,400 ft² • 47.0 cy`

- If a slab or required input is invalid, remove calculated text from the label and show the nearest applicable validation message.
- Corners remain draggable after a drawn polygon is completed.
- The map label must be readable with enough contrast on satellite imagery.

### Summary Cards

Display:

- Concrete to order in cubic yards
- Truckloads as an integer
- Trucks in rotation as an integer
- Pour duration in hours and minutes, or in minutes below one hour
- Finish time as a local clock time

Use the rounded order volume and practical time rounding for display only.

### Truck Schedule Timeline

Use a horizontally scrollable, clock-time Gantt-style timeline.

- Show one row per truckload.
- Number each row by load and show its cyclic truck number.
- Show travel out, unloading, trip back, and washout as distinct colors and labels.
- Model each assigned truck's complete sequence, including later loads on later cycles.
- Use the full unload duration for full loads.
- Use the partial unload duration for the final partial load.
- Start the axis at or before the first truck arrival.
- Extend the axis through all segments needed to display the scheduled rows.
- When the schedule crosses midnight, label or otherwise distinguish wrapped clock times.
- Each timeline segment is keyboard focusable where practical.
- Focus or hover on a segment displays exact start and end times.
- Provide a screen-reader text equivalent for segment timing.

The timeline may have a legend for travel, unloading, return, and washout colors.

### Batch-Plant Order

Show a plain-text order containing:

- Ordered volume
- Number of loads
- First-truck arrival time
- Arrival spacing
- Cyclic truck requirement
- The size of every full load
- An explicit partial-load entry for the final load

Include a **Copy** button that copies the text to the system clipboard.

- On success, briefly show **Copied**.
- If clipboard access fails, keep the text visible and report that automatic copying was unsuccessful.

## Project Save and Open

- Provide **Save Project** and **Open Project** actions in a **File** menu.
- Support `Ctrl+S` for Save Project and `Ctrl+O` for Open Project.
- Save projects as a JSON-based `.cppj` file with format and version metadata.
- Save all project inputs, including:
  - Slab mode
  - Typed length and width
  - Slab thickness
  - Optional concrete mix name or designation
  - Waste allowance
  - Truck capacity
  - One-way travel time
  - Placement rate
  - Washout and reload time
  - First-truck arrival time
  - Concrete price
  - Optional short-load fee
  - Available working time
- Save the completed outline or shape as geographic coordinates.
- Save the map position and zoom level and the window geometry.
- Save derived quantities as project metadata when available; reopening must recalculate from saved inputs and restore the same values.
- Opening a saved project must restore every saved input and the active slab outline or typed shape.
- Invalid, unsupported, or corrupted project files must show an error and leave the current project unchanged.

## Cost Estimator

The concrete cost estimator is included; all other cost modeling is outside scope.

### Inputs

- Price per cubic yard is required to show an estimate and defaults to blank.
- Short-load fee is optional and defaults to blank.
- Blank short-load fee means no fee.
- Both values must be finite decimals greater than or equal to `0`.
- Show inline validation for invalid values.

### Calculations

`concrete_cost = ordered_volume × price_per_cubic_yard`

A short-load fee applies once when the final load is smaller than truck capacity. The fee does not apply when the final load equals the full truck capacity.

`estimated_total = concrete_cost + applicable_short_load_fee`

### Outputs

- Display estimated total and a breakdown of:
  - Concrete cost
  - Short-load fee, if applicable
- Format amounts as USD.
- Update immediately when cost inputs or core volume/load inputs change.
- Keep the cost estimate separate from the batch-plant order text.
- An invalid cost input clears only the cost estimate, not core quantities or the timeline.

## Set-Time Checker

### Input

- Available working time is entered in minutes and defaults to blank.
- When entered, it must be a finite decimal greater than `0`.
- Blank means the checker is unevaluated.
- Invalid input shows an inline error and clears or withholds only this result.

### Calculation

Compare available working time with the unrounded pour duration:

`remaining_time = available_working_minutes - pour_duration_minutes`

- Remaining time greater than or equal to `0`: the pour is expected to finish within the limit.
- Remaining time less than `0`: the pour is expected to exceed the limit.
- Equality counts as within the available time with `0` minutes remaining.
- Use partial unload time for a partial final load.
- Do not use the rounded pour-duration display or include travel before the first arrival or work after the final load.

### Output

For a valid result, show:

- “Within available time” and the remaining minutes, or
- “Exceeds available time by” and the overrun minutes

Clearly label the status as an estimate, not a guarantee of concrete performance.

## Responsive and Accessibility Requirements

- Inputs and primary buttons must support keyboard use.
- Timeline segments and Copy must support keyboard focus where practical.
- Use clear widget labels and visible focus states.
- Preserve readable text and timeline labels on narrow windows.
- Permit horizontal scrolling rather than shrinking the clock-time axis until times are unreadable.
- Do not depend on hover alone for exact schedule details.
- The application should remain usable when the map tiles cannot load.

## Validation Examples

### 40 ft × 60 ft Example

Use a typed `40 ft × 60 ft` slab, `6 in` thickness, `5%` waste, `10 cy` truck capacity, `20 min` one-way travel, `30 cy/hr` placement, `10 min` washout, and `7:00 AM` first arrival.

Expected results:

- Area: `2,400 ft²`
- Unwasted volume: `44.44 cy`
- Volume with waste: `46.67 cy`
- Ordered volume: `47.0 cy`
- Truckloads: `5`
- Load sizes: `10, 10, 10, 10, 7 cy`
- Full unload time: `20 min`
- Arrivals: `7:00, 7:20, 7:40, 8:00, 8:20 AM`
- Final partial-load unload time: `14 min`
- Round trip: `70 min`
- Trucks in rotation: `4`
- Pour duration: `1 h 34 min`
- Finish time: `8:34 AM`
- Truck assignments: `1, 2, 3, 4, 1`

For a `$150/cy` price and `$75` short-load fee:

- Concrete cost: `$7,050`
- Estimated total: `$7,125`

Set-time checks:

- `100 min`: within time, `6 min` remaining
- `94 min`: within time, `0 min` remaining
- `90 min`: exceeds time by `4 min`

### Geographic Polygon Example

A drawn polygon with corners `(40.2500, -111.6500)`, `(40.2510, -111.6500)`, `(40.2510, -111.6490)`, and `(40.2500, -111.6490)` must calculate approximately `101,800 ft²`, within `1%`.

### 20 ft × 20 ft Example

Use `20 ft × 20 ft`, `4 in` thickness, `0%` waste, and retain the other defaults.

Expected results:

- Area: `400 ft²`
- Unwasted volume: `4.94 cy`
- Ordered volume: `5.0 cy`
- Truckloads: `1`
- Trucks in rotation: `1`
- Full unload time: `20 min`
- Final partial load unload time: `10 min`
- Pour duration: `10 min`
- Finish time: `7:10 AM`

For a `$150/cy` price and `$75` short-load fee:

- Concrete cost: `$750`
- Estimated total: `$825`

Set-time equality at `10 min` passes. A limit below `10 min` reports an overrun.

### 50-Cubic-Yard Full-Load Example

For a `50 cy` order with `10 cy` truck capacity:

- The final load is full
- No short-load fee applies
- With `$150/cy`, the estimated total is `$7,500`

## Additional Acceptance Behavior

- Volume display uses one decimal place.
- Truckloads and trucks in rotation display as integers.
- A partial final load must use partial unload time for pour duration.
- A typed `40 × 60` slab must override map shape and produce the exact rectangular area.
- Changing an input or dragging a corner updates every dependent output immediately.
- The schedule must show cyclic truck assignments, not only the truck count.
- Invalid or empty values must show validation and must not calculate from invalid values.
- Arrival and finish schedules must wrap correctly past 11:59 PM.
- Completing or canceling a drawing must leave no incomplete, impossible, or self-intersecting slab.
- If clipboard access fails, preserve the visible order text and show an error feedback message.
- Blank cost and set-time inputs must not block otherwise valid core calculations.
- Display rounding must not change pass/fail set-time results at exact thresholds.

## Build Stages

### 1. Basic Window and Mockup

- Create the main Tkinter window, cards, inputs, defaults, summary placeholders, timeline placeholder, order box, and responsive layout.
- Verify desktop window resizing and narrow-window stacking.
- Verify labels, defaults, validation messages, and keyboard focus.

### 2. Map and Slab Drawing

- Integrate the map widget and Esri imagery.
- Add a centered example slab and the required attribution.
- Add typed rectangles, Draw Slab, Cancel Drawing, polygon completion, corner dragging, and redraw behavior.
- Verify typed `40 × 60` and `20 × 20` slabs and geographic polygon area.

### 3. Concrete and Truck Calculations

- Add area, volume, load splitting, unload time, truck rotation, arrival, and finish calculations.
- Verify both validation examples, partial loads, cyclic assignments, and midnight rollover.

### 4. Schedule, Cost, and Set-Time Outputs

- Add the Gantt-style timeline, clipboard order text, cost estimate, and set-time checker.
- Verify exact segment timing, cyclic trucks, Copy success/failure, and each test case.

### 5. Final Testing and Polish

- Verify accessibility, invalid-input handling, immediate updates, responsive layout, map labels, and offline behavior.
- Verify every example and acceptance case.

## Out of Scope

- Reinforcement
- Finishing crews
- Pump trucks
- Weather
- Detailed scheduling beyond truck sequencing
- Printing or PDF export
- Unit conversion
- Geocoding
- User accounts
- Web deployment
- Browser hosting
- Server-side services
- Costs other than the single concrete cost estimator and optional short-load fee
