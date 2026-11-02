import { execFileSync } from 'node:child_process';
import { copyFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
execFileSync('moon', ['build', '--target', 'js', '--release', 'browser'], { cwd: root, stdio: 'inherit' });
copyFileSync(new URL('../_build/js/release/build/browser/browser.js', import.meta.url), new URL('./decoder.js', import.meta.url));
execFileSync('moon', ['build', '--target', 'wasm-gc', '--release', 'browser'], { cwd: root, stdio: 'inherit' });
copyFileSync(new URL('../_build/wasm-gc/release/build/browser/browser.wasm', import.meta.url), new URL('./decoder.wasm', import.meta.url));
console.log('Playground decoder built. Run node playground/serve.mjs');
