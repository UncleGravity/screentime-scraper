import os
import sqlite3
import json
import requests
from os.path import expanduser
import time
from datetime import datetime, timedelta, timezone
from aw_client import ActivityWatchClient
from aw_core.models import Event

# What this does
# --------------
# Fetch "Screen Time" from KnowledgeC.db (both macOS and iOS app usage)
# Fetch mac usage from aw-watcher-window (overlaps with KnowledgeC.db)
# Fetch browser usage from aw-watcher-web
# Fetch vscode usage from aw-watcher-vscode
# Uploads all data to personal server (not activitywatch related)
# Upload Screen Time data to aw-server
# TODO - Automate this script to run every 5 minutes
# TODO - (OPTIONAL) Add macOS toolbar with status
# TODO - Add support for safari web usage on iOS
# TODO - Figure out how to read the hostname from the mac, currently null

# API_ENDPOINT = "http://localhost:4564/screentime"
API_ENDPOINT = "http://localhost:4564/test"

# Utils

# Prints the UTC offset in seconds
def get_utc_offset():
    # Get the current local time and check if daylight saving is in effect
    is_dst = time.localtime().tm_isdst
    # Get the time difference in seconds
    utc_offset = -time.timezone if is_dst else -time.altzone
    return utc_offset

def format_value(value, default="N/A"):
    """Helper function to handle None values."""
    return default if value is None else value

def convert_to_iso_format(date_string, gmt_offset):
    dt = datetime.strptime(date_string, '%Y-%m-%d %H:%M:%S')
    dt = dt + timedelta(hours=gmt_offset)  # Apply the gmt_offset to the date-time
    return dt.isoformat()

def unix_to_iso_format(unix_time, gmt_offset=0):
    dt = datetime.utcfromtimestamp(unix_time)
    dt = dt + timedelta(hours=int(gmt_offset))  # Apply the gmt_offset to the date-time
    offset_hours = int(gmt_offset)
    offset_str = f"{offset_hours:+03}:00"
    iso_format_with_timezone = f"{dt.isoformat()}{offset_str}"
    return iso_format_with_timezone

################################################
# Fetch data from aw-watcher-web
def read_web_events_from_disk(from_time, to_time):
    aw_client = ActivityWatchClient("browser-usage-fetcher")

    # browser_watcher_bucket_id = f"aw-watcher-web_{aw_client.client_hostname}"
    browser_watcher_bucket_id = "aw-watcher-web-chrome"
    return aw_client.get_events(bucket_id=browser_watcher_bucket_id, limit=-1, start=from_time, end=to_time)

def fetch_web_events(from_time, to_time):
    data = read_web_events_from_disk(from_time, to_time)
    web_event_data = []

    for entry in data:
        event_entry = {
            'time_start': entry['timestamp'].isoformat(),
            'time_end': (entry['timestamp'] + entry['duration']).isoformat(),
            'duration': entry['duration'].total_seconds(),
            'url': entry['data']['url'],
            'audible': entry['data']['audible'],
        }
        web_event_data.append(event_entry)

    return web_event_data

################################################
# Fetch data from aw-watcher-window
def read_window_events_from_disk(from_time, to_time):
    aw_client = ActivityWatchClient("window-usage-fetcher")

    window_watcher_bucket_id = f"aw-watcher-window_{aw_client.client_hostname}"
    return aw_client.get_events(bucket_id=window_watcher_bucket_id, limit=-1, start=from_time, end=to_time)

def fetch_window_events(from_time, to_time):
    data = read_window_events_from_disk(from_time, to_time)
    window_event_data = []

    for entry in data:
        event_entry = {
            'time_start': entry['timestamp'].isoformat(),
            'time_end': (entry['timestamp'] + entry['duration']).isoformat(),
            'duration': entry['duration'].total_seconds(),
            'app_name': entry['data']['app'],
            # 'title': entry['data']['title'],
            # 'url': entry['data']['url'],
        }
        window_event_data.append(event_entry)

    return window_event_data

################################################
# Fetch data from aw-watcher-vscode
def read_vscode_events_from_disk(from_time, to_time):
    aw_client = ActivityWatchClient("vscode-usage-fetcher")

    vscode_watcher_bucket_id = f"aw-watcher-vscode_{aw_client.client_hostname}"
    return aw_client.get_events(bucket_id=vscode_watcher_bucket_id, limit=-1, start=from_time, end=to_time) 

def fetch_vscode_events(from_time, to_time):
    data = read_vscode_events_from_disk(from_time, to_time)
    vscode_event_data = []

    for entry in data:
        event_entry = {
            'time_start': entry['timestamp'].isoformat(),
            'time_end': (entry['timestamp'] + entry['duration']).isoformat(),
            'duration': entry['duration'].total_seconds(),
            'language': entry['data']['language'],
            'project': entry['data']['project'],
            'file': entry['data']['file'],
        }
        vscode_event_data.append(event_entry)

    return vscode_event_data

################################################
# Fetch data from KnowledgeC.db
def read_screentime_web_usage_from_disk(from_time):
    home_folder = expanduser("~")
    path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
    query = f"""
    SELECT
      ZOBJECT.ZVALUESTRING AS 'App_Name',
      ZOBJECT.ZSTRUCTUREDMETADATA AS 'ZSMD',
	  ZSOURCE.ZDEVICEID AS 'Device_ID',
      ZSYNCPEER.ZMODEL AS 'Model_Name',
      (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS 'Usage_in_Seconds',
      ZOBJECT.ZSTARTDATE + 978307200 AS 'Usage_Start_Time',
      ZOBJECT.ZENDDATE + 978307200 AS 'Usage_End_Time',
      ZOBJECT.ZSECONDSFROMGMT/3600 AS 'GMT OFFSET',
	  ZSTRUCTUREDMETADATA.Z_DKDIGITALHEALTHMETADATAKEY__WEBPAGEURL AS 'URL'
    FROM ZOBJECT
      LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
      LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
      LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
    WHERE
      ZSTREAMNAME IS '/app/webUsage' AND
--      ZOBJECT. ZSTARTDATE >= strftime('%s', datetime('now', '-24 hours')) - 978307200 AND
      ZOBJECT.ZSTARTDATE >= strftime('%s', '{from_time.strftime("%Y-%m-%d %H:%M:%S")}') - 978307200 AND
      ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
    ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;
    """
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute(query)
    records = c.fetchall()
    conn.close()

    return records

def read_screentime_from_disk(from_time):
    home_folder = expanduser("~")
    path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
    query = f"""
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
      ZOBJECT.ZSTARTDATE >= strftime('%s', '{from_time.strftime("%Y-%m-%d %H:%M:%S")}') - 978307200 AND
      ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
    ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;
    """

    with sqlite3.connect(path) as conn:
        cur = conn.cursor()
        cur.execute(query)
        records = cur.fetchall()

    return records

def print_screentime(records):
    print("App Usage in the past 24 hours:\n")
    print("{:<35} {:<5} {:<15} {:<10} {:<25} {:<25} {:<10}".format("App Name", "Device ID", "Device Name", "Usage (S)", "Usage Start Time", "Usage End Time", "gmt_offset"))
    for record in records:
        app_name, device_id, device_name, usage, start_time, end_time, gmt_offset = record
        app_name = app_name
        device_id = device_id
        device_name = format_value(device_name)
        usage = usage
        start_time = unix_to_iso_format(start_time, gmt_offset)
        end_time = unix_to_iso_format(end_time, gmt_offset)
        gmt_offset = gmt_offset

        if usage != "N/A":
            usage = "{:.0f}".format(usage)

        print("{:<35} {:<5} {:<15} {:<10} {:<25} {:<25} {:<5}".format(app_name, device_id, device_name, usage, start_time, end_time, gmt_offset))

def save_ios_web_events_to_aw(from_time):
    data = read_screentime_web_usage_from_disk(from_time)
    events = []

    for record in data:
        app_name, zsmd, device_id, model_name, usage, start_time, end_time, gmt_offset, url = record

        print(f"Saving {app_name} to ActivityWatch")

        entry = Event(
            timestamp=unix_to_iso_format(start_time, 0),
            duration=usage,
            data={
            "url": url,
            "title": "N/A",
            "audible": False,
            "incognito": False,
            },
        )
        events.append(entry)

    hostname = "CRISPR" # TODO: Hardcoded for now
    bucket = f"aw-screentime-import-web_{device_id}"

    aw = ActivityWatchClient(client_name="aw-import-screentime")
    aw.client_hostname = hostname
    aw.create_bucket(bucket, "web.tab.current")
    aw.insert_events(bucket, events)

def save_ios_events_to_aw(from_time):
    data = read_screentime_from_disk(from_time)
    events = []

    for record in data:
        app_name, zsmd, device_id, model_name, usage, start_time, end_time, gmt_offset = record

        # Only send the "iPhone" substring is found in the model name (note that it could be null)
        if model_name is not None and "iPhone" in model_name:
            model_name = "iPhone"

        print(f"Saving {app_name} to ActivityWatch")

        entry = Event(
            timestamp=unix_to_iso_format(start_time, 0),
            duration=usage,
            data={"app": app_name, "title": "N/A"},
        )
        events.append(entry)

    hostname = "CRISPR" # TODO: Hardcoded for now
    bucket = f"aw-screentime-import_{device_id}"

    aw = ActivityWatchClient(client_name="aw-import-screentime")
    aw.client_hostname = hostname
    aw.create_bucket(bucket, "currentwindow")
    aw.insert_events(bucket, events)

def fetch_screentime_web_events(from_time):
    data = read_screentime_web_usage_from_disk(from_time)
    screen_time_web_data = []

    for record in data:
        app_name, zsmd, device_id, model_name, usage, start_time, end_time, gmt_offset, url = record

        screen_time_entry = {
            'time_start': unix_to_iso_format(start_time, 0),
            'time_end': unix_to_iso_format(end_time, 0),
            'app_name': app_name,
            'url': url,
            'device_id': device_id,
            'device_name': model_name,
            'gmt_offset': gmt_offset,
        }
        screen_time_web_data.append(screen_time_entry)

    return screen_time_web_data

def fetch_screentime_events(from_time):
    data = read_screentime_from_disk(from_time)
    screen_time_data = []

    for record in data:
        app_name, zsmd, device_id, model_name, usage, start_time, end_time, gmt_offset = record
        screen_time_entry = {
            'time_start': unix_to_iso_format(start_time, 0),
            'time_end': unix_to_iso_format(end_time, 0),
            'app_name': app_name,
            'device_id': device_id,
            'device_name': model_name,
            'gmt_offset': gmt_offset,
        }
        screen_time_data.append(screen_time_entry)

    return screen_time_data


if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    from_time = now - timedelta(days=1)
    to_time = now
    
    ###########################
    # Save to ActivityWatch
    # save_ios_events_to_aw(from_time)
    # save_ios_web_events_to_aw(from_time)
    # exit()

    ###########################
    # Save to API

    # Fetch data
    screentime_data = fetch_screentime_events(from_time)
    screentime_web_data = fetch_screentime_web_events(from_time)
    window_data = fetch_window_events(from_time, to_time)
    web_data = fetch_web_events(from_time, to_time)
    vscode_data = fetch_vscode_events(from_time, to_time)

    # Combine data into a single payload
    combined_data = {
        'screenTimeData': screentime_data,
        'screenTimeWebData': screentime_web_data,
        'windowEventData': window_data,
        'webEventData': web_data,
        'vscodeEventData': vscode_data,
        'host_gmt_offset': get_utc_offset() / 3600
    }

    # print(web_data)
    # exit()
    # Upload data
    try:
        response = requests.post(API_ENDPOINT, json=combined_data)
        print(json.dumps(combined_data, indent=4))
        if response.status_code == 200:
            print('Data successfully sent to the server')
        else:
            print(f'Error sending data to the server, status code: {response.status_code}')
    except requests.exceptions.RequestException as e:
        print(f'Error connecting to the server: {e}')