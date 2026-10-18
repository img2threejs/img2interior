# Tool input contracts

All JSON uses UTF-8. Paths on commands are explicit local files; no tool uploads or generates paid assets. Tools require linked img2_core API 1 and write only their own workspace artifacts/state. Audit gates recheck current inputs instead of trusting a saved pass flag.

## Intake

`init --image PATH --intake PATH --workspace PATH` requires:

```json
{
  "schemaVersion": 1,
  "sourceKind": "synthetic-design-reference",
  "authorization": "Actual permission and scope, reviewed by the project owner",
  "scale": {"unit":"m","basis":"authored-estimate","note":"Single-image scale and unseen depth are authored"},
  "components": ["room-shell","sofa","glazing"],
  "unknowns": ["Unseen construction is not measured"],
  "interactionRequired": true
}
```

`sourceKind`: `synthetic-design-reference`, `photo`, `render`, `floorplan`. Scale basis: `authored-estimate` or `measured`; units `m`. Components are unique nonempty IDs; unknowns is an explicit array. Authorization is a declaration, not a tool-verifiable license. The pinned intake snapshot is `.img2/artifacts/interior/intake.json`.

## Material policy

`audit_materials.py --glb PATH --policy PATH --workspace PATH` requires:

```json
{
  "schemaVersion": 1,
  "materials": [{
    "name": "Exact exported glTF material name",
    "requireBaseColorTexture": true,
    "requireNormalTexture": true,
    "requireRoughnessTexture": true,
    "minRoughnessFactor": 0.8,
    "maxMetallicFactor": 0,
    "maxSheenColorFactor": 0.2,
    "texCoord": 0
  }]
}
```

Only `name` is mandatory per material; declare checks intentionally, not by assumed defaults. Names must be unique and select actual exported materials. Scalar bounds are finite in [0,1], `texCoord` a nonnegative integer. glTF defaults still apply when a factor/extension is absent. The audit checks texture resources, selected primitive UV presence and texture-transform coordinate overrides; it is not the Khronos validator or a texture pixel decoder. For example, roughnessFactor 1 with a low-valued roughness image can still be glossy.

Output: `.img2/artifacts/interior/material-audit.json`. Gate mode: `--workspace PATH --gate`; it is read-only and rejects changed GLB/policy/receipt inputs.

## Delivery contract

`audit_delivery.py --contract PATH --workspace PATH` requires `schemaVersion:1`, `root`, `assets`, `runtime`, `portable`, `native`, and `limitations`.

- `root`: explicit asset directory; relative paths resolve against the contract file. An absolute existing project root is allowed for read-only inspection without large asset copies.
- Each `assets` row: unique nonempty `id`, `role`, POSIX relative `path`, exact expected 64-hex `sha256`.
- Roles: exactly one each `source`, `runtime`, `portable`, `native`; any number of `sidecar` rows.
- All resolved files must stay under root; duplicate paths/IDs, symlink escapes, URLs and missing bytes fail.
- `runtime`: `{"asset":"runtime-id","sidecars":["atlas-id","probe-id"]}`. Reference every sidecar; no undeclared/foreign-role dependency.
- `portable`: `{"asset":"portable-id","limitations":["Static appearance snapshot; no browser cloth physics"]}`.
- `native`: `{"asset":"native-id"}`.
- `limitations`: nonempty strings declaring global assumptions/transport/device limits.

Use observed SHA256s, not invented example digests. The tool cannot establish their provenance or consumer/visual acceptance. Runtime and portable must not be the same file/bytes under two names.

Output: `.img2/artifacts/interior/delivery-audit.json`. Gate mode: `--workspace PATH --gate`; changing the contract or an asset invalidates the saved audit.

## Review and exit codes

`interior_workflow.py record --stage NAME --decision accept|reject|request-input|stop --reviewer NAME --note TEXT --evidence PATH` (repeat evidence flag for multiple files). Stages: `intake,camera,geometry,materials,lighting,interaction,delivery,review`. Evidence resolves inside the workspace and is hash-pinned. `revise --from NAME --reason TEXT` retains history and invalidates the dependent suffix. `next`/`report` are read-only.

Audits/gates: 0 pass, 1 evaluated failure, 2 malformed/error. A gate prints exactly one `img2.gate-verdict` envelope. The real runner produces `img2.gate-run` and stops on a blocking non-pass. Workflow `next` uses 3 for an explicit input/stop block. A passing gate does not authenticate a reviewer or inspect screenshot meaning.
