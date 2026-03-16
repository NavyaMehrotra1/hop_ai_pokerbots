import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tournament.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS bots (
                name TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                matches_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                total_delta INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot1 TEXT NOT NULL,
                bot2 TEXT NOT NULL,
                bot1_delta INTEGER,
                bot2_delta INTEGER,
                winner TEXT,
                num_rounds INTEGER,
                log_path TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (bot1) REFERENCES bots(name),
                FOREIGN KEY (bot2) REFERENCES bots(name)
            );

            CREATE TABLE IF NOT EXISTS tournament_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                status TEXT DEFAULT 'idle',
                started_at TEXT,
                completed_at TEXT,
                total_matches INTEGER DEFAULT 0,
                completed_matches INTEGER DEFAULT 0
            );

            INSERT OR IGNORE INTO tournament_state (id, status) VALUES (1, 'idle');
        ''')


def register_bot(name, path):
    with get_conn() as conn:
        conn.execute(
            'INSERT OR REPLACE INTO bots (name, path) VALUES (?, ?)',
            (name, path)
        )


def create_match(bot1, bot2):
    with get_conn() as conn:
        cursor = conn.execute(
            'INSERT INTO matches (bot1, bot2, created_at, status) VALUES (?, ?, ?, ?)',
            (bot1, bot2, datetime.now().isoformat(), 'pending')
        )
        return cursor.lastrowid


def update_match(match_id, bot1_delta, bot2_delta, winner, num_rounds, log_path, status):
    with get_conn() as conn:
        conn.execute('''
            UPDATE matches
            SET bot1_delta=?, bot2_delta=?, winner=?, num_rounds=?,
                log_path=?, status=?, completed_at=?
            WHERE id=?
        ''', (bot1_delta, bot2_delta, winner, num_rounds, log_path, status,
              datetime.now().isoformat(), match_id))


def update_bot_stats(name, delta, won, drew):
    with get_conn() as conn:
        conn.execute('''
            UPDATE bots SET
                matches_played = matches_played + 1,
                wins = wins + ?,
                losses = losses + ?,
                draws = draws + ?,
                total_delta = total_delta + ?
            WHERE name = ?
        ''', (
            1 if won else 0,
            1 if (not won and not drew) else 0,
            1 if drew else 0,
            delta,
            name
        ))


def get_leaderboard():
    with get_conn() as conn:
        return conn.execute('''
            SELECT *,
                CASE WHEN matches_played > 0
                     THEN ROUND(100.0 * wins / matches_played, 1)
                     ELSE 0 END as win_rate
            FROM bots
            ORDER BY total_delta DESC, wins DESC
        ''').fetchall()


def get_matches(limit=50, offset=0):
    with get_conn() as conn:
        return conn.execute('''
            SELECT * FROM matches
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        ''', (limit, offset)).fetchall()


def get_match(match_id):
    with get_conn() as conn:
        return conn.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()


def get_tournament_state():
    with get_conn() as conn:
        return conn.execute('SELECT * FROM tournament_state WHERE id = 1').fetchone()


def update_tournament_state(**kwargs):
    if not kwargs:
        return
    fields = ', '.join(f'{k}=?' for k in kwargs)
    values = list(kwargs.values())
    with get_conn() as conn:
        conn.execute(f'UPDATE tournament_state SET {fields} WHERE id = 1', values)


def reset_tournament():
    with get_conn() as conn:
        conn.executescript('''
            DELETE FROM matches;
            UPDATE bots SET matches_played=0, wins=0, losses=0, draws=0, total_delta=0;
            UPDATE tournament_state SET status='idle', started_at=NULL, completed_at=NULL,
                total_matches=0, completed_matches=0;
        ''')
