const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('openProxy', {
  listCores: () => ipcRenderer.invoke('cores:list'),
  listProfiles: (coreId) => ipcRenderer.invoke('profiles:list', coreId),
  readProfile: (coreId, fileName) => ipcRenderer.invoke('profiles:read', coreId, fileName),
  saveProfile: (coreId, fileName, content) => ipcRenderer.invoke('profiles:save', coreId, fileName, content),
  createProfile: (coreId, fileName, content) => ipcRenderer.invoke('profiles:create', coreId, fileName, content),
  deleteProfile: (coreId, fileName) => ipcRenderer.invoke('profiles:delete', coreId, fileName),
  startCore: (coreId, fileName) => ipcRenderer.invoke('core:start', coreId, fileName),
  stopCore: () => ipcRenderer.invoke('core:stop'),
  getStatus: () => ipcRenderer.invoke('core:status'),
  onLog: (callback) => ipcRenderer.on('core:log', (_event, line) => callback(line)),
  onStatus: (callback) => ipcRenderer.on('core:status-changed', (_event, status) => callback(status))
});
