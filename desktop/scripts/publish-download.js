#!/usr/bin/env node
/** Copy the built Mac zip into the landing site downloads folder. */
const fs = require('node:fs');
const path = require('node:path');

const desktop = path.resolve(__dirname, '..');
const releaseDir = path.join(desktop, 'release');
const landingDownloads = path.resolve(desktop, '..', 'landing', 'downloads');
const dest = path.join(landingDownloads, 'HIVE-mac.zip');

fs.mkdirSync(landingDownloads, { recursive: true });

const candidates = fs.existsSync(releaseDir)
  ? fs
      .readdirSync(releaseDir)
      .filter((name) => name.endsWith('.zip') && name.toLowerCase().includes('hive'))
      .map((name) => path.join(releaseDir, name))
  : [];

if (!candidates.length) {
  console.error('No HIVE zip found in desktop/release. Run: npm run dist');
  process.exit(1);
}

candidates.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
fs.copyFileSync(candidates[0], dest);
console.log(`Copied ${candidates[0]} → ${dest}`);
console.log('Landing download URL: /downloads/HIVE-mac.zip');
