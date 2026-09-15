import { cp, mkdir, readdir, readFile, realpath, rm, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const profile = process.argv[2] ?? 'debug';
if (!['debug', 'release', 'qa'].includes(profile)) throw new Error('Unknown packaging profile.');
const artifacts = path.join(root, 'artifacts');
await mkdir(artifacts, { recursive: true });
if (profile !== 'qa') {
  const output = path.join(artifacts, profile === 'debug' ? 'desktop-debug' : 'desktop');
  if (existsSync(output)) {
    const resolved = await realpath(output);
    const parent = await realpath(artifacts);
    if (!resolved.toLowerCase().startsWith(`${parent.toLowerCase()}${path.sep}`)) throw new Error('Desktop output is outside the artifact directory.');
    await rm(output, { recursive: true });
  }
  await mkdir(output, { recursive: true });
  await cp(path.join(root, 'desktop/target', profile, 'VisionStudio.exe'), path.join(output, 'VisionStudio.exe'));
  await cp(path.join(artifacts, 'backend'), path.join(output, 'backend'), { recursive: true });
  await cp(path.join(root, 'installer/desktop-README.md'), path.join(output, 'README.md'));
  console.log(`Desktop application: ${output}`);
}
if (profile !== 'debug') {
  const bundle = path.join(root, 'desktop/target/release/bundle/nsis');
  const prefix = profile === 'qa' ? 'Vision Studio QA_' : 'VisionStudio_';
  const installers = (await readdir(bundle)).filter(name => name.startsWith(prefix) && name.endsWith('-setup.exe'));
  if (installers.length !== 1) throw new Error('Expected exactly one matching NSIS installer.');
  const name = profile === 'qa' ? 'VisionStudio-QA-Setup.exe' : 'VisionStudio-Setup.exe';
  const destination = path.join(artifacts, name);
  await cp(path.join(bundle, installers[0]), destination);
  const digest = createHash('sha256').update(await readFile(destination)).digest('hex');
  await writeFile(`${destination}.sha256`, `${digest}  ${name}\n`);
  await cp(path.join(root, 'desktop/target/release/nsis/x64/installer.nsi'), path.join(artifacts, `${name}.nsi`));
  console.log(`Installer: ${destination}`);
}
