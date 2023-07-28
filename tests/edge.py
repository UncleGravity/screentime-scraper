import os
import sqlite3
from datetime import datetime
from os.path import expanduser

def format_value(value, default="BENGKUI"):
    """Helper function to handle None values."""
    return default if value is None else value

def format_seconds(seconds):
    """Convert seconds to a formatted string 'hrs:min:sec'."""
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h:{int(minutes):02d}m:{int(seconds):02d}s"

# Connect to the 'knowledgeC.db' SQLite database
home_folder = expanduser("~")
path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
conn = sqlite3.connect(path)

cur = conn.cursor()

# Define the query with the time constraint and grouping to get cumulative usage for each app and device
query = """
SELECT
  COALESCE(ZOBJECT.ZVALUESTRING, 'None') AS 'App_Name',
  ZSYNCPEER.ZMODEL AS 'Device_Name',
  SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) AS 'Total_Usage_in_Seconds'
FROM ZOBJECT
  LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
  LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
  LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
WHERE
  ZSTREAMNAME IS '/app/usage' AND
  ZOBJECT.ZSTARTDATE >= strftime('%s', datetime('now', '-24 hours')) - 978307200 AND
  ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
GROUP BY COALESCE(ZOBJECT.ZVALUESTRING, 'None'), ZSYNCPEER.ZMODEL
ORDER BY ZSYNCPEER.ZMODEL, SUM(ZOBJECT.ZENDDATE - ZOBJECT.ZSTARTDATE) DESC;
"""

# Execute the query
cur.execute(query)

# Fetch all records and print them in a tabular format
records = cur.fetchall()

print("Cumulative App Usage in the past 24 hours:\n")
print("{:<30} {:<20} {}".format("App Name", "Device Name", "Total Usage (hrs:min:sec)"))
for record in records:
    app_name, device_name, total_usage_seconds = record
    app_name = format_value(app_name)
    device_name = format_value(device_name)
    total_usage_formatted = format_value(total_usage_seconds, None)

    if total_usage_formatted is not None:
        total_usage_formatted = format_seconds(total_usage_seconds)

    print("{:<30} {:<20} {}".format(app_name, device_name, total_usage_formatted))

# Closing the connection
conn.close()