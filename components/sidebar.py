"""
sidebar.py — ChatGPT-style sidebar with:
  - New Chat button
  - Pinned and Favorite sessions categories
  - Session list grouped by date (Today/Yesterday/7 Days/Older)
  - Interactive item previews (last message preview, timestamp, icons)
  - Active highlights and popover menu (Rename, Pin, Favorite, Duplicate, Archive, Delete)
"""
# pyright: ignore [missing-import]
import streamlit as st
import datetime
from vectorstore import build_vector_store
from utils.helpers import format_chat_export_markdown, format_chat_export_json
from components.settings import render_settings_modal, PRESET_PERSONAS
from src.logger import get_logger

logger = get_logger(__name__)


def render_sidebar() -> dict:
    """Renders the full ChatGPT-style sidebar. Returns model config settings dict."""
    settings = {}
    
    # Ensure active session settings exist
    if "sidebar_settings" not in st.session_state:
        st.session_state.sidebar_settings = {
            "model": "gemini-2.5-flash",
            "temperature": 0.7,
            "retriever_k": 4,
            "rag_enabled": True,
            "web_search": False,
            "persona": "",
        }
    
    settings = st.session_state.sidebar_settings

    # Custom sidebar width injection from global settings
    gs = st.session_state.get("global_settings", {})
    sidebar_w = gs.get("sidebar_width", 260)
    
    st.markdown(f"""
    <style>
        [data-testid="stSidebar"] {{
            min-width: {sidebar_w}px !important;
            max-width: {sidebar_w}px !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        # ── HEADER ──────────────────────────────────────────────
        st.markdown("""
        <div class="sidebar-header">
            <span class="sidebar-logo">🤖</span>
            <span class="sidebar-brand">BotTech AI</span>
        </div>
        """, unsafe_allow_html=True)

        # ── NEW CHAT ─────────────────────────────────────────────
        if st.button("＋  New Chat", key="new_chat_btn",
                     use_container_width=True, type="primary"):
            _start_new_chat()

        st.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

        # ── SESSION SEARCH ────────────────────────────────────────
        search_query = st.text_input(
            "🔍 Search chats...",
            key="session_search",
            placeholder="Search conversations...",
            label_visibility="collapsed",
        )

        # ── SESSION HISTORY LIST ──────────────────────────────────
        chat_store = st.session_state.get("chat_store")
        active_session_id = st.session_state.get("active_session_id")

        if chat_store:
            # Refresh sessions
            all_sessions = chat_store.get_all_sessions()
            
            if search_query and search_query.strip():
                results = chat_store.search_sessions(search_query.strip())
                # Filter out archived results
                results = [r for r in results if r.get("is_archived", 0) == 0]
                if results:
                    st.markdown(
                        f"<div class='search-results-label'>{len(results)} result(s)</div>",
                        unsafe_allow_html=True
                    )
                    for session in results[:8]:
                        sid = session["session_id"]
                        title = session.get("title", "New Chat")
                        is_active = sid == active_session_id
                        _render_session_item(sid, title, is_active, chat_store)
                else:
                    st.markdown(
                        "<div class='search-results-label'>No matches found.</div>",
                        unsafe_allow_html=True
                    )
            else:
                _render_session_groups(all_sessions, active_session_id, chat_store)

            st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        st.markdown("<hr class='sidebar-divider'>", unsafe_allow_html=True)

        # ── SIDEBAR FOOTER ────────────────────────────────────────
        if st.button("⚙️ Settings", use_container_width=True):
            render_settings_modal()
        
        if st.button("📁 Export Chats", use_container_width=True):
            _export_chats_modal()
            
        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        
        # ── STATUS FOOTER ─────────────────────────────────────────
        db_ok = st.session_state.get("db") is not None
        status_color = "#10b981" if db_ok else "#ef4444"
        status_text = "Vector DB Ready" if db_ok else "Vector DB Offline"
        
        model_display = settings.get('model', 'gemini-2.5-flash').replace('gemini-','Gemini ')
        st.markdown(f"""
        <div style="text-align:center; padding:12px 0 8px; font-size:0.7rem; color:#6e6e80;">
            <span style="color:{status_color};">●</span>&nbsp;{status_text}
            &nbsp;·&nbsp; {model_display}
        </div>
        <div style="text-align:center; padding-bottom:8px; font-size:0.68rem; color:#4a4a5a;">
            <span class="kbd">Ctrl+Shift+N</span> New Chat
            &nbsp;
            <span class="kbd">Ctrl+/</span> Focus input
        </div>
        """, unsafe_allow_html=True)

    return settings


@st.dialog("Export Chats")
def _export_chats_modal():
    st.markdown("### Export Current Session")
    messages = st.session_state.get("messages", [])
    if messages:
        md_log = format_chat_export_markdown(
            [{"role": m["role"], "content": m["content"]} for m in messages]
        )
        st.download_button(
            label="⬇️ Download Markdown",
            data=md_log,
            file_name=f"bottech_chat_{datetime.date.today()}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        json_log = format_chat_export_json(
            [{"role": m["role"], "content": m["content"]} for m in messages]
        )
        st.download_button(
            label="⬇️ Download JSON",
            data=json_log,
            file_name=f"bottech_chat_{datetime.date.today()}.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.info("No messages to export.")


def _render_session_groups(all_sessions: list, active_session_id: str, chat_store):
    """Renders the grouped session list, including pinned and favorite categories."""
    if not all_sessions:
        st.markdown("""
        <div style="padding:16px 12px; color:#6e6e80; font-size:0.82rem; text-align:center;">
            No conversations yet.<br>Start chatting above!
        </div>
        """, unsafe_allow_html=True)
        return

    # Filter out archived chats
    active_sessions = [s for s in all_sessions if s.get("is_archived", 0) == 0]
    if not active_sessions:
        st.markdown("""
        <div style="padding:16px 12px; color:#6e6e80; font-size:0.82rem; text-align:center;">
            No active conversations.<br>Start chatting above!
        </div>
        """, unsafe_allow_html=True)
        return

    # Pinned Group
    pinned_sessions = [s for s in active_sessions if s.get("is_pinned", 0) == 1]
    if pinned_sessions:
        st.markdown("<div class='session-group-label'>📌 Pinned</div>", unsafe_allow_html=True)
        for session in pinned_sessions:
            sid = session["session_id"]
            title = session.get("title", "New Chat")
            is_active = sid == active_session_id
            _render_session_item(sid, title, is_active, chat_store)

    # Favorites Group (excluding pinned)
    fav_sessions = [s for s in active_sessions if s.get("is_favorited", 0) == 1 and s.get("is_pinned", 0) == 0]
    if fav_sessions:
        st.markdown("<div class='session-group-label'>⭐ Favorites</div>", unsafe_allow_html=True)
        for session in fav_sessions:
            sid = session["session_id"]
            title = session.get("title", "New Chat")
            is_active = sid == active_session_id
            _render_session_item(sid, title, is_active, chat_store)

    # Date Groups (excluding pinned & favorited)
    remaining_sessions = [s for s in active_sessions if s.get("is_pinned", 0) == 0 and s.get("is_favorited", 0) == 0]
    
    now_utc = datetime.datetime.utcnow()
    groups = {
        "Today": [],
        "Yesterday": [],
        "Last 7 Days": [],
        "Older": [],
    }

    for session in remaining_sessions:
        try:
            updated = datetime.datetime.fromisoformat(session["updated_at"])
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

    for group_label, sessions in groups.items():
        if not sessions:
            continue
        st.markdown(
            f"<div class='session-group-label'>{group_label}</div>",
            unsafe_allow_html=True
        )
        for session in sessions:
            sid = session["session_id"]
            title = session.get("title", "New Chat")
            is_active = sid == active_session_id
            _render_session_item(sid, title, is_active, chat_store)


def _render_session_item(session_id: str, title: str, is_active: bool, chat_store):
    """Renders a single session item with load, rename, delete, pin, favorite, and archive options."""
    rename_key = f"renaming_{session_id}"
    is_renaming = st.session_state.get(rename_key, False)

    if is_renaming:
        new_title = st.text_input(
            "Rename chat",
            value=title,
            key=f"rename_input_{session_id}",
            label_visibility="collapsed",
            max_chars=80,
        )
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.button("✓ Save", key=f"save_rename_{session_id}", use_container_width=True):
                if new_title.strip():
                    chat_store.rename_session(session_id, new_title.strip())
                st.session_state[rename_key] = False
                st.rerun()
        with col_cancel:
            if st.button("✗ Cancel", key=f"cancel_rename_{session_id}", use_container_width=True):
                st.session_state[rename_key] = False
                st.rerun()
    else:
        # Load last message preview and timestamp
        last_msg = chat_store.get_session_last_message(session_id)
        if last_msg:
            content = last_msg["content"]
            # Clean up markdown markup
            content = content.replace("**", "").replace("`", "").replace("\n", " ").strip()
            if len(content) > 30:
                preview = content[:28] + "..."
            else:
                preview = content
            
            try:
                dt = datetime.datetime.fromisoformat(last_msg["created_at"])
                if dt.date() == datetime.date.today():
                    time_str = dt.strftime("%I:%M %p")
                else:
                    time_str = dt.strftime("%b %d")
            except Exception:
                time_str = ""
        else:
            preview = "No messages yet"
            time_str = ""
            
        sess_data = chat_store.get_session(session_id)
        is_pinned = sess_data.get("is_pinned", 0) if sess_data else 0
        is_fav = sess_data.get("is_favorited", 0) if sess_data else 0
        
        icons = ""
        if is_pinned:
            icons += "📌 "
        if is_fav:
            icons += "⭐ "
            
        # Standard label representation. theme.css handles newline formatting
        button_label = f"{icons}💬 {title}\n{time_str} · {preview}"
        
        c1, c2 = st.columns([0.83, 0.17])
        with c1:
            btn_style = "primary" if is_active else "secondary"
            # Set key with prefix load_session_ to style it specifically in theme.css
            if st.button(button_label, key=f"load_session_{session_id}", use_container_width=True, help=title, type=btn_style):
                _load_session(session_id, chat_store)
        with c2:
            try:
                with st.popover("⋮", use_container_width=True):
                    # Toggle Pinned
                    pin_lbl = "📌 Unpin" if is_pinned else "📌 Pin"
                    if st.button(pin_lbl, key=f"pin_btn_{session_id}", use_container_width=True):
                        chat_store.toggle_session_pin(session_id)
                        st.rerun()
                        
                    # Toggle Favorite
                    fav_lbl = "⭐ Unfavourite" if is_fav else "⭐ Favourite"
                    if st.button(fav_lbl, key=f"fav_btn_{session_id}", use_container_width=True):
                        chat_store.toggle_session_favorite(session_id)
                        st.rerun()
                        
                    # Duplicate session
                    if st.button("📄 Duplicate", key=f"dup_btn_{session_id}", use_container_width=True):
                        new_id = chat_store.duplicate_session(session_id)
                        if new_id:
                            _load_session(new_id, chat_store)
                            
                    # Rename session
                    if st.button("✏️ Rename", key=f"rename_btn_{session_id}", use_container_width=True):
                        st.session_state[rename_key] = True
                        st.rerun()
                        
                    # Archive session
                    if st.button("📦 Archive", key=f"arc_btn_{session_id}", use_container_width=True):
                        chat_store.toggle_session_archive(session_id)
                        st.rerun()
                        
                    # Delete session
                    if st.button("🗑️ Delete", key=f"del_btn_{session_id}", use_container_width=True, type="primary"):
                        _delete_session(session_id, chat_store)
            except AttributeError:
                # Fallback if popover not available
                if st.button("✏️", key=f"rename_btn_{session_id}"):
                    st.session_state[rename_key] = True
                    st.rerun()


def _load_session(session_id: str, chat_store):
    """Loads a session into the active state."""
    st.session_state.active_session_id = session_id
    raw_messages = chat_store.get_messages(session_id)
    loaded_messages = []
    for m in raw_messages:
        c_desc = m.get("confidence_desc", "")
        s_type = "🧠 AI General Knowledge"
        if c_desc and c_desc.startswith("source:"):
            s_type = c_desc.split("source:")[1]
            if s_type == "📄 Knowledge Base":
                score = m.get("confidence_score")
                if score is not None:
                    if score >= 85:
                        c_desc = "High Confidence (Strong local document matches)"
                    elif score >= 65:
                        c_desc = "Medium-High Confidence (Moderate document matches)"
                    elif score >= 45:
                        c_desc = "Medium Confidence (Weak matches or partial details)"
                    else:
                        c_desc = "Low Confidence (Answering mainly from general training data)"
                else:
                    c_desc = ""
            else:
                c_desc = ""
        loaded_messages.append({
            "role": m["role"],
            "content": m["content"],
            "citations": m.get("citations", []) if s_type == "📄 Knowledge Base" else [],
            "web_citations": m.get("citations", []) if s_type == "🌐 Web Search" else [],
            "confidence_score": m.get("confidence_score"),
            "confidence_desc": c_desc,
            "source_type": s_type,
            "message_id": m.get("message_id", ""),
            "feedback": m.get("feedback"),
        })
    st.session_state.messages = loaded_messages
    from chat_manager import ChatMemory
    memory = ChatMemory()
    for m in raw_messages:
        if m["role"] == "user":
            memory.add_user_message(m["content"])
        else:
            memory.add_assistant_message(m["content"])
    st.session_state.memory = memory
    st.session_state.related_questions = []
    st.session_state.pending_query = None
    st.session_state.edit_mode = False
    logger.info(f"Loaded session: {session_id}")
    st.rerun()


def _delete_session(session_id: str, chat_store):
    """Deletes a session; if active, starts a new chat."""
    chat_store.delete_session(session_id)
    if st.session_state.get("active_session_id") == session_id:
        _start_new_chat()
    else:
        st.rerun()


def _start_new_chat():
    """Resets state and creates a fresh new chat session."""
    from chat_manager import ChatMemory
    from storage import ChatStore
    from config.settings import CHAT_DB_PATH

    chat_store = st.session_state.get("chat_store")
    if chat_store is None:
        chat_store = ChatStore(CHAT_DB_PATH)
        st.session_state.chat_store = chat_store

    new_sid = chat_store.create_session(title="New Chat")
    st.session_state.active_session_id = new_sid
    st.session_state.messages = []
    st.session_state.memory = ChatMemory()
    st.session_state.related_questions = []
    st.session_state.pending_query = None
    st.session_state.edit_mode = False
    st.session_state.edit_message_index = None
    st.session_state.uploaded_files = []
    st.session_state.pending_image = None
    logger.info(f"Started new session: {new_sid}")
    st.rerun()
