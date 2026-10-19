# img2 Interior

**One room image. An editable scene. A viewer you can explore.**

An agent-operated interior reconstruction skill for **Claude Code, Codex and OpenCode**, powered by the [img2 harness](https://github.com/img2threejs/img2). Your agent reads the reference, authors a Blender scene, compares renders, and builds a Three.js viewer with native and portable exports.

Not a pretrained image-to-mesh model or a one-click fidelity guarantee. The workflow depends on scene-specific authoring and visual review.

[Showcase](#showcase) · [Copy-and-use prompt](#copy-and-use-prompt) · [What you get](#what-you-get) · [Installation](#installation) · [Guides](#guides)

> **Availability:** source version 0.3.0; **not yet published to npm**. Private npm payload distribution is planned for authorized users. The implementation stays private; only the approved showcase previews are public.

## Showcase

### Oak / Linen — Living Room

[![Side-by-side living-room comparison: an AI-generated reference on the left and the actual authored Blender render on the right.](https://raw.githubusercontent.com/img2threejs/img2interior-media/375e6af7ab526d7c0c10be91b0e72f2757391ec7/living-room-comparison.webp)](https://raw.githubusercontent.com/img2threejs/img2interior-media/375e6af7ab526d7c0c10be91b0e72f2757391ec7/living-room-comparison.webp)

**Left: design reference. Right: reconstruction.** The reference is AI-generated, not a photograph or measured survey. The result is an actual render of the reopened Blender deliverable, not a retouched reference or an image plane standing in for a room. Open the image for the larger comparison.

This is the **original Oak / Linen living-room research study** from which the packaged recipe and workflow lessons were extracted. It used scene-specific Blender/Python authoring and viewer integration, not a fresh run of the packaged 0.3.0 skill or the prompt below. Framing, proportions, fabric folds and lighting still differ from the reference; this is not a universal fidelity benchmark.

<details>
<summary><strong>See the browser viewer</strong> — camera views, wireframe, curtain controls, sofa finishes and downloads</summary>

[![Actual browser screenshot of the living-room reconstruction, with source comparison, camera views, wireframe, curtain controls, sofa finishes and native/portable download links.](https://raw.githubusercontent.com/img2threejs/img2interior-media/375e6af7ab526d7c0c10be91b0e72f2757391ec7/living-room-viewer.webp)](https://raw.githubusercontent.com/img2threejs/img2interior-media/375e6af7ab526d7c0c10be91b0e72f2757391ec7/living-room-viewer.webp)

A **static screenshot of the working Three.js project**, not a hosted live demo. Its controls are not interactive inside this README. Indirect lighting is baked; curtain movement does not produce fully dynamic global illumination. The portable GLB is a separate static product, not a copy of every browser behavior.

</details>

[Public preview gallery](https://github.com/img2threejs/img2interior-media) · [Bundled gallery and limitations](docs/showcase/README.md)

## Copy-and-use prompt

1. **Install and activate the skill** using the [installation instructions](#installation). Your agent must be able to read images, execute local commands and inspect a real browser.
2. **Open your project**, outside the plugin checkout. Attach **one interior reference image** you have permission to use.
3. **Copy the entire prompt below.** No room-specific placeholders, JSON specification or Python builder to prepare yourself; the agent authors those inputs.

```text
Use the installed img2-interior skill to reconstruct the attached room
reference as an editable 3D interior and a working Three.js viewer in
this project. Complete the workflow, not just a plan or a Blender file.

Read the installed SKILL.md and its required reference guides first.
Confirm that you can see the image and access the required agent tools,
img2 harness, native authoring environment, image tools and WebGL browser.
Set up missing dependencies only in project-local environments. If a
required image, permission or compatible runtime is unavailable, report
the exact blocker instead of inventing progress or substituting a room.

Inspect the actual pixels. Identify the composition, camera, room shell,
furniture, materials and lighting. Preserve the source and its provenance.
Document estimated metre scale, dimensions, hidden surfaces and other
single-view assumptions. Make reasonable labeled estimates; ask only
when a material requirement cannot be decided safely.

Author scene-specific, editable geometry and physically based materials.
Do not reuse a bundled room as the answer, put the reference on furniture
cards, or ask me to write the scene specification or builder. Use suitable
permitted resources, keep their provenance, and preserve unrelated files.

Render, open the images, compare against the reference and repair causes
in camera/composition, geometry, then materials/lighting order. Inspect
lateral and reverse views as well as the source view. Repeat the relevant
reviews and regenerate affected bakes/exports after changes. A passing
build, audit or score does not establish visual fidelity.

Deliver all three products: a packed editable Blender master; a runtime
GLB with every required sidecar and the working Three.js viewer; and a
separate static portable GLB. Follow all eight review stages and the
three blocking gates on current evidence without relaxing their checks.

Launch and inspect the actual viewer. Exercise navigation, source view,
wireframe, reset, applicable material/curtain controls, errors/retry and
downloads at desktop and narrow widths. Reopen the native and portable
files in independent consumer sessions and inspect actual renders.

Hand off artifact locations, setup/launch/reproduction commands, observed
verification evidence, resource notices and remaining visual/technical
limits. Distinguish estimates, emulation and untested claims from proof.
Do not claim exact recovery, universal photorealism or mobile performance.

Do not use paid services, upload private images, publish packages, deploy
publicly or change global configuration without separate authorization.
```

**Keep the same workspace when continuing.** For a revision, describe the visible difference to fix; the skill should resume its recorded workflow, preserve evidence and revisit affected stages rather than initialize a new project. The prompt standardizes execution, not the artistic quality of every result.

## What you get

| Product | Use it for | What travels with it |
| --- | --- | --- |
| **Packed Blender master** (`.blend`) | Edit geometry, cameras, materials and lighting | Native scene with packed images; editable rather than flattened into a reference picture |
| **Runtime scene + Three.js viewer** | Explore the authored room in a browser | Runtime GLB, declared lightmaps/probe/other sidecars, viewer code and applicable controls |
| **Portable GLB** | Open a standalone model in another glTF consumer | Embedded static baked appearance; no browser cloth state or full native PBR relighting |

The handoff also includes the scene specification and Python builder, source/assumptions, resource notices, evidence, commands and known limitations. Generated rooms and full-resolution assets live in **your project**, not in the plugin package. The two small documentation previews above are not downloadable scene assets.

## Installation

### Before you start

| Component | Requirement |
| --- | --- |
| Agent | Image-capable Claude Code, Codex or OpenCode, configured through img2; command execution and browser/image inspection tools |
| Harness | img2 ≥0.4.0, core API 1 |
| CLI / viewer | Git, npm and Node.js 18, 20 or ≥22; prefer a supported LTS release |
| Audit / workspace tools | Python ≥3.10 |
| Native authoring | Separate Python 3.11 environment with `bpy==4.3.0` and `numpy==1.26.4` |
| Image tools / preview | Separate environment from `requirements-surfaces.txt`; a WebGL-capable browser |

The harness registers the skill; it does not install bpy or create the finished app. The agent follows the bundled [environment setup](reference/production-runbook.md#2-prepare-project-local-environments) and preflight before authoring. Compatible Blender wheels must exist for your platform. Obtain written authorization for the proprietary portions before installing or using them.

### Available now: private source or supplied source archive

For the Git method, you need read access to `img2threejs/img2interior` and authenticated Git credentials. These commands register the skill with local agent hosts, so they change local harness/host configuration. Keep the checkout in a persistent location. If you already have a compatible harness, skip its `install` command; if you already have the checkout, do not clone over it.

```sh
git clone https://github.com/img2threejs/img2interior.git "$HOME/img2interior"
npx --yes @img2threejs/img2@0.4.0 install --yes
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor --json
npx --yes @img2threejs/img2@0.4.0 sync --check
```

Restart the agent session, open your project and use the prompt above. The registry ID is **`interior`**; the agent-facing skill is **`img2-interior`**. An authorized source archive uses the same `add --link` flow after extraction. See [installation and removal](reference/installation.md) for archive paths, updates and cleanup.

### Planned: private npm payload

The intended npm package will contain the **skill implementation and bundled guides**, not a public installer that still fetches private GitHub source. Authorized consumers will need npm authentication and package read access, rather than GitHub source access. Package readers can inspect downloaded code; private distribution is access control, not code encryption.

**No npm package name/version or install command is advertised yet.** The package, access policy and consumer installation must be verified before those instructions go live. Installing an arbitrary npm package also does not register a skill automatically; registration uses the official img2 harness. Maintainers: follow the [private npm release checklist](reference/installation.md#private-npm-release-checklist).

## Guides

Detailed guides are **bundled with the installed skill**; ask the agent to read them there. Their GitHub links require separate repository access. The public previews do not require that access.

| Guide | Start here when… |
| --- | --- |
| [Installation and release](reference/installation.md) | Installing, updating, removing, or preparing the private npm payload |
| [Production runbook](reference/production-runbook.md) · [Agent entry point](SKILL.md) | Running or resuming the complete reconstruction |
| [Scene contract](reference/scene-contract.md) | Understanding editable scene inputs and the Blender builder |
| [Resources](reference/resources.md) · [Materials](reference/materials.md) | Selecting assets, recording rights, and preparing PBR surfaces |
| [Bake / export](reference/bake-export.md) · [Viewer](reference/viewer-integration.md) | Understanding the native/runtime/portable split |
| [Delivery](reference/delivery.md) · [Verification record](VERIFICATION.md) | Checking consumer evidence and the scope of previous verification |
| [Changelog](CHANGELOG.md) · [Maintainer checks](reference/installation.md#maintainer-checks) | Reviewing changes or validating a contribution |

## Limits to understand

- **One image is incomplete evidence.** Dimensions, hidden geometry, camera and material properties are estimates unless additional evidence is supplied.
- **Visual review is required.** Contract gates catch stale or inconsistent deliverables; they cannot prove likeness, physical accuracy or photorealism. The showcase is not a universal benchmark.
- **Lighting and exports differ.** Indirect bakes/probes are static. The portable product does not preserve every native material or browser interaction.
- **Interaction is scoped.** Optional rail-mounted curtains use a position-based approximation, not a general cloth solver.
- **Performance is scene-dependent.** Desktop or narrow-viewport captures do not certify physical phones, arbitrary hardware or production network performance.

## Support and contributions

Repository members can use [issues](https://github.com/img2threejs/img2interior/issues) for reproducible bugs. Include plugin/harness versions, OS, the command, expected/actual behavior and a minimal reproduction. Remove credentials, private references, client assets and identifying paths. Package access alone does not grant access to private GitHub issues; npm-only consumers should ask their package administrator to forward reports to the maintainer.

Report security-sensitive information privately to the repository owner; read the bundled [security policy](SECURITY.md) before executing authored Python or consuming external resources. Paid generation, uploads, public deployment and redistribution need their own authorization.

Contributions to proprietary portions require prior written authorization and agreed terms. Keep generated projects, dependencies and private evidence out of commits; the approved documentation previews are the explicit exception. Describe the behavior changed and checks exercised. Separately licensed components retain their own terms; see [component notices](THIRD_PARTY_NOTICES.md) and [maintainer checks](reference/installation.md#maintainer-checks).

## License

**Proprietary — All rights reserved.** The [primary license](LICENSE) grants no automatic permission to use, modify or redistribute the proprietary portions. Obtain written authorization from the copyright holder; GitHub/npm access or payment alone is not a usage license.

[Component notices and prior grants](THIRD_PARTY_NOTICES.md) preserve separately licensed material, including existing Apache-2.0 rights. They do not make the whole product open source, and the proprietary license does not override them. Third-party content and your artwork retain their respective rights.
