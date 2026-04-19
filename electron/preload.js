const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    getBackendPort: () => 8765,
    onServiceStatus: (callback) => ipcRenderer.on('service-status', callback),
});
