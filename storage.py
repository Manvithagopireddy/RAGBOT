"""
chat_store.py — Persistent multi-session chat history using SQLite.
Provides full CRUD for sessions, messages, feedback, search, and personas.
"""
import sqlite3
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
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
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Creates tables if they do not exist. Migrates schema if needed."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id   TEXT PRIMARY KEY,
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
                    is_favorited INTEGER NOT NULL DEFAULT 0
                )
            """)
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
            # Safe migration: add columns if they don't exist
            self._safe_add_column(conn, "sessions", "persona", "TEXT DEFAULT ''")
            self._safe_add_column(conn, "sessions", "web_search", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_pinned", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_favorited", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "sessions", "is_archived", "INTEGER NOT NULL DEFAULT 0")
            self._safe_add_column(conn, "messages", "feedback", "TEXT DEFAULT NULL")
            self._safe_add_column(conn, "messages", "pinned", "INTEGER NOT NULL DEFAULT 0")
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
    ) -> str:
        """Creates a new chat session and returns its session_id."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions
                   (session_id, title, created_at, updated_at, model, temperature,
                    retriever_k, rag_enabled, persona, web_search, is_pinned, is_favorited, is_archived)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)""",
                (session_id, title, now, now, model, temperature,
                 retriever_k, int(rag_enabled), persona, int(web_search)),
            )
            conn.commit()
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Returns all sessions ordered by most recently updated."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Returns a single session by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return dict(row) if row else None

    def rename_session(self, session_id: str, new_title: str):
        """Renames a session."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = ? WHERE session_id = ?",
                (new_title.strip()[:80], now, session_id),
            )
            conn.commit()

    def delete_session(self, session_id: str):
        """Deletes a session and all its messages (CASCADE)."""
        with self._connect() as conn:
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
                if hasattr(obj, 'item') and callable(getattr(obj, 'item')):
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
