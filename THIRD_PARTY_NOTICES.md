# Component licenses and prior grants

The primary product license is the [img2 Interior Free Use, Restricted Commercialization License 1.0](LICENSE). This file identifies portions and rights excluded from its restrictions; it is not a choice of alternative licenses for the entire product. These notices include author-owned material retained under an earlier license, not only third-party dependencies.

## Apache-2.0 components

The following repository-relative paths remain under Apache License, Version 2.0, rather than the primary license's commercialization restrictions:

- `authoring/` and all its contents
- `recipes/` and all its contents
- `examples/` and all its contents
- `tools/author_scene.py`
- `tools/inspect_scene.py`
- `tests/test_authoring.py`
- `requirements-authoring.txt`

Their retained copyright notice is **Copyright 2026 hoainho**. The complete license and copyright notice are in [licenses/Apache-2.0.txt](licenses/Apache-2.0.txt). Preserve the license and applicable notices when redistributing these portions. The primary license does not limit the rights granted for these components, including commercial use and redistribution under Apache-2.0.

## Previously licensed material

Earlier revisions, including the 0.2.0 source through commit `2dceef978d2fd696ea4d1f531049389d3b666eed`, were provided under Apache-2.0. Already granted rights remain effective, including rights to earlier material reused in later revisions. Consult the license supplied with the applicable revision; the primary license's restrictions do not retroactively remove those grants.

Apache-2.0's [copyright grant, section 2](https://www.apache.org/licenses/LICENSE-2.0.txt), is perpetual and irrevocable, subject to the license's terms. A private repository, private npm package or changed license label does not withdraw that grant.

## Blender and its Python API

Apache-2.0 is compatible with GPLv3, not GPLv2-only. Blender and its Python API retain their own license requirements. [Blender's published licensing guidance](https://www.blender.org/about/license/#add-ons) requires distributed Python API scripts to be shared under a GPL-compliant license and distinguishes software from artwork.

Neither `LICENSE` nor this file creates a GPL exception or certifies a combined distribution's compliance. Review Blender binaries, Python API integrations and combined distributions before release; obtain qualified legal advice where the boundary is uncertain. Do not apply the primary license's restrictions to rights that must remain available under an applicable component license.

## External dependencies and resources

Third-party code, dependencies, assets and their required notices retain their respective licenses. The img2 harness, Blender/bpy, Three.js, build tools, Python packages and acquired resources are not relicensed by the product license. Preserve required licenses and notices in any distribution that includes them. A dependency's permissive license and a resource provider's API terms are separate questions.

## User inputs and artwork

The plugin does not claim ownership of a user's reference images, original scene data, renders or artwork merely because the plugin creates or processes them. Copied plugin code and third-party material retain their applicable terms. Public showcase previews grant no rights to unpublished plugin implementation or scene assets.
