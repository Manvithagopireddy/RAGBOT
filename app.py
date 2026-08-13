# pyright: ignore [missing-import]
import streamlit as st
# pyright: ignore [missing-import]
from dotenv import load_dotenv
import os
from pathlib import Path
from config.settings import VECTOR_STORE_DIR, CHAT_DB_PATH
from vectorstore import get_or_build_vector_store
from chat_manager import ChatMemory
from storage import ChatStore
from components.components import inject_custom_css, inject_all_js
from components.sidebar import render_sidebar, _start_new_chat
from components.chat import render_chat_page
from components.analytics import render_analytics_dashboard
from src.logger import get_logger

# Load environment variables
load_dotenv()

logger = get_logger(__name__)

# ── PAGE CONFIG ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BotTech AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── INJECT CSS + KEYBOARD SHORTCUTS ───────────────────────────────────────────
_CSS_PATH = str(Path(__file__).parent / "styles" / "theme.css")
inject_custom_css(_CSS_PATH)
inject_all_js()

# ── INITIALIZE PERSISTENT CHAT STORE ──────────────────────────────────────────
if "chat_store" not in st.session_state:
    st.session_state.chat_store = ChatStore(CHAT_DB_PATH)
    logger.info("ChatStore initialized.")

chat_store: ChatStore = st.session_state.chat_store

# ── INITIALIZE VECTOR DB ───────────────────────────────────────────────────────
if "db" not in st.session_state:
    with st.spinner("Initializing knowledge base…"):
        st.session_state.db = get_or_build_vector_store()

# ── INITIALIZE SESSION STATE ───────────────────────────────────────────────────
if "active_session_id" not in st.session_state:
    all_sessions = chat_store.get_all_sessions()
    if all_sessions:
        most_recent = all_sessions[0]
        sid = most_recent["session_id"]
        st.session_state.active_session_id = sid
        raw_messages = chat_store.get_messages(sid)
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
        memory = ChatMemory()
        for m in raw_messages:
            if m["role"] == "user":
                memory.add_user_message(m["content"])
            else:
                memory.add_assistant_message(m["content"])
        st.session_state.memory = memory
    else:
        new_sid = chat_store.create_session(title="New Chat")
        st.session_state.active_session_id = new_sid
        st.session_state.messages = []
        st.session_state.memory = ChatMemory()

# ── DEFAULT SESSION STATE VARS ─────────────────────────────────────────────────
_defaults = {
    "memory": ChatMemory(),
    "messages": [],
    "related_questions": [],
    "pending_query": None,
    "edit_mode": False,
    "edit_message_index": None,
    "uploaded_files": [],
    "show_comparison": False,
    "show_analytics": False,
    "pending_image": None,
    "persona_text": "",
    "show_right_panel": True,
    "similarity_threshold": 0.4,
    "global_settings": {
        "theme": "Dark",
        "font_size": "Medium",
        "sidebar_width": 260,
        "compact_mode": False,
        "animations_enabled": True,
        "top_p": 0.95,
        "max_tokens": 4096,
        "streaming_enabled": True,
        "hybrid_search": True,
        "accent_color": "#6366f1",
        "chat_density": "Comfortable",
        "rounded_corners": 12,
    }
}
for key, default in _defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── RENDER SIDEBAR ─────────────────────────────────────────────────────────────
sidebar_settings = render_sidebar()
st.session_state.sidebar_settings = sidebar_settings

# ── PAGE ROUTING ───────────────────────────────────────────────────────────────
if st.session_state.get("show_analytics", False):
    render_analytics_dashboard()
else:
    render_chat_page()
