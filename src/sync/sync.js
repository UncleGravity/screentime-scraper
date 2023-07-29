const sqlite3 = require('sqlite3').verbose();
const fetch = require('cross-fetch');
const path = require('path');
const electron = require('electron');
const { formatISO, addSeconds, addHours } = require('date-fns');
const { AWClient } = require('aw-client');
global.AbortController = require('abort-controller');

// const API_ENDPOINT = "http://localhost:4564/test";
let last_to_time = null;

function get_utc_offset() {
  const now = new Date();
  const tzString = now.toString().split(' ')[5];
  const offsetMinutes = parseInt(tzString.substr(3, 2));
  const offsetHours = parseInt(tzString.substr(1, 2));
  return offsetHours + offsetMinutes / 60;
}

function unix_to_iso_format(unix_time, gmt_offset = 0) {
  const dt = new Date(unix_time * 1000);
  return formatISO(addHours(dt, gmt_offset));
}

async function read_web_events_from_disk(from_time, to_time) {
  const aw_client = new AWClient("browser-usage-fetcher");
  const browser_watcher_bucket_id = "aw-watcher-web-chrome";
  return aw_client.getEvents(browser_watcher_bucket_id, { limit: -1, start: from_time, end: to_time });
}

async function fetch_web_events(from_time, to_time) {
  const data = await read_web_events_from_disk(from_time, to_time);
  return data.map(entry => ({
    'time_start': formatISO(entry.timestamp),
    'time_end': formatISO(addSeconds(entry.timestamp, entry.duration)),
    // 'duration': entry.duration,
    'url': entry.data.url,
    // 'audible': entry.data.audible,
  }));
}

async function read_window_events_from_disk(from_time, to_time) {
  const aw_client = new AWClient("window-usage-fetcher");
  const window_watcher_bucket_id = `aw-watcher-window_${(await aw_client.getInfo()).hostname}`;
  return aw_client.getEvents(window_watcher_bucket_id, { limit: -1, start: from_time, end: to_time });
}

async function fetch_window_events(from_time, to_time) {
  const data = await read_window_events_from_disk(from_time, to_time);
  return data.map(entry => ({
    'time_start': formatISO(entry.timestamp),
    'time_end': formatISO(addSeconds(entry.timestamp, entry.duration)),
    // 'duration': entry.duration,
    'app_name': entry.data.app,
  }));
}

async function read_vscode_events_from_disk(from_time, to_time) {
  const aw_client = new AWClient("vscode-usage-fetcher");
  const vscode_watcher_bucket_id = `aw-watcher-vscode_${(await aw_client.getInfo()).hostname}`;
  return aw_client.getEvents(vscode_watcher_bucket_id, { limit: -1, start: from_time, end: to_time });
}

async function fetch_vscode_events(from_time, to_time) {
  const data = await read_vscode_events_from_disk(from_time, to_time);
  return data.map(entry => ({
    'time_start': formatISO(entry.timestamp),
    'time_end': formatISO(addSeconds(entry.timestamp, entry.duration)),
    // 'duration': entry.duration,
    'language': entry.data.language,
    'project': entry.data.project,
    'file': entry.data.file,
  }));
}

function read_screentime_from_disk(from_time) {
  // const home_folder = os.homedir();
  // const dbPath = `${home_folder}/Library/Application Support/Knowledge/knowledgeC.db`;
  const dbPath = path.join((electron.app || electron.remote.app).getPath('home'), 'Library/Application Support/Knowledge/knowledgeC.db');
  // const dbPath = path.join(__dirname, 'knowledgeC.db')
  const query = `
    SELECT
      ZOBJECT.ZVALUESTRING AS 'App_Name',
      ZOBJECT.ZSTRUCTUREDMETADATA AS 'ZSMD',
      ZSOURCE.ZDEVICEID AS 'Device_ID',
      ZSYNCPEER.ZMODEL AS 'Device_Name',
      (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS 'Usage_in_Seconds',
      ZOBJECT.ZSTARTDATE + 978307200 AS 'Usage_Start_Time',
      ZOBJECT.ZENDDATE + 978307200 AS 'Usage_End_Time',
      ZOBJECT.ZSECONDSFROMGMT/3600 AS "GMT OFFSET"
    FROM ZOBJECT
      LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
      LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
      LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
    WHERE
      ZSTREAMNAME IS '/app/usage' AND
      --       ZOBJECT. ZSTARTDATE >= strftime('%s', datetime('now', '-24 hours')) - 978307200 AND
      ZOBJECT.ZSTARTDATE >= strftime('%s', '${formatISO(from_time)}') - 978307200 AND
      ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
    ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;
    `;

  return new Promise((resolve, reject) => {
    console.log(`Reading screentime data from ${dbPath}`);
    const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        reject(err);
      }
    });

    db.all(query, [], (err, rows) => {
      if (err) {
        reject(err);
      }
      // let noname = 0
      // let name = 0
      // let deviceIdList = []
      // for (let i = 0; i < rows.length; i++) {
      //   if (rows[i]['Model_Name'] != null) {
      //     // console.log(rows[i])
      //     name += 1
      //     if (!deviceIdList.includes(rows[i]['Model_Name'])) {
      //       deviceIdList.push(rows[i]['Model_Name'])
      //     }
      //   } else {
      //     noname += 1
      //     continue
      //   }
      // }
      // console.log(rows)
      // console.log(`name: ${name}, noname: ${noname}`);
      // console.log(deviceIdList);
      resolve(rows);
    });

    db.close((err) => {
      if (err) {
        reject(err);
      }
    });
  });
}

async function fetch_screentime_events(from_time) {
  const data = await read_screentime_from_disk(from_time);
  return data.map(record => ({
    'time_start': unix_to_iso_format(record['Usage_Start_Time'], 0),
    'time_end': unix_to_iso_format(record['Usage_End_Time'], 0),
    'app_name': record['App_Name'],
    'device_id': record['Device_ID'],
    'device_name': record['Device_Name'],
    'gmt_offset': record['GMT OFFSET'],
  }));
}

function read_screentime_web_usage_from_disk(from_time) {
  // const home_folder = os.homedir();
  // const dbPath = `${home_folder}/Library/Application Support/Knowledge/knowledgeC.db`;
  const dbPath = path.join((electron.app || electron.remote.app).getPath('home'), 'Library/Application Support/Knowledge/knowledgeC.db');
  const query = `
  SELECT
    ZOBJECT.ZVALUESTRING AS 'App_Name',
    ZOBJECT.ZSTRUCTUREDMETADATA AS 'ZSMD',
    ZSOURCE.ZDEVICEID AS 'Device_ID',
    ZSYNCPEER.ZMODEL AS 'Model_Name',
    (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS 'Usage_in_Seconds',
    ZOBJECT.ZSTARTDATE + 978307200 AS 'Usage_Start_Time',
    ZOBJECT.ZENDDATE + 978307200 AS 'Usage_End_Time',
    ZOBJECT.ZSECONDSFROMGMT/3600 AS "GMT OFFSET",
    ZSTRUCTUREDMETADATA.Z_DKDIGITALHEALTHMETADATAKEY__WEBPAGEURL AS 'URL'
  FROM ZOBJECT
    LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
    LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
    LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
  WHERE
    ZSTREAMNAME IS '/app/webUsage' AND
    ZOBJECT.ZSTARTDATE >= strftime('%s', '${formatISO(from_time)}') - 978307200 AND
    ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
  ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;
  `;

  return new Promise((resolve, reject) => {
    console.log(`Reading screentime web usage from ${dbPath}`);
    const db = new sqlite3.Database(dbPath, sqlite3.OPEN_READONLY, (err) => {
      if (err) {
        reject(err);
      }
    });

    db.all(query, [], (err, rows) => {
      if (err) {
        reject(err);
      }
      // console.log(rows);
      resolve(rows);
    });

    db.close((err) => {
      if (err) {
        reject(err);
      }
    });
  });
}

async function fetch_screentime_web_events(from_time) {
  const data = await read_screentime_web_usage_from_disk(from_time);
  return data.map(record => ({
    'time_start': unix_to_iso_format(record['Usage_Start_Time'], 0),
    'time_end': unix_to_iso_format(record['Usage_End_Time'], 0),
    'app_name': record['App_Name'],
    'url': record['URL'],
    'device_id': record['Device_ID'],
    'device_name': record['Model_Name'],
    'gmt_offset': record['GMT OFFSET'],
  }));
}

async function sync(api_endpoint) {

  const now = new Date();
  const days = 2;
  const from_time = last_to_time || addSeconds(now, -days * 24 * 60 * 60);
  const to_time = now;
  // last_to_time = to_time;

  console.log(`Fetching data from ${formatISO(from_time)} to ${formatISO(to_time)}...`);
  const screentime_data = await fetch_screentime_events(from_time);
  const screentime_web_data = await fetch_screentime_web_events(from_time);
  const window_data = await fetch_window_events(from_time, to_time);
  const web_data = await fetch_web_events(from_time, to_time);
  const vscode_data = await fetch_vscode_events(from_time, to_time);

  const combined_data = {
    'screenTimeData': screentime_data,
    'screenTimeWebData': screentime_web_data,
    'windowEventData': window_data,
    'webEventData': web_data,
    'vscodeEventData': vscode_data,
    'host_gmt_offset': get_utc_offset(),
  };

  // await save_ios_events_to_aw(from_time);

  // console.log(combined_data)
  // console.log(screentime_data)
  // console.log(screentime_web_data)
  // console.log(window_data)
  // console.log(web_data)
  // console.log(vscode_data)

  try {
    const response = await fetch(api_endpoint, {
      method: 'POST',
      body: JSON.stringify(combined_data),
      headers: { 'Content-Type': 'application/json' },
      timeout: 20000 // timeout after 20 seconds
    });

    if (response.ok) {
      console.log(`${formatISO(now)} | Server responded with: ${await response.text()}`);
      return true;
    } else {
      console.log(`Error sending data to the server, status code: ${response.status}`);
      return false;
    }
  } catch (error) {
    if (error instanceof TypeError) {
      console.log('Request timed out'); 
    } else {
      console.log(`Error connecting to server: ${error}`);
    }
    return false; 
  }
}

// send request to "ping" endpoing, if it returns "pong", then return true
async function ping() {
  try {
    const response = await fetch(`${api_endpoint}/ping`);
    if (response.ok) {
      const text = await response.text();
      return text === 'pong';
    } else {
      return false;
    }
  } catch (error) {
    return false;
  }
}

async function test() {
  // fake waiting for 5 seconds
  await new Promise(resolve => setTimeout(resolve, 1000));
  console.log('test');
}

module.exports = { sync, ping, test };

// setInterval(sync, 60 * 5 * 1000);
// sync().catch(error => console.log(error));