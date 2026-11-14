#!/usr/bin/env node
/**
 * Unpackaged `electron .` shows "Electron" in the macOS menu bar because
 * CFBundleName comes from Electron.app. Patch name + icon for local HIVE runs.
 */
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const appPath = path.join(root, 'node_modules', 'electron', 'dist', 'Electron.app');
const plist = path.join(appPath, 'Contents', 'Info.plist');
const resources = path.join(appPath, 'Contents', 'Resources');
const iconSrc = path.join(root, 'build', 'icon.icns');
const iconDst = path.join(resources, 'electron.icns');
const hiveIconDst = path.join(resources, 'hive.icns');

if (!fs.existsSync(plist)) {
  console.warn('[brand-electron] Electron.app not found; skip branding.');
  process.exit(0);
}

function setPlist(key, value) {
  try {
    execFileSync('/usr/libexec/PlistBuddy', ['-c', `Set :${key} ${value}`, plist], {
      stdio: 'ignore',
    });
  } catch {
    try {
      execFileSync('/usr/libexec/PlistBuddy', ['-c', `Add :${key} string ${value}`, plist], {
        stdio: 'ignore',
      });
    } catch (err) {
      console.warn(`[brand-electron] could not set ${key}:`, err.message);
    }
  }
}

setPlist('CFBundleName', 'HIVE');
setPlist('CFBundleDisplayName', 'HIVE');
setPlist('CFBundleIdentifier', 'com.hive.desktop');
setPlist('CFBundleIconFile', 'electron.icns');

if (fs.existsSync(iconSrc)) {
  fs.copyFileSync(iconSrc, iconDst);
  fs.copyFileSync(iconSrc, hiveIconDst);
}

console.log('[brand-electron] Electron.app branded as HIVE');
