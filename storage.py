"""
chat_store.py — Persistent multi-session chat history using SQLite.
Provides full CRUD for sessions, messages, feedback, search, and personas.
"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.logger import get_logger

logger = get_logger(__name__)


class ChatStore:
    """
    Manages persistent chat sessions and messages via SQLite.
    Each session has a UUID, auto-generated title, and ordered messages.
    Supports: feedback (thumbs), session search, custom persona per session.
    """

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates tables if they do not exist. Migrates schema if needed."""
        with self._connect() as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id         TEXT PRIMARY KEY,
                    username        TEXT UNIQUE NOT NULL,
                    email           TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role            TEXT NOT NULL DEFAULT 'user',
                    created_at      TEXT NOT NULL
                )
            """)

            # Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
                    user_id      TEXT NOT NULL DEFAULT 'default_user',
                    title        TEXT NOT NULL DEFAULT 'New Chat',
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    model        TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
                    temperature  REAL NOT NULL DEFAULT 0.7,
                    retriever_k  INTEGER NOT NULL DEFAULT 4,
                    rag_enabled  INTEGER NOT NULL DEFAULT 1,
                    persona      TEXT DEFAULT '',
                    web_search   INTEGER NOT NULL DEFAULT 0,
                    is_pinned    INTEGER NOT NULL DEFAULT 0,
                    is_favorited INTEGER NOT NULL DEFAULT 0,
                    is_archived  INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id      TEXT PRIMARY KEY,
                    session_id      TEXT NOT NULL,
                    role            TEXT NOT NULL,
                    content         TEXT NOT NULL,
                    citations       TEXT,
                    confidence_score INTEGER,
                    confidence_desc  TEXT,
                    feedback        TEXT DEFAULT NULL,
                    pinned          INTEGER NOT NULL DEFAULT 0,
                    created_at      TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)

            # Documents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id     TEXT PRIMARY KEY,
                    user_id         TEXT NOT NULL DEFAULT 'default_user',
                    filename        TEXT NOT NULL,
                    file_path       TEXT NOT NULL,
                    file_type       TEXT NOT NULL,
                    file_size       INTEGER NOT NULL,
                    chunk_count     INTEGER NOT NULL DEFAULT 0,
                    checksum        TEXT,
                    status          TEXT NOT NULL DEFAULT 'indexed',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)

            # Seed default user for backward compatibility
            conn.execute("""
                INSERT OR IGNORE INTO users (user_id, username, email, hashed_password, role, created_at)
                VALUES ('default_user', 'admin', 'admin@ragbot.local', '$2b$12$defaultUserHashPlaceholderForDev2026', 'admin', ?)
            """, (datetime.utcnow().isoformat(),))

            # Safe migrations: add columns if they don't exist
            self._safe_add_column(conn, "sessions", "user_id", "TEXT NOT NULL DEFAULT 'default_user'")
            self._safe_add_column(conn, "sessions", "persona", "TEXT DEFAULT ''")
            self._safe_add_column(conn, "sessions", "web_search", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_pinned", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_favorited", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_archived", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "messages", "feedback", "TEXT DEFAULT NULL")
            self._safe_add_column(conn, "messages", "pinned", "INTEGER NOT NULL DEFAULT 0")

            # Indexes for relational performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at ASC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

            conn.commit()
        logger.info(f"ChatStore DB initialized at: {self.db_path}")

    def _safe_add_column(self, conn, table: str, column: str, col_def: str):
        """Adds a column to an existing table if it doesn't already exist."""
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        except sqlite3.OperationalError:
            pass  # Column already exists

    # ──────────────────────────────────────────────────
    # Session Operations
    # ──────────────────────────────────────────────────

    def create_session(
        self,
        title: str = "New Chat",
        model: str = "gemini-2.5-flash",
        temperature: float = 0.7,
        retriever_k: int = 4,
        rag_enabled: bool = True,
        persona: str = "",
        web_search: bool = False,
        user_id: str = "default_user",
    ) -> str:
        """Creates a new chat session and returns its session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions
                   (session_id, user_id, title, created_at, updated_at, model, temperature,
                    retriever_k, rag_enabled, persona, web_search, is_pinned, is_favorited, is_archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
                (session_id, user_id, title, now, now, model, temperature,
                 retriever_k, int(rag_enabled), persona, int(web_search)),
            )
            conn.commit()
        logger.info(f"Created session: {session_id} (user: {user_id})")
        return session_id

    def get_all_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all sessions ordered by most recently updated, optionally filtered by user_id."""
        with self._connect() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns a single session by ID, optionally verifying user ownership."""
        with self._connect() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ? AND user_id = ?",
                    (session_id, user_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
                ).fetchone()
        return dict(row) if row else None

    def rename_session(self, session_id: str, new_title: str, user_id: Optional[str] = None):
        """Renames a session, optionally verifying user ownership."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if user_id:
                conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ? AND user_id = ?",
                    (new_title.strip()[:80], now, session_id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                    (new_title.strip()[:80], now, session_id),
                )
            conn.commit()

    def delete_session(self, session_id: str, user_id: Optional[str] = None):
        """Deletes a session and all its messages (CASCADE), optionally verifying user ownership."""
        with self._connect() as conn:
            if user_id:
                conn.execute("DELETE FROM sessions WHERE session_id = ? AND user_id = ?", (session_id, user_id))
            else:
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        logger.info(f"Deleted session: {session_id}")

    def toggle_session_pin(self, session_id: str) -> bool:
        """Toggles the pinned state of a session."""
        with self._connect() as conn:
            row = conn.execute("SELECT is_pinned FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                return False
            new_val = 0 if row["is_pinned"] else 1
            conn.execute("UPDATE sessions SET is_pinned = ? WHERE session_id = ?", (new_val, session_id))
            conn.commit()
            return bool(new_val)

    def toggle_session_favorite(self, session_id: str) -> bool:
        """Toggles the favorited state of a session."""
        with self._connect() as conn:
            row = conn.execute("SELECT is_favorited FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                return False
            new_val = 0 if row["is_favorited"] else 1
            conn.execute("UPDATE sessions SET is_favorited = ? WHERE session_id = ?", (new_val, session_id))
            conn.commit()
            return bool(new_val)

    def toggle_session_archive(self, session_id: str) -> bool:
        """Toggles the archived state of a session."""
        with self._connect() as conn:
            row = conn.execute("SELECT is_archived FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                return False
            new_val = 0 if row["is_archived"] else 1
            conn.execute("UPDATE sessions SET is_archived = ? WHERE session_id = ?", (new_val, session_id))
            conn.commit()
            return bool(new_val)

    def get_archived_sessions(self) -> List[Dict[str, Any]]:
        """Returns all archived sessions ordered by most recently updated."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE is_archived = 1 ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def duplicate_session(self, session_id: str) -> Optional[str]:
        """Duplicates a session and all its messages. Returns the new session ID."""
        with self._connect() as conn:
            sess = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            if not sess:
                return None

            new_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            new_title = f"{sess['title']} (Copy)"

            conn.execute(
                """INSERT INTO sessions
                   (session_id, title, created_at, updated_at, model, temperature, retriever_k, rag_enabled, persona, web_search, is_pinned, is_favorited, is_archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id, new_title, now, now, sess["model"], sess["temperature"], sess["retriever_k"], sess["rag_enabled"], sess["persona"], sess["web_search"], 0, 0, 0)
            )

            messages = conn.execute("SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
            for m in messages:
                conn.execute(
                    """INSERT INTO messages (message_id, session_id, role, content, citations, confidence_score, confidence_desc, feedback, pinned, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), new_id, m["role"], m["content"], m["citations"], m["confidence_score"], m["confidence_desc"], m["feedback"], m["pinned"], m["created_at"])
                )
            conn.commit()
            return new_id

    def clear_all_sessions(self):
        """Deletes all sessions and messages in the database."""
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions")
            conn.commit()
        logger.info("Cleared all sessions from database.")

    def update_session_timestamp(self, session_id: str):
        """Bumps the updated_at timestamp for ordering."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            conn.commit()

    def update_session_settings(
        self,
        session_id: str,
        temperature: float,
        retriever_k: int,
        rag_enabled: bool,
        model: str = "gemini-2.5-flash",
        persona: str = "",
        web_search: bool = False,
    ):
        """Persists all model settings for a session."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """UPDATE sessions
                   SET temperature=?, retriever_k=?, rag_enabled=?,
                       model=?, persona=?, web_search=?, updated_at=?
                   WHERE session_id=?""",
                (temperature, retriever_k, int(rag_enabled),
                 model, persona, int(web_search), now, session_id),
            )
            conn.commit()

    def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """Searches sessions by title or message content."""
        q = f"%{query.lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT DISTINCT s.* FROM sessions s
                   LEFT JOIN messages m ON s.session_id = m.session_id
                   WHERE LOWER(s.title) LIKE ? OR LOWER(m.content) LIKE ?
                   ORDER BY s.updated_at DESC LIMIT 20""",
                (q, q),
            ).fetchall()
        return [dict(r) for r in rows]

    # ──────────────────────────────────────────────────
    # Message Operations
    # ──────────────────────────────────────────────────

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        citations: Optional[List[Dict]] = None,
        confidence_score: Optional[int] = None,
        confidence_desc: Optional[str] = None,
    ) -> str:
        """Appends a message to a session."""
        message_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'item') and callable(obj.item):
                    return obj.item()
                if 'float' in obj.__class__.__name__.lower():
                    return float(obj)
                if 'int' in obj.__class__.__name__.lower():
                    return int(obj)
                return super().default(obj)

        citations_json = json.dumps(citations, cls=NumpyEncoder) if citations else None
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO messages
                   (message_id, session_id, role, content, citations,
                    confidence_score, confidence_desc, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (message_id, session_id, role, content, citations_json,
                 confidence_score, confidence_desc, now),
            )
            conn.commit()
        self.update_session_timestamp(session_id)
        return message_id

    def get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns all messages for a session in chronological order."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        result = []
        for r in rows:
            msg = dict(r)
            if msg.get("citations"):
                try:
                    msg["citations"] = json.loads(msg["citations"])
                except Exception:
                    msg["citations"] = []
            else:
                msg["citations"] = []
            result.append(msg)
        return result

    def update_message_feedback(self, message_id: str, feedback: str):
        """Stores thumbs up/down feedback for a message."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET feedback = ? WHERE message_id = ?",
                (feedback, message_id),
            )
            conn.commit()

    def toggle_pin_message(self, message_id: str) -> bool:
        """Toggles the pinned state of a message. Returns new pinned state."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT pinned FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row is None:
                return False
            new_pinned = 0 if row["pinned"] else 1
            conn.execute(
                "UPDATE messages SET pinned = ? WHERE message_id = ?",
                (new_pinned, message_id),
            )
            conn.commit()
        return bool(new_pinned)

    def get_pinned_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns all pinned messages for a session."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM messages WHERE session_id = ? AND pinned = 1
                   ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session_last_message(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Returns the content and created_at timestamp of the last message in a session."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content, created_at FROM messages WHERE session_id = ? ORDER BY created_at DESC LIMIT 1",
                (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def delete_messages_from(self, session_id: str, from_created_at: str):
        """Deletes all messages after (inclusive) a given timestamp."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM messages WHERE session_id = ? AND created_at >= ?",
                (session_id, from_created_at),
            )
            conn.commit()

    def clear_messages(self, session_id: str):
        """Removes all messages from a session without deleting the session."""
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

    def append_message_content(self, message_id: str, text_to_append: str):
        """Appends text to the content of an existing message."""
        with self._connect() as conn:
            row = conn.execute("SELECT content FROM messages WHERE message_id = ?", (message_id,)).fetchone()
            if row:
                new_content = row["content"] + text_to_append
                conn.execute("UPDATE messages SET content = ? WHERE message_id = ?", (new_content, message_id))
                conn.commit()

    def update_message_content(self, message_id: str, new_content: str):
        """Updates the content of an existing message."""
        with self._connect() as conn:
            conn.execute("UPDATE messages SET content = ? WHERE message_id = ?", (new_content, message_id))
            conn.commit()

    def save_message_source_type(self, message_id: str, source_type: str) -> None:
        """
        Persists the routing source type (e.g. 'source:📄 Knowledge Base') into
        the confidence_desc field of a message.

        This is the proper public API for what chat.py previously did by calling
        the private _connect() method directly (FIX BUG-006 / BUG-010).
        """
        tag = f"source:{source_type}"
        with self._connect() as conn:
            conn.execute(
                "UPDATE messages SET confidence_desc = ? WHERE message_id = ?",
                (tag, message_id),
            )
            conn.commit()

    def get_message_count(self, session_id: str) -> int:
        """Returns the total number of messages in a session."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────────
    # Analytics
    # ──────────────────────────────────────────────────

    def get_analytics(self) -> Dict[str, Any]:
        """Returns aggregate stats for the analytics dashboard."""
        with self._connect() as conn:
            total_sessions = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
            total_messages = conn.execute("SELECT COUNT(*) as c FROM messages").fetchone()["c"]
            user_messages = conn.execute(
                "SELECT COUNT(*) as c FROM messages WHERE role='user'"
            ).fetchone()["c"]
            thumbs_up = conn.execute(
                "SELECT COUNT(*) as c FROM messages WHERE feedback='up'"
            ).fetchone()["c"]
            thumbs_down = conn.execute(
                "SELECT COUNT(*) as c FROM messages WHERE feedback='down'"
            ).fetchone()["c"]

            # Messages per day (last 14 days)
            daily = conn.execute(
                """SELECT DATE(created_at) as day, COUNT(*) as cnt
                   FROM messages
                   WHERE DATE(created_at) >= DATE('now', '-14 days')
                   GROUP BY day ORDER BY day ASC"""
            ).fetchall()

            # Avg response length
            avg_len = conn.execute(
                "SELECT AVG(LENGTH(content)) as a FROM messages WHERE role='assistant'"
            ).fetchone()["a"]

            # Avg confidence score per day (last 14 days) — assistant messages with score
            daily_confidence = conn.execute(
                """SELECT DATE(created_at) as day, AVG(confidence_score) as avg_score
                   FROM messages
                   WHERE role='assistant'
                     AND confidence_score IS NOT NULL
                     AND DATE(created_at) >= DATE('now', '-14 days')
                   GROUP BY day ORDER BY day ASC"""
            ).fetchall()

            # Overall avg confidence score
            avg_confidence = conn.execute(
                """SELECT AVG(confidence_score) as a FROM messages
                   WHERE role='assistant' AND confidence_score IS NOT NULL"""
            ).fetchone()["a"]

            # Source type distribution from confidence_desc prefix
            kb_count = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE role='assistant' AND confidence_desc LIKE 'source:📄 Knowledge Base'"""
            ).fetchone()["c"]
            web_count = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE role='assistant' AND confidence_desc LIKE 'source:🌐 Web Search'"""
            ).fetchone()["c"]
            ai_count = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE role='assistant'
                     AND (confidence_desc IS NULL OR confidence_desc NOT LIKE 'source:%')"""
            ).fetchone()["c"]

            # Model usage breakdown
            model_usage = conn.execute(
                """SELECT model, COUNT(*) as cnt FROM sessions GROUP BY model ORDER BY cnt DESC"""
            ).fetchall()

            # Feedback counts per source type
            fb_kb_up = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='up' AND confidence_desc LIKE 'source:📄 Knowledge Base'"""
            ).fetchone()["c"]
            fb_kb_down = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='down' AND confidence_desc LIKE 'source:📄 Knowledge Base'"""
            ).fetchone()["c"]
            fb_web_up = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='up' AND confidence_desc LIKE 'source:🌐 Web Search'"""
            ).fetchone()["c"]
            fb_web_down = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='down' AND confidence_desc LIKE 'source:🌐 Web Search'"""
            ).fetchone()["c"]
            fb_ai_up = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='up'
                     AND (confidence_desc IS NULL OR confidence_desc NOT LIKE 'source:%')"""
            ).fetchone()["c"]
            fb_ai_down = conn.execute(
                """SELECT COUNT(*) as c FROM messages
                   WHERE feedback='down'
                     AND (confidence_desc IS NULL OR confidence_desc NOT LIKE 'source:%')"""
            ).fetchone()["c"]

            # Top 5 sessions by message count
            top_sessions = conn.execute(
                """SELECT s.title, s.model, s.created_at,
                          COUNT(m.message_id) as msg_count
                   FROM sessions s
                   LEFT JOIN messages m ON s.session_id = m.session_id
                   GROUP BY s.session_id
                   ORDER BY msg_count DESC LIMIT 5"""
            ).fetchall()

            # Sessions created per day (last 14 days)
            daily_sessions = conn.execute(
                """SELECT DATE(created_at) as day, COUNT(*) as cnt
                   FROM sessions
                   WHERE DATE(created_at) >= DATE('now', '-14 days')
                   GROUP BY day ORDER BY day ASC"""
            ).fetchall()

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "user_messages": user_messages,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "daily_messages": [dict(r) for r in daily],
            "avg_response_length": int(avg_len or 0),
            "daily_confidence": [dict(r) for r in daily_confidence],
            "avg_confidence": round(avg_confidence or 0, 1),
            "source_distribution": {
                "Knowledge Base": kb_count,
                "Web Search": web_count,
                "AI General": ai_count,
            },
            "model_usage": [dict(r) for r in model_usage],
            "feedback_by_source": {
                "Knowledge Base": {"up": fb_kb_up, "down": fb_kb_down},
                "Web Search": {"up": fb_web_up, "down": fb_web_down},
                "AI General": {"up": fb_ai_up, "down": fb_ai_down},
            },
            "top_sessions": [dict(r) for r in top_sessions],
            "daily_sessions": [dict(r) for r in daily_sessions],
        }

    # ──────────────────────────────────────────────────
    # Grouped Session Listing (for ChatGPT sidebar)
    # ──────────────────────────────────────────────────

    def get_sessions_grouped(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns sessions grouped by: Today / Yesterday / Last 7 Days / Older."""
        all_sessions = self.get_all_sessions()
        now_utc = datetime.utcnow()

        groups: Dict[str, List[Dict]] = {
            "Today": [],
            "Yesterday": [],
            "Last 7 Days": [],
            "Older": [],
        }

        for session in all_sessions:
            if session.get("is_archived", 0) == 1:
                continue
            try:
                updated = datetime.fromisoformat(session["updated_at"])
                delta = now_utc - updated
                if delta.days == 0:
                    groups["Today"].append(session)
                elif delta.days == 1:
                    groups["Yesterday"].append(session)
                elif delta.days <= 7:
                    groups["Last 7 Days"].append(session)
                else:
                    groups["Older"].append(session)
            except Exception:
                groups["Older"].append(session)

        return groups

    # ──────────────────────────────────────────────────
    # User Operations
    # ──────────────────────────────────────────────────

    def create_user(
        self,
        username: str,
        email: str,
        hashed_password: str,
        role: str = "user",
    ) -> Dict[str, Any]:
        """Creates a new user record."""
        user_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO users (user_id, username, email, hashed_password, role, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username.strip(), email.strip().lower(), hashed_password, role, now)
            )
            conn.commit()
        return {
            "user_id": user_id,
            "username": username.strip(),
            "email": email.strip().lower(),
            "role": role,
            "created_at": now
        }

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Finds user by user_id."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Finds user by username."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(username) = ?", (username.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Finds user by email."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None

    # ──────────────────────────────────────────────────
    # Document Operations
    # ──────────────────────────────────────────────────

    def add_document(
        self,
        document_id: str,
        filename: str,
        file_path: str,
        file_type: str,
        file_size: int,
        chunk_count: int = 0,
        checksum: Optional[str] = None,
        status: str = "indexed",
        user_id: str = "default_user",
    ) -> Dict[str, Any]:
        """Records a new document in the catalog."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO documents
                   (document_id, user_id, filename, file_path, file_type, file_size, chunk_count, checksum, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (document_id, user_id, filename, file_path, file_type, file_size, chunk_count, checksum, status, now, now)
            )
            conn.commit()
        return {
            "document_id": document_id,
            "user_id": user_id,
            "filename": filename,
            "file_path": file_path,
            "file_type": file_type,
            "file_size": file_size,
            "chunk_count": chunk_count,
            "checksum": checksum,
            "status": status,
            "created_at": now,
            "updated_at": now
        }

    def get_documents(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all documents, optionally filtered by user_id."""
        with self._connect() as conn:
            if user_id:
                rows = conn.execute(
                    "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
                    (user_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM documents ORDER BY created_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def get_document(self, document_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Returns a single document by ID, optionally verifying user ownership."""
        with self._connect() as conn:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM documents WHERE document_id = ? AND user_id = ?",
                    (document_id, user_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM documents WHERE document_id = ?",
                    (document_id,)
                ).fetchone()
        return dict(row) if row else None

    def delete_document(self, document_id: str, user_id: Optional[str] = None) -> bool:
        """Deletes a document from the catalog."""
        with self._connect() as conn:
            if user_id:
                cur = conn.execute(
                    "DELETE FROM documents WHERE document_id = ? AND user_id = ?",
                    (document_id, user_id)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM documents WHERE document_id = ?",
                    (document_id,)
                )
            conn.commit()
            return cur.rowcount > 0

    def update_document_status(
        self,
        document_id: str,
        status: str,
        chunk_count: Optional[int] = None
    ) -> bool:
        """Updates document status and optionally chunk count."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            if chunk_count is not None:
                cur = conn.execute(
                    "UPDATE documents SET status = ?, chunk_count = ?, updated_at = ? WHERE document_id = ?",
                    (status, chunk_count, now, document_id)
                )
            else:
                cur = conn.execute(
                    "UPDATE documents SET status = ?, updated_at = ? WHERE document_id = ?",
                    (status, now, document_id)
                )
            conn.commit()
            return cur.rowcount > 0

