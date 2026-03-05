import sqlite3
from contextlib import contextmanager

SQLITE_PATH = "db.sqlite"

@contextmanager
def connect():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def _now():
    import datetime
    return datetime.datetime.utcnow().isoformat(timespec="seconds")+"Z"

def init_db():
    with connect() as conn:
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY,
          first_name TEXT,
          username TEXT,
          photo_url TEXT,
          balance INTEGER NOT NULL DEFAULT 0,
          referrer_id INTEGER NULL,
          created_at TEXT NOT NULL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS tx(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          type TEXT NOT NULL,
          amount INTEGER NOT NULL,
          meta TEXT NULL,
          created_at TEXT NOT NULL
        );
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS payments(
          telegram_payment_charge_id TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          amount INTEGER NOT NULL,
          currency TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """)
        conn.commit()

def upsert_user(uid:int, first_name:str, username:str, photo_url:str):
    with connect() as conn:
        c=conn.cursor()
        c.execute("SELECT id FROM users WHERE id=?", (uid,))
        if c.fetchone() is None:
            c.execute("INSERT INTO users(id,first_name,username,photo_url,balance,referrer_id,created_at) VALUES (?,?,?,?,0,NULL,?)",
                      (uid, first_name, username, photo_url, _now()))
        else:
            c.execute("UPDATE users SET first_name=?, username=?, photo_url=? WHERE id=?",
                      (first_name, username, photo_url, uid))
        conn.commit()

def get_user(uid:int):
    with connect() as conn:
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (uid,))
        return c.fetchone()

def set_referrer_if_empty(uid:int, ref:int):
    if not ref or ref==uid:
        return
    with connect() as conn:
        c=conn.cursor()
        c.execute("UPDATE users SET referrer_id=? WHERE id=? AND referrer_id IS NULL", (ref, uid))
        conn.commit()

def add_balance(uid:int, amount:int, tx_type:str, meta:str|None=None):
    with connect() as conn:
        c=conn.cursor()
        c.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, uid))
        c.execute("INSERT INTO tx(user_id,type,amount,meta,created_at) VALUES (?,?,?,?,?)",
                  (uid, tx_type, amount, meta, _now()))
        conn.commit()

def get_stats(uid:int):
    with connect() as conn:
        c=conn.cursor()
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id=?", (uid,))
        refs=c.fetchone()[0]
        c.execute("SELECT COALESCE(SUM(amount),0) FROM tx WHERE user_id=? AND type='ref_bonus'", (uid,))
        earned=c.fetchone()[0]
        return int(refs), int(earned)

def record_payment_if_new(charge_id:str, user_id:int, amount:int, currency:str)->bool:
    with connect() as conn:
        c=conn.cursor()
        try:
            c.execute("INSERT INTO payments(telegram_payment_charge_id,user_id,amount,currency,created_at) VALUES (?,?,?,?,?)",
                      (charge_id, user_id, amount, currency, _now()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def list_users(limit=200):
    with connect() as conn:
        c=conn.cursor()
        c.execute("SELECT id,first_name,username,balance,referrer_id,created_at FROM users ORDER BY created_at DESC LIMIT ?", (limit,))
        return c.fetchall()

def list_tx(limit=200):
    with connect() as conn:
        c=conn.cursor()
        c.execute("SELECT id,user_id,type,amount,created_at,meta FROM tx ORDER BY created_at DESC LIMIT ?", (limit,))
        return c.fetchall()
