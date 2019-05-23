import sqlite3
conn = sqlite3.connect('objects.db')
conn.execute("DELETE from OBJECT;")
conn.commit()
conn.close()