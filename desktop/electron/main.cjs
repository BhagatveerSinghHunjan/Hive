const { app, BrowserWindow, ipcMain, screen, Menu } = require('electron');
const path = require('node:path');
const { PythonBridge } = require('./python-bridge.cjs');

// Menu bar / About name — must run before ready on macOS.
app.setName('HIVE');
if (process.platform === 'win32') {
  app.setAppUserModelId('com.hive.desktop');
}

const REPO_ROOT = process.env.HIVE_ROOT || path.resolve(__dirname, '..', '..');
const DEV_URL = process.env.VITE_DEV_SERVER_URL;
const ICON_PNG = path.join(__dirname, '..', 'build', 'icon.png');
const ICON_ICNS = path.join(__dirname, '..', 'build', 'icon.icns');
const APP_ICON = process.platform === 'darwin' ? ICON_ICNS : ICON_PNG;

let win = null;
let bridge = null;
let rendererReady = false;
let pendingEvents = [];
let quitting = false;

function send(channel, payload) {
  if (win && !win.isDestroyed()) {
    win.webContents.send(channel, payload);
  }
}

function sendEvent(msg) {
  if (rendererReady) {
    send('hive:event', msg);
  } else {
    // Keep startup events (especially `ready`) until React has subscribed.
    pendingEvents.push(msg);
    if (pendingEvents.length > 200) pendingEvents.shift();
  }
}

function startBridge() {
  if (bridge && bridge.isRunning()) return;
  if (bridge) bridge.destroy();

  bridge = new PythonBridge({
    repoRoot: REPO_ROOT,
    onEvent: sendEvent,
    onLog: (line) => send('hive:log', line),
    onExit: (info) => {
      const failedBridge = bridge;
      bridge = null;
      send('hive:runtime-exit', info);
      if (failedBridge) failedBridge.destroy();
    },
  });
  bridge.start();
}

async function restartBridge() {
  rendererReady = true;
  pendingEvents = [];
  if (bridge) {
    await bridge.stop();
    bridge = null;
  }
  startBridge();
  return { ok: true };
}

function createWindow() {
  // Fit inside the usable desktop area. Hardcoded sizes overflow at 125% scaling.
  const { workAreaSize } = screen.getPrimaryDisplay();
  const width = Math.min(1280, Math.max(960, workAreaSize.width - 64));
  const height = Math.min(760, Math.max(600, workAreaSize.height - 64));

  win = new BrowserWindow({
    width,
    height,
    minWidth: Math.min(1024, width),
    minHeight: Math.min(640, height),
    center: true,
    backgroundColor: '#0d0b08',
    title: 'HIVE Desktop',
    icon: APP_ICON,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  win.webContents.on('did-start-loading', () => {
    rendererReady = false;
  });

  win.webContents.on('did-finish-load', () => {
    if (bridge && bridge.isRunning()) {
      sendEvent({ type: 'ready' });
    } else {
      startBridge();
    }
  });

  win.on('closed', () => {
    win = null;
  });

  if (DEV_URL) {
    win.loadURL(DEV_URL);
  } else {
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }
}

app.whenReady().then(() => {
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return;
  }

  app.on('second-instance', () => {
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  ipcMain.on('hive:send', (_event, msg) => {
    if (bridge) bridge.send(msg);
  });

  ipcMain.on('hive:renderer-ready', () => {
    rendererReady = true;
    if (!bridge) startBridge();
    const queued = pendingEvents;
    pendingEvents = [];
    for (const msg of queued) send('hive:event', msg);
  });

  ipcMain.handle('hive:restart', async () => restartBridge());

  if (process.platform === 'darwin' && app.dock) {
    try {
      app.dock.setIcon(ICON_PNG);
    } catch {
      // Native dock icon is best-effort in unpackaged electron .
    }
    Menu.setApplicationMenu(
      Menu.buildFromTemplate([
        {
          label: 'HIVE',
          submenu: [
            { role: 'about' },
            { type: 'separator' },
            { role: 'services' },
            { type: 'separator' },
            { role: 'hide' },
            { role: 'hideOthers' },
            { role: 'unhide' },
            { type: 'separator' },
            { role: 'quit' },
          ],
        },
        { role: 'editMenu' },
        { role: 'viewMenu' },
        { role: 'windowMenu' },
      ]),
    );
  }

  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  app.quit();
});

app.on('before-quit', (event) => {
  if (bridge && !quitting) {
    quitting = true;
    event.preventDefault();
    const active = bridge;
    bridge = null;
    active
      .stop()
      .catch(() => {})
      .finally(() => {
        app.quit();
      });
  }
});
