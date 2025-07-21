import sqlite3

# Open (or create) links.db in the working directory
conn = sqlite3.connect('links.db')
c    = conn.cursor()

def init_db():
    c.execute('''
      CREATE TABLE IF NOT EXISTS links (
        discord_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL
      )
    ''')
    conn.commit()
