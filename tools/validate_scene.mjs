#!/usr/bin/env node
// Validate actual assets with the pinned workspace dependency; no network callbacks.
import { createHash, randomUUID } from 'node:crypto';
import { lstat, mkdir, readFile, realpath, stat, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const plugin = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const inside = (root, target) => {
  const relative = path.relative(root, target);
  return relative === '' || (!relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative));
};

async function main() {
  const { values } = parseArgs({ options: {
    workspace: { type: 'string' }, asset: { type: 'string' }, 'run-id': { type: 'string', default: randomUUID() },
  } });
  if (!values.workspace || !values.asset) throw new Error('Use --workspace W --asset W-relative.glb [--run-id ID] after npm ci');
  const workspace = await realpath(path.resolve(values.workspace));
  if (inside(await realpath(plugin), workspace)) throw new Error('Authored workspace must be outside the installed plugin');
  const run = values['run-id'];
  if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(run)) throw new Error('run-id must be a plain slug, at most 64 characters');

  async function confined(relative) {
    if (path.isAbsolute(relative)) throw new Error('Expected a workspace-relative asset/output');
    const target = path.resolve(workspace, relative);
    if (!inside(workspace, target)) throw new Error('Resource escapes workspace: ' + relative);
    let current = workspace;
    for (const part of path.relative(workspace, target).split(path.sep)) {
      current = path.join(current, part);
      try {
        if ((await lstat(current)).isSymbolicLink()) throw new Error('Symlinked resource/output is not permitted: ' + relative);
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
    }
    return target;
  }

  const asset = await confined(values.asset);
  if (!/\.(gltf|glb)$/i.test(asset)) throw new Error('Expected a .gltf or .glb file');
  if ((await stat(asset)).size > 512 * 1024 * 1024) throw new Error('Validation input exceeds 512 MiB');
  const bytes = await readFile(asset);
  const require = createRequire(path.join(workspace, 'package.json'));
  const validator = require('gltf-validator');
  const resources = [];
  const report = await validator.validateBytes(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength), {
    uri: path.basename(asset), maxIssues: 10000,
    externalResourceFunction: async uri => {
      if (typeof uri !== 'string' || /^[a-z][\w+.-]*:/i.test(uri) || uri.startsWith('//') || /[?#\\]/.test(uri)) {
        throw new Error('Only local workspace resources may be validated: ' + uri);
      }
      const decoded = decodeURIComponent(uri);
      const target = await confined(path.relative(workspace, path.resolve(path.dirname(asset), decoded)));
      if ((await stat(target)).size > 512 * 1024 * 1024) throw new Error('Validation dependency exceeds 512 MiB');
      const data = await readFile(target);
      resources.push({ path: path.relative(workspace, target), bytes: data.length, sha256: sha256(data) });
      return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    },
  });
  const output = await confined(path.join('.img2/artifacts/interior/production', run, 'khronos-' + path.basename(asset) + '.json'));
  const result = { schemaVersion: 1, asset: values.asset, bytes: bytes.length, sha256: sha256(bytes),
    validatorVersion: validator.version(), resources, report,
    passed: report.issues.numErrors === 0 && report.issues.truncated !== true,
    limit: 'glTF conformance only; no image likeness, native reopening or interaction approval' };
  await mkdir(path.dirname(output), { recursive: true });
  await writeFile(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ ...result, report: report.issues, receipt: path.relative(workspace, output) }, null, 2));
  process.exitCode = result.passed ? 0 : 1;
}

main().catch(error => {
  console.error(JSON.stringify({ status: 'error', reason: String(error.message ?? error) }));
  process.exitCode = 2;
});
