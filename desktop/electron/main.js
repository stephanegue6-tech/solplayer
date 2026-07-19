// CrimTrack Desktop — processus principal Electron.
//
// Rôle : au démarrage, lancer l'exécutable backend embarqué (compilé par
// PyInstaller, voir .github/workflows/build-windows-desktop.yml), attendre
// qu'il réponde, puis ouvrir une fenêtre qui charge son interface — le
// backend sert aussi le frontend statique (voir CRIMTRACK_FRONTEND_DIR côté
// backend), donc tout tourne sur une seule origine http://127.0.0.1:8000.
//
// Les données (base SQLite, pièces jointes, secret JWT) vivent dans le
// dossier de données utilisateur Windows (%APPDATA%\CrimTrack), jamais
// dans le dossier d'installation — celui-ci est souvent en lecture seule
// et de toute façon écrasé à chaque mise à jour.

const { app, BrowserWindow, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const crypto = require("crypto");
const { spawn } = require("child_process");

const PORT = 8000;
const HEALTH_URL = `http://127.0.0.1:${PORT}/health`;

let backendProcess = null;
let mainWindow = null;

function backendExecutablePath() {
  // En build packagé : resources/backend/crimtrack-backend.exe
  // En dev (npm start sans build) : on retombe sur `python run_desktop.py`
  // dans ../backend, pour pouvoir itérer sans repasser par PyInstaller à
  // chaque changement.
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend", "crimtrack-backend.exe");
  }
  return null; // signal : mode dev, on lance via python
}

function frontendDirPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "frontend");
  }
  return path.join(__dirname, "..", "..", "frontend");
}

function ensureUserDataLayout() {
  const base = app.getPath("userData"); // %APPDATA%\CrimTrack sous Windows
  const dataDir = path.join(base, "data");
  const storageDir = path.join(base, "storage");
  const secretPath = path.join(base, "jwt.secret");

  fs.mkdirSync(dataDir, { recursive: true });
  fs.mkdirSync(storageDir, { recursive: true });

  if (!fs.existsSync(secretPath)) {
    // Secret JWT généré une seule fois, persistant entre les lancements —
    // sinon toute session serait invalidée à chaque redémarrage de l'app.
    fs.writeFileSync(secretPath, crypto.randomBytes(32).toString("hex"), { mode: 0o600 });
  }
  const jwtSecret = fs.readFileSync(secretPath, "utf8").trim();

  return {
    databaseUrl: `sqlite:///${path.join(dataDir, "crimtrack.db").replace(/\\/g, "/")}`,
    storageDir,
    jwtSecret,
  };
}

function waitForBackend(retriesLeft = 40) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = require("http").get(HEALTH_URL, (res) => {
        res.resume();
        resolve();
      });
      req.on("error", () => {
        if (retriesLeft <= 0) return reject(new Error("Le service backend n'a pas démarré à temps."));
        setTimeout(() => waitForBackend(retriesLeft - 1).then(resolve, reject), 300);
      });
    };
    attempt();
  });
}

function startBackend() {
  const { databaseUrl, storageDir, jwtSecret } = ensureUserDataLayout();
  const env = {
    ...process.env,
    DATABASE_URL: databaseUrl,
    STORAGE_DIR: storageDir,
    JWT_SECRET_KEY: jwtSecret,
    CRIMTRACK_FRONTEND_DIR: frontendDirPath(),
    CRIMTRACK_PORT: String(PORT),
  };

  const exePath = backendExecutablePath();
  if (exePath) {
    backendProcess = spawn(exePath, [], { env, windowsHide: true });
  } else {
    // Mode développement (npm start) : nécessite un venv Python configuré
    // dans ../backend avec les dépendances installées (voir README).
    const backendDir = path.join(__dirname, "..", "..", "backend");
    backendProcess = spawn("python", ["run_desktop.py"], { cwd: backendDir, env, windowsHide: true });
  }

  backendProcess.stdout?.on("data", (d) => process.stdout.write(`[backend] ${d}`));
  backendProcess.stderr?.on("data", (d) => process.stderr.write(`[backend] ${d}`));
  backendProcess.on("exit", (code) => {
    if (code !== 0 && code !== null) {
      dialog.showErrorBox(
        "CrimTrack — service arrêté",
        `Le service backend s'est arrêté de façon inattendue (code ${code}). ` +
          "Redémarrez l'application. Si le problème persiste, consultez les journaux."
      );
    }
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    backgroundColor: "#10141a", // cf. frontend/style.css --ink, évite un flash blanc au chargement
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.loadURL(`http://127.0.0.1:${PORT}/`);
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForBackend();
  } catch (err) {
    dialog.showErrorBox("CrimTrack — démarrage impossible", err.message);
    app.quit();
    return;
  }
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (backendProcess) backendProcess.kill();
});
