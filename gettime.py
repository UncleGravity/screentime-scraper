import os
import sqlite3
from os.path import expanduser

def open_knowledgeC_db():
    home_folder = expanduser("~")
    path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
    conn = sqlite3.connect(path)
    return conn

def fetch_screen_time_data(conn):
    cursor = conn.cursor()
    query = """
    SELECT
        ZOBJECT.Z_PK AS object_id,
        ZOBJECT.Z_PK AS app_identifier,
        ZCONTEXTUALKEYPATH.ZDEVICEIDSTRING AS device_name,
        ZSTRUCTUREDMETADATA.Z_DKINTENSITYSERIESMETADATAKEY__SCREENONBYTIMERANGES__READINGS AS screen_time_readings
    FROM
        ZOBJECT
        JOIN ZSTRUCTUREDMETADATA ON ZOBJECT.ZSTRUCTUREDMETADATA = ZSTRUCTUREDMETADATA.Z_PK
        JOIN ZCONTEXTUALKEYPATH ON ZOBJECT.ZVALUEINTEGER = ZCONTEXTUALKEYPATH.ZDEVICEID
    WHERE
        ZOBJECT.Z_ENT = 25
        AND ZSTRUCTUREDMETADATA.Z_DKINTENSITYSERIESMETADATAKEY__SCREENONBYTIMERANGES__READINGS IS NOT NULL
    """
    cursor.execute(query)
    return cursor.fetchall()

def main():
    conn = open_knowledgeC_db()
    data = fetch_screen_time_data(conn)
    conn.close()

    print("Screen Time Data:")
    for row in data:
        app_identifier = row[1]
        device_name = row[2]
        screen_time_readings_hex = row[3]
        screen_time_readings = bytes.fromhex(screen_time_readings_hex[2:])

        try:
            num_readings = int(len(screen_time_readings) / 16)
            total_seconds = sum(int.from_bytes(screen_time_readings[i * 16:i * 16 + 8], "little") for i in range(num_readings))
            total_minutes = total_seconds // 60

            print(f"App Identifier: {app_identifier}; Device: {device_name}; Screen Time: {total_minutes} minutes")
        except IndexError as e:
            print(f"Error processing screen time data for App Identifier: {app_identifier}; Device: {device_name}; Error: {str(e)}")


if __name__ == "__main__":
    main()
