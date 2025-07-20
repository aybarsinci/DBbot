import os, sqlite3

# If DB_PATH isn’t set in the environment, fall back to your local file:
DB_PATH = os.getenv('DB_PATH', 'links.db')

conn = sqlite3.connect(DB_PATH)
c    = conn.cursor()

def init_db():
    c.execute('''
      CREATE TABLE IF NOT EXISTS links (
        discord_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL
      )
    ''')
    conn.commit()
