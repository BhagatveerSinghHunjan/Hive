const { contextBridge, ipcRenderer } = require('electron');

function subscribe(channel, callback) {
  const handler = (_event, payload) => callback(payload);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
}

contextBridge.exposeInMainWorld('hive', {
  send: (msg) => ipcRenderer.send('hive:send', msg),
  ready: () => ipcRenderer.send('hive:renderer-ready'),
  restart: () => ipcRenderer.invoke('hive:restart'),
  onEvent: (cb) => subscribe('hive:event', cb),
  onLog: (cb) => subscribe('hive:log', cb),
  onExit: (cb) => subscribe('hive:runtime-exit', cb),
});
