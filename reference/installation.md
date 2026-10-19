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

## npm release plan

The GitHub repository stays private. npm is the intended installer channel, but this plugin does not yet include a generated npm installer or a published npm release. The source installation above remains the available path.

### Choose the artifact and access model

| Model | What npm distributes | What users need |
|---|---|---|
| Public installer, private GitHub implementation | Only the CLI, package metadata, and public README/license | Authorized HTTPS Git access to this repository |
| Public payload package, private GitHub development | The plugin implementation itself | Public npm access; included code is no longer private |
| Private payload package, private GitHub development | The plugin implementation, restricted by npm permissions | A paid npm user/organization account, npm authentication, and package read access |

The recommended private-source model is the first row, using the official installer generator. A public installer does not grant access to a private Git repository. A private npm payload can avoid GitHub access for consumers, but package readers can still inspect downloaded code. These controls do not replace or change the existing Apache-2.0 license.

See npm's [private package requirements](https://docs.npmjs.com/about-private-packages). Decide on payload visibility and licensing before authorizing the first publish.

### Prepare an installer release

1. **Confirm ownership and versions.** Choose an available npm package name owned by the maintainer or organization. Keep the plugin ID `interior` and skill name `img2-interior`. Select a reviewed plugin semver tag or full commit SHA; do not make an installer silently track an unreviewed branch.
2. **Generate the official wrapper.** Use `create-img2-plugin-cli` from a reviewed img2 version with `--private-repo`, `--source img2threejs/img2interior`, an explicit `--ref`, and a reviewed full `--workflow-ref` SHA. The generator creates `cli/`, its tests/public README/license, a publish workflow, and `CLI_QUICKSTART.md`; none of these have been generated in this repository yet.
3. **Review the tarball, not just the repository.** Run the generated CLI tests and `npm pack --dry-run` from `cli/`; inspect the actual packed tarball and test that artifact in an isolated consumer. Allow only the intended installer files and required package metadata/documentation. Do not include the plugin payload, credentials, workspace state, references, scene assets, or environments. Do not publish from the plugin root.
4. **Authorize the first publish.** Use an npm account with package write access and 2FA. Follow the generated quickstart for the reviewed package name, explicit access setting, and first manual release. For this public-wrapper model, the access setting is `public`; publishing is a separate authorized operation, not part of installing or testing the skill.
5. **Configure tokenless CI releases.** After the package exists, configure npm trusted publishing for this repository's exact caller workflow filename and the required publish permission. Use a supported GitHub-hosted runner with `id-token: write`; do not store a long-lived npm write token. Trusted publishing requires Node ≥22.14.0 and npm ≥11.5.1; the SDK's current release-setup instructions require npm ≥11.15 for its trust-management command.
6. **Keep private-source provenance disabled.** Generate with `--private-repo` and retain `provenance=false`. npm trusted publishing supports authentication for this release flow, but npm provenance attestations are not supported for private source repositories, even when the npm installer is public.
7. **Verify and document consumer access.** Test dry-run/install/doctor/removal in isolated host directories with authorized HTTPS Git credentials; also check an unauthorized consumer fails without a partial plugin registration. npm authentication alone is not GitHub authorization. Keep credentials out of package contents, command URLs, logs, and public examples.
8. **Release immutable versions.** Plugin source tags use `vX.Y.Z`; generated installer release tags use `cli-vX.Y.Z`. Publish the exact tested tarball, record the installed source ref/integrity, and update public install instructions only after the package/version is available and verified. npm installation does not register a catalog entry.

Official references: [img2 wrapper contract](https://github.com/img2threejs/img2/blob/main/docs/WRITING_A_PLUGIN.md#10-plugin-cli-wrapper-optional), [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/), and [npm provenance requirements](https://docs.npmjs.com/generating-provenance-statements/).
