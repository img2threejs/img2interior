# Exercise the viewer, not just the solver

## Declare scope

Keep a real orbit/pan/zoom viewer with bounded room camera, reset, loading/error/retry and accessible controls. Add cloth, finish variants and downloads only when implemented and requested. `interactionRequired:false` permits a static scene, not skipping camera, keyboard, loading, accessibility and visibility checks; explain omitted cloth controls in evidence.

Install/build/serve the actual [Three.js template](viewer-integration.md), which derives source aspect, arbitrary view/variant sets and room safety from schema-2 manifest rather than Oak/Linen. Cloth requires explicit horizontal Y-up rail/depth/origin, hem point coordinates, enough render vertices for exact 50×16 solver intersections, identity scene root and single-owner deforming geometry. The native helper emits this metadata. Missing/unsupported rigs fail actionably; arbitrary rotated roots or other solvers are not silently accepted.

## Cloth acceptance when present

1. Grab the actual cloth material point at multiple low/middle/high UV locations on every declared panel, plus hem points. Compute the rendered-lattice correspondence; a hem's UVs are not the cloth binding.
2. Keep material UV0 unchanged. Measure held UV/point error and pin rail/header attachments; record units, sampling, viewport and tolerances chosen for the actual consumer.
3. Move nearby points with spatial/temporal falloff. Exercise reverse drag, release and physical settling. Do not claim calibrated FEM or full self/furniture collision from a position-based approximation.
4. Give the grip exclusive pointer ownership; disable orbit only while held. Camera position, quaternion, target and projection must remain unchanged, not just a screenshot that looks stationary.
5. Own wheel input only during the grip, release it afterwards and restore any wrapped control method on disposal.
6. Cancel safely on pointer capture loss, outside release, touch cancel, an added finger, blur, source-mode switch and tab leave. Never leave controls stuck.
7. Exercise slider/open/close/keyboard alternatives, optional wind and reduced motion. Touch emulation is not real-phone proof.

The real diagnostic snapshot `window.interiorStudy.curtains` supplies panel IDs, low/middle/high/header/hem-level UV/world/canvas probes and held point/target/error. Use actual visible ray hits (folds may occlude a nominal UV), paced input and observed rendered frames; record transient versus settled error and camera/projection invariants. A fixed wall-clock delay under a simultaneous bake is not a solver-convergence measurement. The hem ray must actually report `part:"hem"`; do not relabel a nearby cloth hit.

## Lifecycle and camera

- Constrain eye/target after every controls update, including below-event-epsilon updates. Stress keyboard, orbit, pan and zoom at bounds.
- Pause hidden/offscreen rendering and cancel held gestures. Do not weaken visibility safety because a test window was occluded.
- Wait for wind-off physics to settle before asserting on-demand sleep; observe frame counters over an interval.
- Trigger actual WebGL context loss and recovery; verify assets, interactions and wind can resume. An error overlay alone is not recovery.
- Exercise real load failure/retry and source/3D switching. Observe page errors and actual network requests.
- Change finishes rapidly and verify only declared component materials change, preserving geometry/UV/texture/lightmap identities.

## Accessible/responsive surface

Inspect actual desktop and narrow canvas bounds, overflow, focus, readable labels and keyboard controls. Test touch targets and reduced motion. Record locale, dynamic text/ARIA and error metadata; the case's English-only requirement is not mandatory for every project. Distinguish real devices, emulation and untested combinations.

## Interaction-stage evidence

Include runtime URL/build identifier, input sequences, numerical receipts, screenshots and named limitations. Record observed performance/payload separately from desired budget. Do not substitute a bare non-crash result for held-point correctness, lifecycle transitions or actual UI inspection.
