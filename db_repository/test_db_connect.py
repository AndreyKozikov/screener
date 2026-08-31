import sqlite3

path = r"D:\Andrew\GeekBrains\Python\BondsScreener\backend\db\bonds.db"

conn = sqlite3.connect(path)
print("OK")
conn.close()