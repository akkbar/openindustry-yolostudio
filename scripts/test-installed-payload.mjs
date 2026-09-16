import { readFile } from 'node:fs/promises';

const expected = await readFile(new URL('../artifacts/desktop/OpenIndustry%20Vision%20Studio.exe', import.meta.url));
const installed = await readFile(process.argv[2]);
// Tauri temporarily patches this marker when creating NSIS packages, then
// restores the portable binary. Account for that one documented metadata field.
const portableTag = Buffer.from('__TAURI_BUNDLE_TYPE_VAR_UNK');
const installerTag = Buffer.from('__TAURI_BUNDLE_TYPE_VAR_NSS');
const offset = expected.indexOf(portableTag);
if (offset < 0 || offset !== expected.lastIndexOf(portableTag)) {
  throw new Error('The release executable has an unexpected Tauri bundle marker.');
}
installerTag.copy(expected, offset);
if (!installed.equals(expected)) {
  throw new Error('The installed desktop does not match the release payload.');
}
console.log('Installed desktop matches the release payload, including its NSIS bundle marker.');
