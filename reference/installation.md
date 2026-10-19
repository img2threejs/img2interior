# Install and maintain

## Requirements

- img2 harness/CLI >=0.4.0, core API 1, Node.js 18, 20 or >=22, npm, Git and Python >=3.10. Prefer a supported Node LTS release.
- A configured, image-capable Claude Code, Codex or OpenCode host with command execution and browser/image inspection. Hermes is not supported by this harness.
- Production native tools: isolated Python 3.11/bpy 4.3.0/NumPy 1.26.4 (`requirements-authoring.txt`); separate NumPy/Pillow image environment (`requirements-surfaces.txt`). Audit/state tools remain stdlib plus core API 1.
- Workspace-local pinned npm dependencies and a real WebGL browser for the viewer/validator. See [production setup and commands](production-runbook.md); a harness install does not silently install bpy, image packages or a web app. Compatible Blender wheels must exist for your platform.
- Version 0.3.0 uses the [img2 Interior Free Use, Restricted Commercialization License 1.0](../LICENSE): use and modification are free, including commercial project work and output delivery; selling/bundling the tool or offering paid hosted/API access to its workflow requires prior written permission. The output exception permits viewer/runtime code with deliverables. [Component notices](../THIRD_PARTY_NOTICES.md) preserve separately licensed portions and earlier grants.

## Public npm install (preferred)

Install `@img2threejs/img2interior@0.3.1` from the public npm registry into a dedicated, persistent prefix, then register it with the official img2 harness via `add --link`. `npm install` is the real distribution and tracking event; `add --link` is the host registration step. The package has no lifecycle scripts, so `npm install` performs only a fetch and a directory copy. Neither step requires Git credentials or an authenticated npm session — the package is in the default-public `@img2threejs` scope.

```sh
npm install --prefix "$HOME/.local/share/img2interior" @img2threejs/img2interior@0.3.1
npx --yes @img2threejs/img2@0.4.0 install --yes
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/.local/share/img2interior/node_modules/@img2threejs/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor --json
npx --yes @img2threejs/img2@0.4.0 sync --check
npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
```

Skip the `install --yes` step if a compatible harness already exists on this host; the `add --link` flow alone is sufficient then. Keep the dedicated prefix in place at `$HOME/.local/share/img2interior` — future `npm install --prefix "$HOME/.local/share/img2interior" @img2threejs/img2interior@<version>` commands update the live link without moving it. Do not pass `--force`, do not run a global install, and do not delete the prefix while a host link still points inside it.

The first `npx --yes` belongs to npx; the second `--yes` on `add` skips the harness consent prompt. The plugin manifests as `interior`; the harness-derived skill name is `img2-interior`. Optional `--plugin interior` enforces the manifest `name` matches before the registration is written. Restart the agent session after adding, open the authored project, attach an image and use the [standard prompt](../README.md#copy-and-use-prompt).

> **Why this two-step path?** The img2 0.4.0 harness `add npm:@img2threejs/img2interior@<version> --yes` flow expects `npm view` to return a nested `info.dist.integrity`, but npm 10/11 return a flat `dist.integrity`; `add` therefore refuses the package rather than registering it. Real consumers use `npm install` to fetch the public package into a dedicated prefix, then `add --link` that installed copy. The `add npm:` transport bug lives in the img2 harness, not in this package; until the harness ships a fix, the documented supported install path is the two-step flow above. Do not claim `add npm:` works.

## Install from public source or supplied archive

The public GitHub repository `img2threejs/img2interior` is the same project that ships as the public npm package. Use this path when you want an exact commit, when working without npm connectivity, or when the npm registry is unreachable. No private access or authenticated Git credentials are required for the public repository.

```sh
git clone https://github.com/img2threejs/img2interior.git "$HOME/img2interior"
npx --yes @img2threejs/img2@0.4.0 install --yes
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor --json
npx --yes @img2threejs/img2@0.4.0 sync --check
npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
```

Skip the `install --yes` step if a compatible harness already exists on this host; the `add --link` flow alone is sufficient then. Do not clone over an existing checkout. Restart the agent session after adding, open the authored project, attach an image and use the [standard prompt](../README.md#copy-and-use-prompt).

A supplied source archive installs through the same official CLI: extract it into a persistent directory and pass that extracted `img2interior` directory to `add --link`. Use its actual absolute path, not the ZIP path. The link points through `$IMG2_HOME/plugins/interior/` to this persistent checkout; do not move/delete a linked source. `_img2_local.py` in root/tools is generated and ignored, not committed or distributed. `add --link` is a local-only registration; the public GitHub source is unchanged.

## Inspect and remove

```sh
npx --yes @img2threejs/img2@0.4.0 list
npx --yes @img2threejs/img2@0.4.0 update interior --check
npx --yes @img2threejs/img2@0.4.0 remove interior --yes
```

Local links are live; `update` does not fetch them. Removal unregisters owned links, not the original checkout. Never use `--force` to hide another registration or overwrite an unrelated host path. Review the harness's refusal instead.

## Download metrics

Read public npm registry data through the documented endpoints; do not embed a tracker in the package or the source archive. Per the [npm download-counts spec](https://github.com/npm/registry/blob/main/docs/download-counts.md):

- **Package metadata** (version, description, license, repository): `https://registry.npmjs.org/@img2threejs/img2interior` — no auth required for a public scoped package.
- **Point-in-time total** for a single period (returns one integer count): `https://api.npmjs.org/downloads/point/{period}/@img2threejs/img2interior`, where `{period}` is `last-day`, `last-week` or `last-month`.
- **Date range with one bucket per day**: `https://api.npmjs.org/downloads/range/last-month/@img2threejs/img2interior` — yields per-day totals for the last 30 days.
- **Custom date range with one bucket per day**: `https://api.npmjs.org/downloads/range/YYYY-MM-DD:YYYY-MM-DD/@img2threejs/img2interior` for any period you choose.

**Limits to disclose, not work around.** Download counts include CI reinstalls, mirror fetches and any consumer that ran the install command, so they are not a "unique users" figure; cached registry mirrors and offline package managers may report 0. The public API updates roughly daily with a delay; the badge in the README therefore lags real consumption. No telemetry, beacon or remote call is added by this skill — there is nothing to disable and the registry's API is the only source these counts come from.

## Project boundary

Keep the current directory in the authored project. Resolve `SKILL_DIR` from the linked skill, then call its tools by absolute path. Do not initialize a room inside the plugin. Project state is in `.img2/state.json`, under `plugins.interior`; receipts are under `.img2/artifacts/interior/`.

`interior_project.py start` pins a supplied image; the agent authors intake/spec/builder and executes the full loop. `install-viewer` and the explicit hash-guarded `use-recipe` copy owned templates into the workspace with preflight collision checks. A new image is never routed to the old room. Keep dependency/build installs local; the installed plugin is not the generated app. On resume use the recorded workflow's `next` operation rather than initialize again.

## Public npm release checklist

**Distribution model:** public source repository plus a **public scoped npm package** that ships the same project. No GitHub authentication is required to read or install either artifact. The maintainer publishes the package with `npm publish --access public`; once that version is live and consumer-tested, the install command in the README is the supported path.

1. **Confirm the real name, registry and access policy.** Select an owned scoped package name and exact version (`@img2threejs/img2interior`, current release `0.3.1`). Keep plugin ID `interior` and skill name `img2-interior`; align package and plugin versions.
2. **Package the implementation, not a Git-fetch wrapper.** Use a reviewed root `package.json` and explicit file allowlist. Include `plugin.json`, `SKILL.md`, steps/gates, tools, authoring helpers, resource library, viewer/templates, required recipes/examples, references, dependency manifests, README, `docs/showcase/`, `LICENSE`, `THIRD_PARTY_NOTICES.md` and `licenses/Apache-2.0.txt`. Include needed scripts/fixtures without generated state. Exclude credentials, generated `_img2_local.py`, environments, `node_modules`, builds, private production reports, full-resolution references and generated scenes.
3. **Use public access and correct license metadata.** Scoped packages default to restricted access; set `publishConfig.access: "public"` and publish with `--access public`. Do not set `"private": true`, which prevents publication entirely. Use npm's custom-license convention `license: "SEE LICENSE IN LICENSE"`; preserve `THIRD_PARTY_NOTICES.md` and `licenses/Apache-2.0.txt` rather than the deprecated `licenses` metadata array. Review Blender/Python API and combined-distribution obligations before release; the primary license is not a GPL exception.
4. **Review the actual tarball.** Run `npm pack --dry-run`, build the tarball, inspect its complete file list and install that exact artifact in an isolated consumer. The source ZIP packager is a separate format, not proof of an npm package. Reopen the bundled guides/gallery without GitHub access; verify license files, image paths and required runtime dependencies. Confirm the tarball ships no `preinstall`/`install`/`postinstall` scripts; lifecycle scripts are not used and would expand the install attack surface.
5. **Authorize and perform the first publication separately.** Use explicit `--access public`, reviewed bytes, the publishing account's required authentication/2FA. Do not publish merely to preview the README. For CI, review current [trusted-publishing support](https://docs.npmjs.com/trusted-publishers/) for the selected registry/account and workflow; never commit credentials or assume an OIDC flow has been configured. Provenance attestation of npm releases from a public repository is enabled by `npm publish --provenance` after an OIDC publisher is configured; leave it off rather than claim an attestation that has not been issued.
6. **Test the actual consumer install path.** The img2 0.4.0 harness `add npm:@img2threejs/img2interior@<exact-version> --yes` flow is **broken against npm 10/11** — it expects a nested `info.dist.integrity` from `npm view`, but npm 10/11 return a flat `dist.integrity`, so `add` refuses the package. The img2 harness bug is not in this package. Until the harness ships a fix, verify consumer install via the two-step flow:

    ```sh
    npm install --prefix "$HOME/.local/share/img2interior" @img2threejs/img2interior@<exact-version>
    npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/.local/share/img2interior/node_modules/@img2threejs/img2interior" --yes
    npx --yes @img2threejs/img2@0.4.0 doctor --json
    npx --yes @img2threejs/img2@0.4.0 sync --check
    npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
    ```

    Confirm a consumer without an authenticated npm session can complete install → link → doctor → sync → capabilities and removal. Do not weaken access or use `--force` to conceal the img2 transport failure. Record the failure mode in the release notes; do not assert `add npm:` works.
7. **Keep versions immutable.** Record the published version and `dist.integrity` for each release; do not republish the same version with different bytes. `npm install --prefix "$HOME/.local/share/img2interior" @img2threejs/img2interior@<version>` updates the live link in place; the host link points at the installed prefix, so the consumer's next launch sees the new bytes. `npm install` alone is not host skill registration; `add --link` is. A package release does not register an img2 catalog entry; the harness `add --link` flow against the installed prefix is sufficient on its own. The README's install block and the badge URLs reflect the published `@img2threejs/img2interior@0.3.1` exactly; any new release updates the version specifier in lockstep with the tarball.

### README and showcase delivery

npm renders a root README using [GitHub Flavored Markdown](https://docs.npmjs.com/about-package-readme-files/). A GitHub README change does not update a published npm version until a new package release. Image bytes are pinned to an immutable commit in the separately hosted [media repository](https://github.com/img2threejs/img2interior-media) — those raw-image URLs are public, but they reference media, not source. The same image bytes are included in `docs/showcase/` for local viewing; see the [gallery](../docs/showcase/README.md). The live demo link in the README points at [img2threejs.io/living-room/](https://img2threejs.io/living-room/), an actual hosted Three.js viewer of the same authored scene. Test image delivery without GitHub/npm credentials and keep alt text/captions accurate. No signed expiring image URLs, unpublished package URLs, CI badges implying public access, or unverified live-demo links.

Detailed guides ship with the public package and source. Both channels expose the same source, so a reference link in a guide works from either install method (the `npm install --prefix` flow or the Git clone flow). Public media access grants neither plugin permission nor access to any user's project assets. Updating previews is independent of releasing a new package.

## Maintainer checks

Run from the plugin root. Set `IMG2_HARNESS_SOURCE` to a compatible img2 Git checkout; the [CI workflow](../.github/workflows/ci.yml) records the pinned revision. Install image dependencies in a project-local environment before the Python suite.

```sh
export IMG2_HARNESS_SOURCE=/absolute/path/to/img2
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-surfaces.txt
python -m unittest discover -s tests -v
npm ci --prefix runtime/viewer
npm run build --prefix runtime/viewer
VIEWER_ROOT="$PWD/runtime/viewer" node --test tests/viewer/*.test.mjs
python scripts/verify_install.py --harness-source "$IMG2_HARNESS_SOURCE"
python scripts/package_plugin.py
```

Native regressions need the separate authoring environment: set `IMG2_BLENDER_PYTHON` to that Python executable before the suite. Optional-environment skips are not passing native checks. Tests/builds do not replace changed-path rendering or browser inspection.

`verify_install.py` runs the official CLI with temporary HOME/IMG2_HOME and three isolated host configurations; it does not alter real host settings or launchers. It checks install/add, identity, links, doctor, sync, capability resolution and removal. The source packager writes a deterministic versioned ZIP and `SHA256SUMS` under `dist/`, including `LICENSE`, `THIRD_PARTY_NOTICES.md`, the retained Apache-2.0 license and the small documentation gallery, not generated scene assets. Neither command publishes anything.

Official references: [publishing packages](https://docs.npmjs.com/creating-and-publishing-packages/), [package metadata](https://docs.npmjs.com/cli/v11/configuring-npm/package-json/), [npm provenance](https://docs.npmjs.com/generating-provenance-statements/) and the [img2 harness](https://github.com/img2threejs/img2).
