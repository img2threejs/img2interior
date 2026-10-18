# Install and maintain

## Requirements

- img2 harness/CLI >=0.4.0, Node.js >=18, Git, Python >=3.10.
- A configured Claude Code, Codex or OpenCode host. Hermes is not supported by this harness.
- Production native tools: isolated Python 3.11/bpy 4.3.0/NumPy 1.26.4 (`requirements-authoring.txt`); separate NumPy/Pillow image environment (`requirements-surfaces.txt`). Audit/state tools remain stdlib plus core API 1.
- Workspace-local pinned npm dependencies and a real WebGL browser for the viewer/validator. The pinned viewer accepts Node 18, 20 or >=22; production preflight checks the actual binary. See [production setup and commands](production-runbook.md); a harness install does not silently install bpy, image packages or a web app.

## Install the private source checkout

Access to `img2threejs/img2interior` is required. Use authenticated HTTPS Git credentials (or an authorized SSH key); never put access tokens in a remote URL. Linking does not make the source public.

```sh
git clone https://github.com/img2threejs/img2interior.git "$HOME/img2interior"
npx --yes @img2threejs/img2@0.4.0 install --yes
npx --yes @img2threejs/img2@0.4.0 add --link "$HOME/img2interior" --yes
npx --yes @img2threejs/img2@0.4.0 doctor
npx --yes @img2threejs/img2@0.4.0 sync --check
npx --yes @img2threejs/img2@0.4.0 capabilities --from-kind image --to-kind interior-scene-candidate --plugin interior --json
```

If the harness already exists, the first command preserves that checkout; it is not an upgrade command. Check its compatibility before adding. Restart the agent session after linking.

`interior` is the manifest/registry ID, `img2-interior` the harness-derived skill name, and `img2interior` this repository's name. The host link points through `$IMG2_HOME/plugins/interior/` to this persistent checkout. Do not move/delete a linked source. `_img2_local.py` in root/tools is generated and ignored, not committed or distributed.

This release supports persistent checkout/archive installation. Source hosting, including a private GitHub repository, does not publish an npm package or register the plugin in the official catalog. Do not run `img2 add interior` until an actual catalog entry exists. An extracted release archive installs with the same `add --link /absolute/extracted/img2interior` command.

## Inspect and remove

```sh
npx --yes @img2threejs/img2@0.4.0 list
npx --yes @img2threejs/img2@0.4.0 update interior --check
npx --yes @img2threejs/img2@0.4.0 remove interior --yes
```

Local links are live; `update` does not fetch them. Removal unregisters owned links, not the original checkout. Never use `--force` to hide another registration or overwrite an unrelated host path. Review the harness's refusal instead.

## Project boundary

Keep the current directory in the authored project. Resolve `SKILL_DIR` from the linked skill, then call its tools by absolute path. Do not `cd` into the plugin and initialize a room there. All plugin state is in the project's `.img2/state.json`, under `plugins.interior`; receipts are under `.img2/artifacts/interior/`.

`interior_project.py start` pins a supplied image; the agent authors its intake/spec/builder and executes the full loop. `install-viewer` and the explicit hash-guarded `use-recipe` copy owned templates into W with preflight collision checks. A new image is never routed to the old room. Keep environment/dependency/build installs local and do not turn the installed plugin into the generated app.

## Isolated installation proof

```sh
python3 scripts/verify_install.py --harness-source /absolute/path/to/img2
```

This runs the official CLI with a temporary HOME/IMG2_HOME and three temporary host configurations; it does not alter real host settings or launchers. It checks install/add, registry identity, host links, doctor, sync, capability resolution and removal. Use a Git checkout of the harness, not a random Python directory.

## Release and catalog boundaries

Keep the repository private unless its owner separately authorizes a visibility change. Repository hosting and source ZIPs do not create an npm package, semver-tagged release or catalog entry. Request those operations separately; if an npm convenience installer is authorized, use the harness's official `create-img2-plugin-cli`, not a parallel custom installer.
