# Install and maintain

## Requirements

- img2 harness/CLI >=0.4.0, core API 1, Node.js 18, 20 or >=22, npm, Git and Python >=3.10. Prefer a supported Node LTS release.
- A configured, image-capable Claude Code, Codex or OpenCode host with command execution and browser/image inspection. Hermes is not supported by this harness.
- Production native tools: isolated Python 3.11/bpy 4.3.0/NumPy 1.26.4 (`requirements-authoring.txt`); separate NumPy/Pillow image environment (`requirements-surfaces.txt`). Audit/state tools remain stdlib plus core API 1.
- Workspace-local pinned npm dependencies and a real WebGL browser for the viewer/validator. See [production setup and commands](production-runbook.md); a harness install does not silently install bpy, image packages or a web app. Compatible Blender wheels must exist for your platform.
- Version 0.3.0 uses the repository's [mixed license](../LICENSE): proprietary portions require prior written authorization. GitHub or npm access alone does not grant usage rights; Apache-2.0 exceptions and earlier grants remain effective.

## Install the private source checkout

Access to `img2threejs/img2interior` is required. Use authenticated HTTPS Git credentials or an authorized SSH key; never put access tokens in a remote URL. Linking does not make the source public. Keep the checkout in a persistent location outside authored projects.

```sh
git clone https://github.com/img2threejs/img2interior.git "$HOME/img2interior"
npx --yes @img2threejs/img2@0.4.0 install --yes
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor --json
npx --yes @img2threejs/img2@0.4.0 sync --check
npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
```

These commands change local harness/host configuration. Skip `install` if a compatible harness already exists; it is not an upgrade command. Do not clone over an existing checkout. Restart the agent session after linking, open the authored project, attach an image and use the [standard prompt](../README.md#copy-and-use-prompt).

`interior` is the manifest/registry ID, `img2-interior` the harness-derived skill name, and `img2interior` this repository's name. The host link points through `$IMG2_HOME/plugins/interior/` to this persistent checkout. Do not move/delete a linked source. `_img2_local.py` in root/tools is generated and ignored, not committed or distributed.

An authorized source archive installs through the same official CLI: extract it into a persistent directory and pass that extracted `img2interior` directory to `add --link`. Use its actual absolute path, not the ZIP path. Source hosting and archives do not create an npm package or catalog entry; do not run `img2 add interior` before a catalog entry exists.

## Inspect and remove

```sh
npx --yes @img2threejs/img2@0.4.0 list
npx --yes @img2threejs/img2@0.4.0 update interior --check
npx --yes @img2threejs/img2@0.4.0 remove interior --yes
```

Local links are live; `update` does not fetch them. Removal unregisters owned links, not the original checkout. Never use `--force` to hide another registration or overwrite an unrelated host path. Review the harness's refusal instead.

## Project boundary

Keep the current directory in the authored project. Resolve `SKILL_DIR` from the linked skill, then call its tools by absolute path. Do not initialize a room inside the plugin. Project state is in `.img2/state.json`, under `plugins.interior`; receipts are under `.img2/artifacts/interior/`.

`interior_project.py start` pins a supplied image; the agent authors intake/spec/builder and executes the full loop. `install-viewer` and the explicit hash-guarded `use-recipe` copy owned templates into the workspace with preflight collision checks. A new image is never routed to the old room. Keep dependency/build installs local; the installed plugin is not the generated app. On resume use the recorded workflow's `next` operation rather than initialize again.

## Private npm release checklist

**Chosen distribution model:** private GitHub development plus a **private scoped npm payload** containing the implementation. No npm package metadata, payload release or catalog entry exists yet; source/archive installation remains the available method. A public wrapper that fetches private GitHub source is not the intended consumer flow.

The historical npm Enterprise product [was sunset](https://docs.npmjs.com/configuring-your-registry-settings-as-an-npm-enterprise-user/). For npm registry distribution, obtain a current user/organization plan supporting private packages, then configure package read/write permissions and authentication. A plan purchase is not a usage license, automatic package publication or code encryption. Do not confuse this with a separately configured GitHub Packages registry.

1. **Confirm the real name, registry and access policy.** Select an owned scoped package name and exact version. Keep plugin ID `interior` and skill name `img2-interior`; align package and plugin versions. Do not advertise a copy/paste npm install command until that real version is published and consumer-tested.
2. **Package the implementation, not a Git-fetch wrapper.** Use a reviewed root `package.json` and explicit file allowlist. Include `plugin.json`, `SKILL.md`, steps/gates, tools, authoring helpers, resource library, viewer/templates, required recipes/examples, references, dependency manifests, README, `docs/showcase/`, root `LICENSE` and `licenses/Apache-2.0.txt`. Include needed scripts/fixtures without generated state. Exclude credentials, generated `_img2_local.py`, environments, `node_modules`, builds, private production reports, full-resolution references and generated scenes.
3. **Keep access and license metadata correct.** Use `license: "SEE LICENSE IN LICENSE"` and `publishConfig.access: "restricted"` for the scoped private payload. `private: true` prevents npm publication; it is not the switch for a publishable private package. Preserve Apache-2.0 exceptions, earlier grants and third-party notices; review Blender/Python API and combined-distribution obligations with qualified counsel. This documentation is not a GPL compliance certification.
4. **Review the actual tarball.** Run `npm pack --dry-run`, build the tarball, inspect its complete file list and install that exact artifact in an isolated consumer. The source ZIP packager is a separate format, not proof of an npm package. Reopen the bundled guides/gallery without GitHub access; verify license files, image paths and required runtime dependencies.
5. **Authorize and perform the first publication separately.** Use explicit restricted access, reviewed bytes, package write permission and the account's required authentication/2FA. Do not publish merely to preview the README. For CI, review current [trusted-publishing support](https://docs.npmjs.com/trusted-publishers/) for the selected registry/account and workflow; never commit credentials or assume an OIDC flow has been configured. Private source repositories do not support npm provenance attestations; keep provenance disabled rather than claim an attestation exists.
6. **Test authenticated consumer registration after publication.** Use the official `img2 add` provider with the published package's exact `npm:` source. Harness 0.4.0 resolves packages with `npm view` and `npm pack`; verify the intended npm registry/auth configuration in practice. Test without GitHub source credentials, plus doctor, sync, capability resolution, update and removal. Packages outside the default `@img2threejs` scope require explicit source approval. Check an unauthorized npm reader fails without partial registration; do not weaken access or use `--force` to conceal failures.
7. **Keep versions immutable and update real instructions.** Record the package version/integrity, verify authorized and unauthorized reads, then replace the README's planned status with the tested install command. Use the official harness for registration; `npm install` alone is not host skill registration. A package release does not register an img2 catalog entry.

### README and showcase delivery

npm renders a root README using [GitHub Flavored Markdown](https://docs.npmjs.com/about-package-readme-files/). A GitHub README change does not update a published npm version until a new package release. Relative private-GitHub image URLs do not grant npm readers GitHub access.

The landing page therefore embeds **public HTTPS previews pinned to an immutable commit** in the separately authorized [media repository](https://github.com/img2threejs/img2interior-media). Only optimized previews and captions are public, never implementation, GLBs, textures, full-resolution inputs or private reports. The same image bytes are included in `docs/showcase/` for local viewing; see the [gallery](../docs/showcase/README.md). Test image delivery without GitHub/npm credentials and keep alt text/captions accurate. No signed expiring image URLs, unpublished package URLs, CI badges implying public access, or unverified live-demo links.

Detailed guides ship with the private payload. Their source links may require GitHub access; npm-only consumers should ask their agent to open the installed guides. Public media access grants neither plugin permission nor access to unpublished scene assets. Updating previews is separate from changing source-repository visibility.

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

`verify_install.py` runs the official CLI with temporary HOME/IMG2_HOME and three isolated host configurations; it does not alter real host settings or launchers. It checks install/add, identity, links, doctor, sync, capability resolution and removal. The source packager writes a deterministic versioned ZIP and `SHA256SUMS` under `dist/`, including both license files and the small documentation gallery, not generated scene assets. Neither command publishes anything.

Official references: [private packages](https://docs.npmjs.com/creating-and-publishing-private-packages/), [package metadata](https://docs.npmjs.com/cli/v11/configuring-npm/package-json/), [npm provenance](https://docs.npmjs.com/generating-provenance-statements/) and the [img2 harness](https://github.com/img2threejs/img2).
