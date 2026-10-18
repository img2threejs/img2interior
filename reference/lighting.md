# Lighting, UV1 and transport boundaries

## Establish coordinate and color truth first

Build an asymmetric colored-light fixture with a rotated UV1 island. Compare decoded EXR sampling against the native renderer before changing atlas row orientation. Record transforms, row convention, linear/non-color channels, view transform and identical camera/crop. The showcase's once-flipped fixture MAE was a coordinate/color check, not an interior likeness score; do not hard-code that result for another decoder.

Run `author_scene.py calibrate --workspace W --run-id calibration-r01 --width 256 --samples 8`, then serve/open its child viewer and compare the actual canvas to the native expected render. See [bake/export](bake-export.md) for the real rotated-UV1/float-EXR/PI field, cardinal probe and child install commands. Native calibration alone leaves browser sampling explicitly unverified.

Keep albedo sRGB, normal/roughness non-color, and radiance/lightmaps linear. Record the chosen tone mapping and exposure. If a portable already contains a display transform, do not apply the same transform again during consumer inspection.

## Separate ambient/fill from direct sun

For the exercised baked track:

1. Keep UV0 surface detail and a separate UV1 atlas layout.
2. Bake full diffuse lighting for the separately labeled static portable appearance.
3. Bake ambient/fill with the direct sun disabled for the runtime; restore native light state in `finally` even on failure.
4. Add runtime shadowed direct sunlight once. Never combine an old full-sun atlas with new runtime sun and call double lighting acceptable.
5. Build the reflection probe from the same native scene/light state as the relevant bake.
6. Keep dynamic cloth out of incompatible static lighting; document that baked indirect illumination does not rebounce as curtains/finishes move.

This is one reproducible transport approximation, not a requirement that every project use baked GI. If another renderer/strategy is used, declare it and independently verify the same lighting/representation obligations.

## Diagnose with receiver/control evidence

At the same camera and exposure, compare open/closed curtains on floor/rug receiver crops and an unaffected control patch. Actual direct shadows should change; the control should not darken because of a global exposure multiplier. Display-encoded RGB averages are not irradiance.

Keep glazing/refraction and any shadow-ray transmission approximation explicit. Do not hide glass, disable physical parts or make the whole room darker to mimic closure. Preserve real window blockers and inspect grounded contact shadows.

## Invalidation and expensive bakes

- Geometry, layout, material reflectance or lighting changes can invalidate transport: revise from the earliest affected stage and regenerate dependent outputs.
- A scoped textile/detail bake leaves other groups' old GI approximation in place; state that limit. Use a full bake for globally updated transport.
- An export-only parameter conversion does not itself change native illumination. Do not cancel an expensive native bake just because an export adapter changed.
- Hash/version the actual native master, atlas set, probe and exports. Never mix captures from different candidates without labeling them.

The shipped pipeline actually bakes full diffuse and SUN-disabled ambient passes, OIDN-filters lighting with normal guides, creates independent static portable maps, and records PI intensity/authoring revision. `bake`, `probe`, `export` are real separate CLI stages. Refresh/draft invalidates required atlases/probe; export checks current probe revision/pose/hash, not existence. See the [runbook](production-runbook.md) for cold and repair sequences.

## Lighting-stage evidence

Include calibration fixture measurements, source/lateral room renders, runtime bake/direct-light model, receiver/control crops, contact review and limitations. Passing hashes or numerical fixture calibration does not grant visual acceptance.
