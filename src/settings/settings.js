const { ipcRenderer } = require('electron');

window.onload = function () {
  // request api values from main process
  ipcRenderer.send('request-api-values');
}

ipcRenderer.on('response-api-values', (event, { api1 }) => {
  if (api1 !== null) {
    document.getElementById('api1').value = api1;
  }
});

document.getElementById('settings-form').addEventListener('submit', function (e) {
  e.preventDefault();

  const api1 = document.getElementById('api1').value;

  ipcRenderer.send('update-api-values', { api1 });

  window.close();
});