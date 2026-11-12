import sqlite3

from db_repository.config.paths import DB_PATH

conn = sqlite3.connect(DB_PATH)
print("OK")
conn.close()
