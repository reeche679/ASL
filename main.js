const { app, BrowserWindow } = require('electron');
const path = require('path');

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false,
            enableRemoteModule: true
        }
    });

    // Load your HTML file
    mainWindow.loadFile('index.html');

    // Open the DevTools by default
    mainWindow.webContents.openDevTools();

    // Handle DevTools errors
    mainWindow.webContents.on('devtools-opened', () => {
        // Ensure DevTools loads properly
        mainWindow.webContents.executeJavaScript(`
            if (!window.__devtools_loaded) {
                window.__devtools_loaded = true;
                window.location.reload();
            }
        `);
    });
}

app.whenReady().then(() => {
    createWindow();

    app.on('activate', function () {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', function () {
    if (process.platform !== 'darwin') app.quit();
}); 