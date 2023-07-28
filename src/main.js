const { app, ipcMain, powerMonitor, Notification, Tray, Menu, BrowserWindow, nativeImage } = require('electron');
const { ping, sync, test } = require('./sync/sync.js');
const path = require('path');
const fs = require('fs');
const log = require('electron-log'); console.log = log.log;
const Store = require('electron-store'); const store = new Store();
const { askForFullDiskAccess } = require('node-mac-permissions')

let tray, syncInterval, settingsWindow;
let isQuiting = false;

////////////////////////////////////////////////////////
// Functions
////////////////////////////////////////////////////////

async function syncFunction() {

  console.log('Running syncFunction')
  const syncEnabled = store.get('syncEnabled') || false;
  if (!syncEnabled) { console.log("Sync Disabled. Not running."); return; }

  const apiEndpoint = store.get('api1') || '';

  try {
    await test(); result = false;
    // let result = await sync(apiEndpoint);

    if (result) {
      store.set('lastSync', new Date());  // save lastSync to local storage
      console.log('Sync successful');
      // Reset sync interval (in case we trigger sync manually)
      if (syncInterval) {
        console.log('Resetting sync interval');
        const syncFrequency = store.get('syncFrequency') || 1;
        clearInterval(syncInterval);
        syncInterval = setInterval(syncFunction, syncFrequency * 60 * 1000);
      }
    } else {
      console.log('Sync failed');
      new Notification({
        title: "ScreenTime Scraper",
        body: "Sync Failed"
      }).show()
    }
  } catch (e) {
    new Notification({
      title: "ScreenTime Scraper",
      body: "Sync Error: " + e
    }).show()
  }

  updateMenu();

}

function updateMenu() {
  const syncFrequency = store.get('syncFrequency') || 1;
  const syncEnabled = store.get('syncEnabled') || false;
  const lastSync = store.get('lastSync');
  const apiEndpoint = store.get('api1') || '';

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Settings', click: createSettingsWindow },
    { label: apiEndpoint != '' ? 'Sync Now' : 'Sync Now (no endpoint)', click: syncFunction, enabled: (apiEndpoint != '') },
    { label: `Last Sync: ${lastSync ? lastSync : 'Never'}`, enabled: false },
    { type: 'separator' },
    {
      label: 'Frequency (minutes)', submenu: [
        { label: '1 minute', type: 'radio', checked: syncFrequency === 1, click: () => updateSyncFrequency(1) },
        { label: '1 hour', type: 'radio', checked: syncFrequency === 60, click: () => updateSyncFrequency(60) },
        { label: '12 hours', type: 'radio', checked: syncFrequency === 12 * 60, click: () => updateSyncFrequency(12 * 60) },
        { label: '24 hours', type: 'radio', checked: syncFrequency === 24 * 60, click: () => updateSyncFrequency(24 * 60) },
        // add or remove options as needed
      ]
    },
    { label: 'Enable Auto Sync', type: 'checkbox', checked: syncEnabled, click: (row) => { setAutoSyncState(row.checked); updateMenu(); } },
    { label: syncEnabled ? `Auto Sync frequency is set to every ${syncFrequency} minutes.` : 'Auto Sync is disabled.', enabled: false },
    { type: 'separator' },
    { label: 'Exit', click: () => { isQuiting = true; app.quit(); } }
  ])

  tray.setToolTip('This is my application.')
  tray.setContextMenu(contextMenu)
}

function createSettingsWindow() {

  if (settingsWindow) {
    settingsWindow.show();
    return;
  }

  settingsWindow = new BrowserWindow({
    width: 500,
    height: 165,
    show: false,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    }
  });

  settingsWindow.loadFile(path.join(__dirname, 'settings/settings.html'));

  settingsWindow.on('ready-to-show', () => {
    settingsWindow.show();
  })

  // when the window is closed, just hide it 
  settingsWindow.on('close', (event) => {
    if (!isQuiting) {
      event.preventDefault();
      settingsWindow.hide();
    }
    return false;
  });
}

async function updateSyncFrequency(minutes) {
  // Check if the sync interval has passed since the last sync (with the new frequency)
  const lastSync = store.get('lastSync') || new Date();
  const syncEnabled = store.get('syncEnabled') || false;
  const now = new Date();
  const timeSinceLastSync = (now - lastSync) / 1000 / 60; // minutes
  if (timeSinceLastSync > minutes && syncEnabled) {
    await syncFunction();
  }

  // Update the sync frequency
  store.set('syncFrequency', minutes);  // save frequency to local storage
  clearInterval(syncInterval);
  if (syncEnabled) {
    syncInterval = setInterval(syncFunction, minutes * 60 * 1000);
  }
  updateMenu();
}

async function setAutoSyncState(state) {

  if (store.get('syncEnabled') == state) {
    console.log('Sync state is already set to', state);
    return;
  }

  if (state && !syncInterval) {
    console.log('Creating new sync interval');
    const syncFrequency = store.get('syncFrequency') || 1;
    syncInterval = setInterval(syncFunction, syncFrequency * 60 * 1000);
  } else if (!state) {
    console.log('Clearing sync interval');
    clearInterval(syncInterval);
  }

  console.log('Setting sync state to', state);
  store.set('syncEnabled', state);

}

////////////////////////////////////////////////////////
// IPC
////////////////////////////////////////////////////////
ipcMain.on('update-api-values', (event, { api1 }) => {
  store.set('api1', api1);
  if (api1 == '') {
    setAutoSyncState(false);
  }
  updateMenu();
});

ipcMain.on('request-api-values', (event) => {
  const api1 = store.get('api1') || '';

  event.reply('response-api-values', { api1 });
});

////////////////////////////////////////////////////////
// Listeners
////////////////////////////////////////////////////////

app.on('before-quit', function () {
  isQuiting = true;
});

powerMonitor.on('resume', async () => {
  console.log('Restarting sync after sleep');
  syncFrequency = store.get('syncFrequency') || 1;
  await updateSyncFrequency(syncFrequency);
});

app.whenReady().then(async () => {
  if (app.dock) {
    app.dock.hide();
  }

  app.setLoginItemSettings({ openAtLogin: true, })

  const icon = nativeImage.createFromDataURL('data:image/png;base64,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')
  tray = new Tray(icon);

  // Show notification permission on first run
  new Notification();

  // Request access to Home directory
  const filePath = path.resolve(app.getPath('home'), 'Library/Application Support/Knowledge/knowledgeC.db');

  try {
    fs.accessSync(filePath, fs.constants.R_OK);
    console.log(`Access to ${filePath} granted!`)
    updateMenu();
    await initialize();

  } catch (err) {
    console.log(`No access to ${filePath}! Error: ${err}`);
    askForFullDiskAccess();
    // Apple will ask the app to restart after granting access so nothing else needs to be done here
  }

  // new Notification({
  //   title: "Title?",
  //   body: "SOMETHING HAPPENED"
  // }).show()

})

async function initialize() {
  // await syncFunction();
  syncFrequency = store.get('syncFrequency') || 1; // in minutes
  await updateSyncFrequency(syncFrequency);
}

// Notes:
// https://www.reddit.com/r/node/comments/v84pp4/has_anyone_got_sqlite3_and_electron_working_on/