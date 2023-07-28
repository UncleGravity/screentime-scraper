import os
import sqlite3
from os.path import expanduser

def open_knowledgeC_db():
    home_folder = expanduser("~")
    path = os.path.join(home_folder, "Library/Application Support/Knowledge/knowledgeC.db")
    conn = sqlite3.connect(path)
    return conn

def get_table_names(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [row[0] for row in cursor.fetchall()]

def get_table_structure(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()

def main():
    conn = open_knowledgeC_db()
    table_names = get_table_names(conn)

    for table_name in table_names:
        print(f"Table: {table_name}")
        structure = get_table_structure(conn, table_name)
        for column in structure:
            print(f"  {column[1]} ({column[2]})")
        print()

    conn.close()

if __name__ == "__main__":
    main()
