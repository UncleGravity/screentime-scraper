import os
import sqlite3
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from os.path import expanduser
import seaborn as sns

# Graph style and appearance
sns.set(style="whitegrid")

def format_value(value, default="N/A"):
    """Helper function to handle None values."""
    return default if value is None else value

home_folder = expanduser("~")
path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
conn = sqlite3.connect(path)
cur = conn.cursor()

# Define the query with the time constraint to select data from the past 24 hours only
query = """
SELECT
  ZOBJECT.ZVALUESTRING AS 'App_Name',
  ZSYNCPEER.ZMODEL AS 'Device_Name',
  ZOBJECT.ZSTARTDATE AS 'Usage_Start_Time',
  ZOBJECT.ZENDDATE AS 'Usage_End_Time'
FROM ZOBJECT
  LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
  LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
  LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
WHERE
  Device_name IS 'iPhone13,3' AND
  ZSTREAMNAME IS '/app/usage' AND
  ZOBJECT.ZSTARTDATE >= strftime('%s', datetime('now', '-24 hours')) - 978307200 AND
  ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200 AND
  (ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) > 15
ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;

"""

app_names_query = """
SELECT DISTINCT
  ZOBJECT.ZVALUESTRING AS 'App_Name'
FROM ZOBJECT
  LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
WHERE
  ZSTREAMNAME IS '/app/usage'
"""

# Execute the query
cur.execute(query)
records = cur.fetchall()
cur.execute(app_names_query)
app_names = cur.fetchall()

# Create a dictionary to store app name as key and starting y-axis position value as value
app_name_positions = {app[0]: i for i, app in enumerate(app_names)}

# Setup the graph
fig, ax = plt.subplots(figsize=(12, 6))



# Create a dictionary to store app names with their respective usage time
app_usage = {}

# Iterate over records to sum up the usage time and store it in the dictionary
for record in records:
    app_name, device_id, start_time, end_time = record
    app_name = format_value(app_name)
    start_time = datetime(2001, 1, 1) + timedelta(seconds=start_time)
    end_time = datetime(2001, 1, 1) + timedelta(seconds=end_time)

    # Calculate duration
    duration = end_time - start_time
    if duration.total_seconds() > 15:
        if app_name not in app_usage:
            app_usage[app_name] = duration
        else:
            app_usage[app_name] += duration
          
# Filter apps with a total usage time of more than 15 seconds
filtered_app_names = [app for app, usage in app_usage.items() if usage.total_seconds() > 30]

# Update the dictionary for plotting
app_name_positions = {app: i for i, app in enumerate(filtered_app_names)}

# Plotting segments
for record in records:
    app_name, device_id, start_time, end_time = record
    app_name = format_value(app_name)
    start_time = datetime(2001, 1, 1) + timedelta(seconds=start_time)
    end_time = datetime(2001, 1, 1) + timedelta(seconds=end_time)

    # Calculate duration and only plot if it's over 15 seconds and the app_name is in the filtered list
    duration = end_time - start_time
    if duration.total_seconds() > 15 and app_name in filtered_app_names:
        y_pos = app_name_positions[app_name]
        ax.hlines(y=y_pos, xmin=start_time, xmax=end_time, linewidth=10)

# Setting labels, ticks, and formatting
yticks = list(app_name_positions.values())
yticklabels = list(app_name_positions.keys())
ax.set_yticks(yticks)
ax.set_yticklabels(yticklabels)
ax.set_ylim(-1, len(app_name_positions))
ax.xaxis.set_minor_locator(mdates.HourLocator())
ax.xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M'))
ax.xaxis.set_major_locator(mdates.HourLocator(interval=6))
ax.xaxis.set_major_formatter(mdates.DateFormatter('\n%b %d, %Y\n%H:%M'))
plt.xlabel("App usage time")
plt.ylabel("App names")
plt.title("App Usage in the last 24 hours")


# Show the graph
plt.show()

# Closing the connection
conn.close()
