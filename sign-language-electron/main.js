const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { PythonShell } = require('python-shell');

let mainWindow;
let pythonProcess;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  mainWindow.loadFile('index.html');
  
  // Open DevTools in development
  mainWindow.webContents.openDevTools();
}

function startPythonProcess() {
  const pythonPath = path.join(__dirname, '..', 'venv310', 'Scripts', 'python.exe');
  console.log('Using Python path:', pythonPath);

  let options = {
    mode: 'text',
    pythonPath: pythonPath,
    pythonOptions: ['-u'], // unbuffered output
    scriptPath: path.join(__dirname),
    args: []
  };

  console.log('Starting Python process with options:', options);

  try {
    pythonProcess = new PythonShell('sign_detector.py', options);

    pythonProcess.on('message', function (message) {
      try {
        // Send message to renderer process
        mainWindow.webContents.send('python-message', message);
      } catch (error) {
        console.error('Error processing message:', error);
        mainWindow.webContents.send('python-error', `Error processing message: ${error.message}`);
      }
    });

    pythonProcess.on('error', function (err) {
      console.error('Python Error:', err);
      mainWindow.webContents.send('python-error', `Python Error: ${err.message}`);
    });

    pythonProcess.on('stderr', function (stderr) {
      console.error('Python stderr:', stderr);
      mainWindow.webContents.send('python-error', `Python stderr: ${stderr}`);
    });

    pythonProcess.on('close', function () {
      console.log('Python process closed');
      mainWindow.webContents.send('python-closed');
      // Restart Python process if it closes unexpectedly
      setTimeout(startPythonProcess, 1000);
    });
  } catch (error) {
    console.error('Failed to start Python process:', error);
    mainWindow.webContents.send('python-error', `Failed to start Python process: ${error.message}`);
  }
}

app.whenReady().then(() => {
  createWindow();
  startPythonProcess();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    if (pythonProcess) {
      pythonProcess.kill();
    }
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
}); 