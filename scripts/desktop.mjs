import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const env = { ...process.env };
const localCargo = path.join(root, '.tools', 'cargo');
if (existsSync(path.join(localCargo, 'bin', 'cargo.exe'))) {
  env.CARGO_HOME = localCargo;
  env.RUSTUP_HOME = path.join(root, '.tools', 'rustup');
  env.PATH = `${path.join(localCargo, 'bin')}${path.delimiter}${env.PATH}`;
}
const args = process.argv.slice(2);
const cargo = ['check', 'test', 'fmt'].includes(args[0]);
const command = cargo ? 'cargo' : process.execPath;
const commandArgs = cargo
  ? [args[0], ...(args[0] === 'fmt' ? [] : ['--locked']), ...args.slice(1)]
  : [path.join(root, 'node_modules', '@tauri-apps', 'cli', 'tauri.js'), ...args];
const child = spawn(command, commandArgs, { cwd: path.join(root, 'desktop'), env, stdio: 'inherit' });
child.on('error', (error) => { console.error(`Desktop command failed: ${error.message}`); process.exitCode = 1; });
child.on('exit', (code) => { process.exitCode = code ?? 1; });
