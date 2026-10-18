# Agent-authored scene contract

The agent creates `scene-spec.json` and real `build_scene.py` after viewing the supplied image. Bootstrap does not invent these. The small [studio builder](../examples/studio/build_scene.py) is a mechanism fixture, not a fallback reconstruction; the [Oak/Linen recipe](../recipes/oak-linen/scene-spec.json) is source-hash guarded.

## Specification fields

| Field | Requirement |
|---|---|
| `schemaVersion` | Integer 1. |
| `title`, `sourceKind` | Actual scene title and photo/render/synthetic-design-reference/floorplan classification. |
| `source` | Workspace-relative pinned image under `public/`; actual PNG/JPEG/WebP extension. |
| `sourceViewLimit`, `portability` | Nonempty honest descriptions of single-view uncertainty and static/runtime/native differences. |
| `authoring.sceneBuilder` | Workspace-relative Python module exporting `build_scene(context)`; trusted executable code, not downloaded page instructions. |
| `authoring.sourceImageSize` | Actual displayed `[width,height]`, honoring source orientation; no fixed showcase aspect. |
| `authoring.room` | Authored native Z-up metre extents `x:[min,max]`, `y:[min,max]`, `height`; builder must implement them and return actual room bounds. |
| `authoring.cameraEstimate` | Source `position`, `target`, `lensMm`, `sensorWidthMm`; position must differ from target. Match through actual renders. |
| `authoring.inspectionViews` | Object of named native Z-up `position,target` poses; `source` is implicit. Choose meaningful lateral/reverse/material/cloth views for this scene. |
| `authoring.probePosition` | Authored indoor Z-up point, chosen away from geometry; production probe is 2:1 equirectangular. |
| `authoring.resourceManifest` | Optional workspace-relative actual acquisition receipt; omit for genuinely procedural scenes. |
| `runtime` | `background:null` or local HDR/EXR URL, `backgroundIntensity`, optional `glassTransmission`, `variants:[]` or named finishes and optional `finishTarget`. |
| `assumptions` | Specific authored geometry/scale/material/lighting limits; do not claim measurements from one image. |

A nonempty variant list uses `{id,label,color:"#rrggbb",roughness?}`. The first entry is the authored base; others are relative linear tints for the declared finish group, not replacement material assets. Base RGB channels must be nonzero for relative recoloring. No sofa, curtains, fixed view names or exactly three variants are required.

## Builder execution

`author_scene.py draft` starts an empty Blender scene, explicitly loads the workspace module, calls `build_scene(context)`, finalizes meshes/modifiers/transforms, verifies one material UV0 layer per physical mesh, saves packed native state and actually renders. Subsequent stages reopen that master; they do not reinterpret the source image.

`context.workspace`, `.assets`, `.evidence` are `Path` objects for this project/current run. `.spec` is the parsed dictionary; `.resolve(relative)` confines data inputs/outputs to the workspace. `.helpers` lazily creates a workspace-private helper namespace; no installed-source paths or import-time scene generation.

A complete builder creates actual physical objects, material graphs, a source camera, world/lights and JSON-serializable summary with at least `roomBounds:{min,max}` in native Z-up, camera/views/components/assumptions. Use the complete linked builders as API examples, not an empty factory or a canned scene. Use a real source camera with horizontal sensor fit; ensure actual world pose and target match the declaration. No zero-vector camera templates.

## Reusable helper surface

| Helper | Purpose / identity |
|---|---|
| `material(name,color,roughness=...,metallic=...,maps=...,color_path=...,normal_strength=...)` | Actual Principled graph; map dictionary `color/normal/roughness` resolves inside W. Albedo sRGB, normal/roughness non-color; explicit UV0 normal mapping. Texture overrides the constant base input; dye the map or author a multiply graph when intended. |
| `mesh(name,vertices,faces,material,component,finish=None,tile=...)` | Actual topology with component/physical IDs and metric material UV0. |
| `box`, `tube`, `lathe`, `cushion` | Editable authoring primitives for shell/supports, pipes/seams, hollow vessels and closed lofted soft forms. Choose semantic component/finish explicitly. |
| `project_uv(obj,metres=...)` | Physical-scale local UV0; do not reuse it as the bake layer. |
| `import_model(path,component,center,height=None,width=None,yaw=...)` | Import real local glTF, preserve world affine placement, normalize UV0 and fit declared dimensions. Visually review before using. |
| `bounds(objects)`, `tag`, `light` | World bounds, semantic identity and native light construction. |
| `curtain(name,origin,rail,depth,width,closed_width,height,material,...)` | Actual 100×32 cloth, hems and hooks in an explicit horizontal orthonormal native Z-up frame; exact 50×16 solver intersections and glTF Y-up metadata. |

Preserve real geometry instead of photo cards, material UV0 instead of bake UV reuse, and identity outside a repair's scope. The packaged case shows BVH-seated piping, skewed cushions, explicit furniture contact, real openings and local garden assets; those are techniques, not mandatory furniture.

## Runtime coordinate and cloth contract

Convert native `(x,y,z)` to glTF/Three `(x,z,-y)`. Exported manifest schema 2 contains actual Y-up camera/room bounds/views, source dimensions, atlas URLs/intensities, probe/background, explicit `lighting.sun` object or null, finish groups and product links.

Cloth meshes must carry `curtain_id`, `curtain_part`, dimensions/tile/fabric width, signed `curtain_rail_axis`, `curtain_depth_axis` and `curtain_plane_origin` in glTF Y-up scene coordinates; hem/hook metadata adds `curtain_v` / `curtain_u`. Rails are horizontal and orthogonal. Closed width exceeds open width; both pinned rail endpoints remain inside room bounds. Deforming geometry must be single-user and preserve exact lattice UV intersections. Nonidentity scene roots are rejected rather than silently mis-simulated; this is not an arbitrary-rig cloth importer.

Review the full actual builder/example before running it. Workspace confinement protects file placement, not execution sandboxing: Python builders and Blender add-ons can execute code. Do not execute asset/page-provided scripts as scene specifications.
