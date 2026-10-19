'use strict';
const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('videoAnatomySetup', {
  status: () => ipcRenderer.invoke('setup:status'),
  chooseLibrary: () => ipcRenderer.invoke('setup:choose-library'),
  start: options => ipcRenderer.invoke('setup:start', options),
});
