# Changelog

## 0.3.1 — 2026-10-19

### Distribution

- **Install documentation correction.** The img2 0.4.0 harness `add npm:@img2threejs/img2interior@<version> --yes` flow is broken against npm 10/11 — it expects a nested `info.dist.integrity` from `npm view`, but npm 10/11 return a flat `dist.integrity`, so the harness `add` command refuses the package. The bug is in the img2 harness, not in this package. The documented supported install path is now a two-step flow: `npm install --prefix "$HOME/.local/share/img2interior" @img2threejs/img2interior@0.3.1` (the real distribution and tracking event) followed by `npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/.local/share/img2interior/node_modules/@img2threejs/img2interior" --yes` (the host registration step). The package ships no lifecycle scripts, so `npm install` performs only a fetch and a directory copy. README and `reference/installation.md` describe the two-step path; the `add npm:` flow is recorded as broken and **must not** be advertised as working. Update by re-running the `npm install --prefix` command against the new version — the host link points at the installed prefix, so the consumer's next launch sees the new bytes. Do not pass `--force`, do not run a global install, and do not delete the prefix while a host link still points inside it. Source clone and supplied archive paths remain supported via `add --link` only. Bump SKILL metadata to `0.3.1`; root `package.json` and `plugin.json` version bumps belong to the maintainer.

## 0.3.0 — 2026-10-19

### Licensing

- Replace the no-permission proprietary notice with the **img2 Interior Free Use, Restricted Commercialization License 1.0**: allow free use/modification, commercial project work, paid client output delivery, viewer/runtime code accompanying outputs, and free noncommercial sharing with notices. Require prior written permission to sell/repackage the tool or provide paid hosted/API access to its authoring/generation workflow. Label it source-available, not OSI-approved open source; align README, skill metadata and installation guidance.
- Move the exact separately licensed component scope and earlier-grant notices into `THIRD_PARTY_NOTICES.md`; retain `licenses/Apache-2.0.txt` unchanged. Require all three files in source archives and the npm package. This reorganization neither revokes existing Apache-2.0 rights nor certifies exclusive ownership or Blender GPL compliance for the entire distribution.

### Distribution

- Replace private-distribution plans: published as **`@img2threejs/img2interior@0.3.0`** with `npm publish --access public`. The public npm package and the public `img2threejs/img2interior` GitHub repository ship the same project; no authenticated npm login or `--allow-any-source` flag is required for consumers (the package lives in the default-trusted `@img2threejs` scope). README, `reference/installation.md` and `docs/showcase/README.md` describe the public install flow, public source access, the actual hosted [live demo](https://img2threejs.io/living-room/), the four support links (Ko-fi, donate page, PayPal, Binance Pay), and the public npm download / package metadata endpoints plus their limits. Maintainer checklist now uses `npm publish --access public`, an explicit public tarball review and a public-consumer registration check (`add npm:@img2threejs/img2interior@<version> --yes`) instead of an authenticated-read check.
- Add a discoverable showcase/support reference in `SKILL.md` so the live demo, the bundled gallery, and the support links are reachable from the agent skill itself without changing behavior.

### Documentation

- Redesign the README as a package landing page with a complete, room-independent copy-and-use prompt, explicit setup/delivery expectations, and actual Oak / Linen living-room reference/native/browser previews. Link the actual hosted [live demo](https://img2threejs.io/living-room/) prominently in the top navigation, the showcase heading and the gallery footer; keep the static screenshots but label them as captured frames from the live page rather than as the only available view. Distinguish the native Blender comparison image from the archived viewer capture.
- Include the small offline showcase gallery and both optimized previews in source archives. Use immutable public-media image URLs for the npm-facing README without exposing plugin code, scene files, or full-resolution references.

No scene behavior, reconstruction-quality result, or visual-quality upgrade is introduced by this revision; only the license text, public-distribution plumbing, and the documentation supporting both change.

## 0.2.0 — 2026-10-18

### Full agent-operated production

- Expand the single-assignment skill and ordered actor/program steps through actual image/reference analysis, composition, live resource selection, native geometry/PBR, observed repair, bake/export, Three.js interaction and three-product delivery. The agent authors project inputs/code; no user-supplied JSON or stock-room fallback.
- Add workspace-only source intake/preflight, owned template/recipe installation, immutable evidence snapshots and manifest-derived delivery inventories.
- Add live Poly Haven discovery/info/files/acquisition with local glTF dependencies, bounded HTTPS/redirect/path handling, publisher MD5/size and SHA receipts, plus real dye/roughness/crop/metric-normal preparation.
- Package reusable bpy geometry/material/UV helpers, render/refresh stages, full-static and SUN-free two-pass diffuse/OIDN bakes, revision-bound indoor probe, actual runtime/portable exports and packed-master/portable consumer inspection.
- Preserve policy-addressable material identities and UV0 mappings across rebakes; a real native failing-before/passing-after regression covers repeated export and retained artist roughness. Update the production case policy to its stable names.
- Add real asymmetric UV1/native/EXR/probe/browser calibration fixtures, packed-pixel/non-white-sheen/export-failure regression and local Khronos validation; retain actual warnings rather than suppressing them.
- Package the pinned manifest-driven Three.js/Vite viewer: arbitrary source aspect/views/finishes, optional sun/background/cloth, UV1 linear atlases/PI, specular probe, bounded navigation, point-bound rail cloth, accessible controls, loading/retry/lifecycle and product links.
- Keep complete Oak/Linen authoring/spec/resource/surface reproduction behind the exact source hash; provide a separate complete asymmetric studio mechanism fixture. Neither reconstructs a different image automatically.

### Integration and distribution

- Preserve all eight evidence-pinned reviews, append-only revision/invalidation and three blocking gates; distinguish agent attestations from mechanical checks.
- Normalize production workspace roots before macOS alias confinement/relative paths; retain genuine traversal, escaping symlink, stale source and ownership protections.
- Separate installed-library import paths from explicit workspace output roots using the official SDK-compatible entrypoint convention.
- Include authoring/resources/viewer/recipes and optional dependency declarations in deterministic source ZIPs; exclude dependency/environment/build/private output trees. Extend CI definition with real image dependencies and viewer behavioral/build commands.
- Document executable per-step inputs/actions/exits, causal repair, resource/license authority, native/runtime/portable limitations and evidence-backed release verification. No universal neural recovery, fresh full-quality realism, physical-phone certification or npm/catalog publication is implied.

## 0.1.0 — 2026-10-18

### Interior workflow

- Ship a standalone img2 plugin with registry ID `interior`, host skill `img2-interior`, typed `image → interior-scene-candidate` capability, explicit program/agent steps and three blocking gates.
- Add eight evidence-pinned authoring/review stages with immutable source/intake, named reviewer attestations, rejection/request-input/stop handling, append-only history and dependent-stage invalidation.
- Add stdlib GLB binding/resource/UV/scalar-policy audits and distinct source/runtime/portable/native/sidecar hash contracts. Gates reevaluate current inputs without rewriting receipts.
- Distill Oak / Linen repairs into routed guidance for camera/form, textile/PBR/export pitfalls, UV0/UV1 and EXR calibration, ambient/direct lighting, cloth/camera ownership, lifecycle/accessibility and consumer delivery.

### Installation and distribution

- Use official img2 install/add/link/state/gate APIs; no custom installer, Forge imports or cross-plugin Python imports.
- Add isolated three-host installation/removal verification, pinned compatibility CI, deterministic installable source-ZIP packaging and a professional README/input/reference set.
- Exclude generated bootstrap files, workspace state, caches, credentials and large showcase assets from release archives.

### Integration repairs and observed verification

- Fix valid intake evidence rejection through workspace path aliases (including macOS `/var` versus `/private/var`) by comparing resolved identity/content while retaining lexical pins for symlink-retarget detection.
- Add a failing-before/passing-after directory-alias regression; keep source/evidence freshness and confinement checks intact.
- Correct capability examples/probes to specify both typed-edge endpoints, not a named plugin with an unspecified `null → null` query.
- Verify 47 behavior regressions, official installation in Claude/Codex/OpenCode sandboxes with zero doctor findings, and real showcase audit/state/gate replay including rejection/revision and stale-input counterexamples.

0.1.0 was verified as a local source release. Repository hosting is separate from npm/catalog publication; no room-generation or physical-phone certification is implied.
