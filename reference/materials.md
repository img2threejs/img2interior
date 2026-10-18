# Material identity, not generic gloss

## Inspect what is actually bound

For each critical material, inspect the exported GLB and runtime binding, not just an asset manifest or a Principled default. Record albedo, normal, metallic/roughness, effective texture coordinates/transform, physical tile scale, color spaces, normal strength, sheen/specular factors and affected mesh IDs.

Use `audit_materials.py` with an explicit policy; [tool inputs](tool-inputs.md) defines its schema. The bundled Oak / Linen policy targets two exact current curtain material names and their actual bound maps. It is not a universal textile preset.

```sh
python3 "$SKILL_DIR/tools/audit_materials.py" --workspace "$PWD" --glb ./public/assets/interior/room-runtime.glb --policy ./material-policy.json
```

This audits wiring, resource/UV presence and declared scalar bounds. It does not decode texture pixels, infer color space correctness, measure effective roughness or certify fabric. A roughness image can override the scalar: a scalar of 1 does not prove the surface is matte. Inspect decoded texture statistics separately when needed and record their interpretation.

Acquire/verify actual resources and run `prepare_surfaces.py --workspace W --recipe surfaces.json` in the image environment; [resources](resources.md) defines the real dye/roughness/crop/metric-normal operations and receipts. Author intended map/UV/scalar requirements before auditing, not by copying whatever the exported material happens to contain. Provisional bake/probe/export may be needed for the first bound-GLB review; final lighting acceptance still requires its later production round.

After changing a used map, run `author_scene.py refresh-material --workspace W --run-id material-r02 --image public/assets/interior/MAP.png`, then regenerate required bakes/probe/export and reopen the packed master without that external input. Pixel refresh does not implement a material-graph edit. `material-regression` provides the actual packed-image/UV0/non-white-sheen success-and-failure fixture; [bake/export](bake-export.md) explains its limits.

## Physical-scale visual review

1. Capture an overview and fixed frontal/grazing macro views under unchanged lights/exposure.
2. Record camera/projection, canvas crop and physical texel footprint. Compare matched native-pixel captures where possible; label unmatched crops honestly.
3. Review linen yarn, upholstery seams, leather grain, wood grain, marble and plaster as distinct materials, not one noisy normal map.
4. Exercise deforming cloth while held and after release. Preserve UV0/material coordinates and unrelated sofa geometry/textures/variants.
5. Review native/runtime/portable material behavior separately; a low-density baked portable may blur where runtime PBR retains yarn detail.

## Showcase-derived failure modes

- A resource dictionary contained an albedo, but the material factory did not attach it. Inspect exported `baseColorTexture`.
- A connected roughness map had a low tail despite a matte scalar. Changing only the scalar was not the causal fix.
- Reusing packed Blender images after replacing a PNG preserved stale pixels. Refresh only the owned packed image, reload it, then reopen without the external source to verify packing.
- Blender 4.3's exercised sheen exporter treated nonzero weight as an enable gate and exported unweighted tint. For constant weight, scope the conversion to export and restore native inputs in `finally`; test non-white tint. Do not generalize an exporter workaround to untested versions.
- Curtain and sofa samplers must remain independent; a cloth filtering repair must not change unrelated finishes.

The case used a 0.65 m authored UV0 tile, normal strength 0.70, low broad sheen and dedicated high-roughness linen derivatives. These are observed design settings, not a measured BRDF or a default for every room.

## Material-stage evidence

Cite the machine audit, actual bound-map/factor report, UV/identity checks, frontal/grazing renders and reviewer explanation. Keep technical pass separate from visual acceptance. A change to finish/reflectance can require rebaking affected lighting atlases and refreshing the probe/export; see [lighting](lighting.md).
