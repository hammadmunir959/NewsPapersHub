const { app, BrowserWindow } = require('electron');
const path = require('path');
const net = require('net');
const { spawn } = require('child_process');

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8765;

function getBackendPath() {
    if (app.isPackaged) {
        return path.join(process.resourcesPath, 'bin', 'newspapershub-backend');
    }
    return path.join(__dirname, 'bin', 'newspapershub-backend');
}

function startBackend() {
    const backendPath = getBackendPath();
    console.log(`[Electron] Starting backend from: ${backendPath}`);

    backendProcess = spawn(backendPath, [], {
        cwd: path.dirname(backendPath),
        env: { ...process.env, PROJECT_ROOT: path.dirname(backendPath) }
    });

    backendProcess.stdout.on('data', (data) => console.log(`[Backend] ${data}`));
    backendProcess.stderr.on('data', (data) => console.error(`[Backend Error] ${data}`));

    backendProcess.on('close', (code) => {
        console.log(`[Backend] Process exited with code ${code}`);
    });
}

function checkPort(port) {
    return new Promise((resolve) => {
        const socket = new net.Socket();
        socket.setTimeout(500);
        socket.on('connect', () => { socket.destroy(); resolve(true); });
        socket.on('error', () => resolve(false));
        socket.on('timeout', () => { socket.destroy(); resolve(false); });
        socket.connect(port, '127.0.0.1');
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function waitForBackend(port, retries = 30) {
    for (let i = 0; i < retries; i++) {
        const alive = await checkPort(port);
        if (alive) return true;
        await sleep(1000);
    }
    return false;
}

async function createWindow() {
    startBackend();

    mainWindow = new BrowserWindow({
        width: 1280,
        height: 800,
        show: false,
        title: 'NewsPapersHub',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        }
    });

    // Show splash while waiting for backend
    mainWindow.loadFile(path.join(__dirname, 'splash.html'));
    mainWindow.show();

    const backendReady = await waitForBackend(BACKEND_PORT);

    if (!backendReady) {
        mainWindow.loadFile(path.join(__dirname, 'error.html'));
        return;
    }

    // Load Flutter Web app
    mainWindow.loadFile(path.join(__dirname, 'web', 'index.html'));

    // Remove menu bar for clean look
    mainWindow.setMenuBarVisibility(false);
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (backendProcess) backendProcess.kill();
    if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
