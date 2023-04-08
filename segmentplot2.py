import os
import sqlite3
import matplotlib.pyplot as plt
import matplotlib.dates as md
from datetime import datetime, timedelta
from os.path import expanduser
from collections import defaultdict

home_folder = expanduser("~")
path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")

conn = sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

query = """
SELECT
  ZOBJECT.ZVALUESTRING AS 'App_Name',
  ZOBJECT.ZSTRUCTUREDMETADATA AS 'ZSMD',
  DateTime(ZOBJECT.ZSTARTDATE + 978307200, 'UNIXEPOCH', 'localtime') AS 'Usage_Start_Time [timestamp]',
  DateTime(ZOBJECT.ZENDDATE + 978307200, 'UNIXEPOCH', 'localtime') AS 'Usage_End_Time [timestamp]'
FROM ZOBJECT
  LEFT JOIN ZSTRUCTUREDMETADATA ON ZSTRUCTUREDMETADATA.Z_PK = ZOBJECT.ZSTRUCTUREDMETADATA
  LEFT JOIN ZSOURCE ON ZOBJECT.ZSOURCE = ZSOURCE.Z_PK
  LEFT JOIN ZSYNCPEER ON ZSOURCE.ZDEVICEID = ZSYNCPEER.ZDEVICEID
WHERE
  ZSTREAMNAME IS '/app/usage' AND
  ZOBJECT.ZSTARTDATE >= strftime('%s', datetime('now', '-24 hours')) - 978307200 AND
  ZOBJECT.ZENDDATE <= strftime('%s', datetime('now')) - 978307200
ORDER BY ZSYNCPEER.ZDEVICEID, ZOBJECT.ZSTARTDATE;
"""

cur = conn.cursor()
cur.execute(query)
records = cur.fetchall()

app_usage_data = []
app_cumulative_times = defaultdict(int)

for record in records:
    app_name, zsmd, start_time, end_time = record

    if zsmd != 3:
        continue

    app_cumulative_times[app_name] += (end_time - start_time).total_seconds()
    app_usage_data.append((app_name, start_time, end_time - start_time))

app_names = sorted(set(app_name for app_name, _, _ in app_usage_data), key=lambda x: app_cumulative_times[x], reverse=True)

fig, ax = plt.subplots()

for app_index, app_name in enumerate(app_names):
    for name, start, duration in app_usage_data:
        if name == app_name:
            ax.barh(app_index, duration.total_seconds() / 3600, left=start, height=0.8, edgecolor='black')

ax.set_yticks(range(len(app_names)))
ax.set_yticklabels(app_names)

ax.xaxis_date()
xfmt = md.DateFormatter('%d-%m-%Y %H:%M:%S')
ax.xaxis.set_major_formatter(xfmt)

plt.xlabel('Time (hours)')
plt.xticks(rotation=25)
plt.title('App Usage Timeline (past 24 hours)')

plt.tight_layout()
plt.show()

conn.close()
