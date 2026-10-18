'use strict';
const { app, BrowserWindow, dialog, ipcMain, Menu, safeStorage, session, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const { createSession, isLocalAddress, isApplicationUrl, backendCommand, privateEnvironment } = require('./session.cjs');
app.setName('Video Anatomy');
// Set shell state before acquiring the single-instance lock; otherwise Electron
// creates the shared library directory before an atomic first import can run.
const shellData = path.join(app.getPath('appData'), 'Video Anatomy Desktop');
fs.mkdirSync(shellData, { recursive: true });
app.setPath('userData', shellData);
let backend, setupWindow, workspace, stopping = false;
const root = path.resolve(__dirname, '..');
const setupUrl = require('node:url').pathToFileURL(path.join(__dirname, 'setup.html')).href;
const libraryPath = () => path.join(app.getPath('appData'), 'Video Anatomy');
const keyPath = () => path.join(app.getPath('userData'), 'credentials', 'openai-key.encrypted');
const canRememberKey = () => process.platform === 'darwin' && safeStorage.isEncryptionAvailable();
function storedKey() {
  if (!canRememberKey() || !fs.existsSync(keyPath())) return '';
  try { return safeStorage.decryptString(fs.readFileSync(keyPath())); } catch { return ''; }
}
function saveKey(key) {
  if (!canRememberKey()) throw new Error('Keychain encryption is unavailable. Use session-only mode.');
  fs.mkdirSync(path.dirname(keyPath()), { recursive: true, mode: 0o700 });
  fs.writeFileSync(keyPath(), safeStorage.encryptString(key), { mode: 0o600 });
}
function trustedSetup(event) { return setupWindow && event.sender === setupWindow.webContents && event.senderFrame.url === setupUrl; }
function stopBackend() {
  if (backend && backend.exitCode === null) {
    backend.kill('SIGTERM');
    const processToStop = backend;
    setTimeout(() => { if (processToStop.exitCode === null) processToStop.kill('SIGKILL'); }, 4000).unref();
  }
}
function guardWindow(window, allowed) {
  const openSource = url => {
    try {
      const parsed = new URL(url);
      if (window === workspace && parsed.protocol === 'https:' && !parsed.username && !parsed.password) shell.openExternal(parsed.href);
    } catch { /* Invalid links stay closed. */ }
  };
  window.webContents.setWindowOpenHandler(({ url }) => { openSource(url); return { action: 'deny' }; });
  window.webContents.on('will-navigate', (event, url) => { if (!allowed(url)) { event.preventDefault(); openSource(url); } });
  window.webContents.on('will-redirect', (event, url) => { if (!allowed(url)) event.preventDefault(); });
}
async function startBackend(apiKey, migrationSource) {
  const token = createSession();
  const config = backendCommand({ packaged: app.isPackaged, resourcesPath: process.resourcesPath, root });
  if (!fs.existsSync(config.command)) throw new Error('The backend runtime is missing. See the desktop README for the macOS build steps.');
  const args = [...config.args, '--desktop', '--no-open', '--port', '0', '--data-dir', libraryPath()];
  if (migrationSource) args.push('--migrate-from', migrationSource);
  backend = spawn(config.command, args, { cwd: config.cwd, env: privateEnvironment(config.mediaBin), stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
  backend.stdin.end(JSON.stringify({ api_key: apiKey, session_token: token }) + '\n');
  const address = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => { stopBackend(); reject(new Error('The backend did not become ready within 60 seconds. Your library has not been deleted.')); }, 60000);
    const lines = readline.createInterface({ input: backend.stdout });
    let resolved = false;
    lines.on('line', (line) => {
      if (!line.startsWith('VIDEO_ANATOMY_READY ')) return;
      try {
        const result = JSON.parse(line.slice('VIDEO_ANATOMY_READY '.length));
        if (!isLocalAddress(result.url)) throw new Error('Invalid local address');
        resolved = true; clearTimeout(timeout); resolve(result.url);
      } catch { clearTimeout(timeout); reject(new Error('The backend returned an invalid local address.')); }
    });
    backend.stderr.on('data', () => {});
    backend.once('error', () => { clearTimeout(timeout); reject(new Error('The bundled backend could not start.')); });
    backend.once('exit', () => {
      clearTimeout(timeout);
      if (!resolved) reject(new Error('The backend stopped before startup completed. Close another copy of the app and verify the selected library.'));
      else if (!stopping) { dialog.showErrorBox('Backend stopped', 'Your saved work is retained. Quit and reopen Video Anatomy.'); app.quit(); }
    });
  });
  const privateSession = session.fromPartition('video-anatomy-session');
  privateSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  privateSession.webRequest.onBeforeSendHeaders((details, callback) => {
    if (isApplicationUrl(details.url, address)) callback({ requestHeaders: { ...details.requestHeaders, 'X-Video-Anatomy-Token': token } });
    else callback({ cancel: true });
  });
  workspace = new BrowserWindow({ width: 1440, height: 900, minWidth: 1100, minHeight: 700, title: 'Video Anatomy', show: false, backgroundColor: '#eef1ef', webPreferences: { session: privateSession, contextIsolation: true, nodeIntegration: false, sandbox: true } });
  guardWindow(workspace, url => isApplicationUrl(url, address));
  await workspace.loadURL(address);
  workspace.show();
  if (setupWindow) { setupWindow.destroy(); setupWindow = null; }
  workspace.on('closed', () => { workspace = null; app.quit(); });
}
function showSetup() {
  setupWindow = new BrowserWindow({ width: 560, height: 650, resizable: false, title: 'Video Anatomy — Setup', webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  guardWindow(setupWindow, url => url === setupUrl);
  setupWindow.loadFile(path.join(__dirname, 'setup.html'));
  setupWindow.on('closed', () => { setupWindow = null; if (!workspace) app.quit(); });
}
if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { (workspace || setupWindow)?.show(); (workspace || setupWindow)?.focus(); });
  app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      { label: 'Video Anatomy', submenu: [
        { label: 'Open Library Folder', click: () => { if (fs.existsSync(libraryPath())) shell.openPath(libraryPath()); else dialog.showMessageBox({ message: 'Open a workspace first to create or import its library.' }); } },
        { label: 'Forget Saved API Key', click: () => { if (fs.existsSync(keyPath())) fs.unlinkSync(keyPath()); dialog.showMessageBox({ message: 'Saved key removed', detail: 'Restart the app to stop using the current session key.' }); } },
        { type: 'separator' }, { role: 'quit' }
      ] }, { role: 'editMenu' }, { label: 'View', submenu: [{ role: 'reload' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }, { role: 'togglefullscreen' }] }
    ])); showSetup();
  });
}
ipcMain.handle('setup:status', event => {
  if (!trustedSetup(event)) throw new Error('Invalid setup session.');
  return { hasSavedKey: Boolean(storedKey()), canRemember: canRememberKey(), library: libraryPath() };
});
let chosenMigration;
ipcMain.handle('setup:choose-library', async event => {
  if (!trustedSetup(event)) throw new Error('Invalid setup session.');
  const result = await dialog.showOpenDialog(setupWindow, { title: 'Select the old .local-data/live folder', properties: ['openDirectory', 'showHiddenFiles'] });
  chosenMigration = result.canceled ? undefined : result.filePaths[0]; return chosenMigration || '';
});
ipcMain.handle('setup:start', async (event, options) => {
  if (!trustedSetup(event) || backend) return { ok: false, message: 'A startup is already in progress.' };
  try {
    const key = options.offline ? '' : (options.useSaved ? storedKey() : String(options.key || '').trim());
    if (!options.offline && (!key || /\s/.test(key) || !/^[\x00-\x7f]+$/.test(key))) throw new Error('Enter a complete API key, use a saved key, or open offline.');
    if (options.remember && key) saveKey(key);
    await startBackend(key, chosenMigration); return { ok: true };
  } catch (error) {
    stopBackend(); backend = null; return { ok: false, message: error.message || 'Startup failed. Your saved library is retained.' };
  }
});
app.on('before-quit', event => {
  if (stopping || !backend || backend.exitCode !== null) return;
  event.preventDefault(); stopping = true;
  const processToStop = backend;
  const timeout = setTimeout(() => { if (processToStop.exitCode === null) processToStop.kill('SIGKILL'); app.quit(); }, 4500);
  processToStop.once('exit', () => { clearTimeout(timeout); app.quit(); });
  processToStop.kill('SIGTERM');
});
app.on('window-all-closed', () => app.quit());
