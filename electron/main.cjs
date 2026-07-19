const path = require('node:path');
const { app, BrowserWindow, ipcMain } = require('electron');
const { CoreManager } = require('./core-manager.cjs');

let mainWindow;
let manager;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 760,
    minWidth: 900,
    minHeight: 620,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  manager = new CoreManager(
    app.getAppPath(),
    (line) => mainWindow?.webContents.send('core:log', line),
    (status) => mainWindow?.webContents.send('core:status-changed', status)
  );

  if (!app.isPackaged) mainWindow.loadURL('http://localhost:5173');
  else mainWindow.loadFile(path.join(app.getAppPath(), 'dist', 'index.html'));
}

app.whenReady().then(() => {
  createWindow();
  ipcMain.handle('cores:list', () => manager.listCores());
  ipcMain.handle('profiles:list', (_e, coreId) => manager.listProfiles(coreId));
  ipcMain.handle('profiles:read', (_e, coreId, fileName) => manager.readProfile(coreId, fileName));
  ipcMain.handle('profiles:save', (_e, coreId, fileName, content) => manager.saveProfile(coreId, fileName, content));
  ipcMain.handle('profiles:create', (_e, coreId, fileName, content) => manager.saveProfile(coreId, fileName, content, true));
  ipcMain.handle('profiles:delete', (_e, coreId, fileName) => manager.deleteProfile(coreId, fileName));
  ipcMain.handle('core:start', (_e, coreId, fileName) => manager.start(coreId, fileName));
  ipcMain.handle('core:stop', () => manager.stop());
  ipcMain.handle('core:status', () => manager.status());
});

app.on('window-all-closed', () => {
  manager?.stop();
  if (process.platform !== 'darwin') app.quit();
});
