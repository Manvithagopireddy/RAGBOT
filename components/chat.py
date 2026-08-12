"""
chat.py — ChatGPT-style chat interface with:
  - Persistent multi-session messages with streaming responses
  - Search Priority: FAISS Knowledge Base → AI General Knowledge
  - Message Actions: Copy, Regenerate, Feedback, Share, Edit
  - Multi-format File Upload (PDF, DOCX, CSV, PPTX, TXT, Images)
  - Suggested follow-up questions
  - Right Side Panel (collapsible) with sources and confidence
  - Welcome screen when empty
"""
# pyright: ignore [missing-import]
import streamlit as st
import datetime
from rag import execute_rag_pipeline
from utils.helpers import parse_related_questions, calculate_confidence_score, generate_chat_title
from src.file_handler import index_uploaded_file, get_file_size_label, get_file_icon
from components.components import render_upload_indicator, render_typing_indicator, render_image_preview
from components.citations import render_citations, render_web_citations
from components.confidence import render_confidence_gauge
from components.home import render_welcome_screen
from src.retriever import retrieve_relevant_chunks
from src.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_UPLOAD_TYPES = ["pdf", "txt", "csv", "docx", "pptx"]
IMAGE_TYPES = ["jpg", "jpeg", "png", "webp", "gif"]


def render_chat_page():
    """Renders the main ChatGPT-style chat interface."""

    db = st.session_state.get("db")
    memory = st.session_state.get("memory")
    chat_store = st.session_state.get("chat_store")
    active_session_id = st.session_state.get("active_session_id")
    messages = st.session_state.get("messages", [])
    sidebar_settings = st.session_state.get("sidebar_settings", {})
    gs = st.session_state.get("global_settings", {})

    # Ensure right panel state exists
    if "show_right_panel" not in st.session_state:
        st.session_state.show_right_panel = True

    # ── CHAT HEADER ──────────────────────────────────────────────
    session_title = "New Chat"
    if chat_store and active_session_id:
        session = chat_store.get_session(active_session_id)
        if session:
            session_title = session.get("title", "New Chat")

    model_name = sidebar_settings.get("model", "gemini-2.5-flash")
    rag_on = sidebar_settings.get("rag_enabled", True)
    web_on = sidebar_settings.get("web_search", False)

    if web_on:
        mode_badge = "🌐 Web Search"
    elif rag_on:
        mode_badge = "📚 RAG ON"
    else:
        mode_badge = "💬 Direct"

    model_display = model_name.replace("gemini-", "Gemini ").replace("-", " ").title()
    show_right_panel = st.session_state.show_right_panel

    # Render Share Modal if active
    if st.session_state.get("show_share_modal", False):
        _render_share_modal(st.session_state.get("share_content", ""))

    # Header section with details toggle
    c_head, c_toggle = st.columns([0.84, 0.16])
    with c_head:
        st.markdown(f"""
        <div class="chat-header">
            <div class="chat-header-title">{session_title}</div>
            <div class="chat-header-model-badge">⚡ {model_display} · {mode_badge}</div>
        </div>
        """, unsafe_allow_html=True)
    with c_toggle:
        toggle_label = "📋 Hide Details" if show_right_panel else "📋 Details"
        if st.button(toggle_label, key="toggle_right_panel_btn", use_container_width=True):
            st.session_state.show_right_panel = not show_right_panel
            st.rerun()

    # ── PERSONA / WEB SEARCH BADGES ───────────────────────────────
    persona = sidebar_settings.get("persona", "")
    if persona:
        persona_short = persona[:50] + "…" if len(persona) > 50 else persona
        st.markdown(f'<div class="persona-badge">🎭 {persona_short}</div>', unsafe_allow_html=True)
    if web_on:
        st.markdown('<div class="web-badge">🌐 Web Search Active</div>', unsafe_allow_html=True)

    # ── SPLIT LAYOUT (MAIN CHAT vs RIGHT DETAILS PANEL) ───────────
    if show_right_panel:
        col_main, col_right = st.columns([0.74, 0.26])
    else:
        col_main = st.container()

    with col_main:
        # ── EDIT MODE ────────────────────────────────────────────────
        edit_mode = st.session_state.get("edit_mode", False)
        edit_idx = st.session_state.get("edit_message_index", None)

        if edit_mode and edit_idx is not None:
            _render_edit_mode(edit_idx, messages, db, memory, chat_store, active_session_id, sidebar_settings)
        else:
            # ── EMPTY STATE: WELCOME SCREEN ───────────────────────────────
            if not messages:
                render_welcome_screen()
            else:
                chat_container = st.container(border=False)
                with chat_container:
                    _render_message_history(messages, chat_store, active_session_id)

            # ── RELATED FOLLOW-UP QUESTIONS ───────────────────────────────
            related = st.session_state.get("related_questions", [])
            if related:
                st.markdown(
                    "<div class='related-questions-label'>💡 Suggested Follow-ups</div>",
                    unsafe_allow_html=True
                )
                rel_cols = st.columns(min(len(related), 3))
                for i, question in enumerate(related):
                    with rel_cols[i % len(rel_cols)]:
                        if st.button(f"➔ {question}", key=f"rel_q_{i}", use_container_width=True):
                            st.session_state.pending_query = question
                            st.session_state.related_questions = []
                            st.rerun()

            # ── CHAT INPUT ────────────────────────────────────────────────
            user_query = None
            if st.session_state.get("pending_query"):
                user_query = st.session_state.pending_query
                st.session_state.pending_query = None
                
                _handle_user_query(
                    user_query, db, memory, chat_store, active_session_id, sidebar_settings, messages
                )

            else:
                prompt = st.chat_input(
                    "Message BotTech…",
                    key="main_chat_input",
                    accept_file="multiple",
                    accept_audio=False,
                )

                if prompt:
                    text_query = getattr(prompt, "text", "")
                    files = getattr(prompt, "files", [])

                    if text_query or files:
                        # Process files (images vs document chunks)
                        for f in files:
                            if f.name.lower().endswith(tuple(IMAGE_TYPES)):
                                img_bytes = f.read()
                                mime = f"image/{f.type.split('/')[-1]}" if f.type else "image/jpeg"
                                st.session_state.pending_image = {"bytes": img_bytes, "mime": mime, "name": f.name}
                            elif f.name.lower().endswith(tuple(SUPPORTED_UPLOAD_TYPES)):
                                already_indexed = any(
                                    idx_f.get("name") == f.name for idx_f in st.session_state.get("uploaded_files", [])
                                )
                                if not already_indexed:
                                    with st.spinner(f"Indexing {f.name}…"):
                                        updated_db = index_uploaded_file(f, st.session_state.get("db"))
                                        st.session_state.db = updated_db
                                        db = updated_db
                                        size_label = get_file_size_label(f)
                                        icon = get_file_icon(f.name)
                                        st.session_state.setdefault("uploaded_files", []).append(
                                            {"name": f.name, "size": size_label, "icon": icon}
                                        )

                        if text_query or st.session_state.get("pending_image"):
                            _handle_user_query(
                                text_query, db, memory, chat_store, active_session_id, sidebar_settings, messages
                            )

            # ── DISCLAIMER ────────────────────────────────────────────────
            st.markdown(
                "<div class='input-disclaimer'>BotTech AI can make mistakes. Always verify important information.</div>",
                unsafe_allow_html=True,
            )

    # RENDER COLLAPSIBLE RIGHT PANEL
    if show_right_panel:
        with col_right:
            from components.right_panel import render_right_panel
            render_right_panel()


@st.dialog("Share Message")
def _render_share_modal(content: str):
    st.markdown("### 🔗 Share Response")
    st.markdown("Copy the response text below:")
    st.text_area("Markdown text:", value=content, height=220)
    st.markdown("---")
    if st.button("Close Modal"):
        st.session_state.show_share_modal = False
        st.rerun()


# ── PRIVATE HELPERS ────────────────────────────────────────────────────────────

def _render_message_history(messages: list, chat_store=None, active_session_id: str = None):
    """Renders all messages with clean per-message action rows."""
    for idx, msg in enumerate(messages):
        role = msg["role"]
        content = msg["content"]
        avatar = "👤" if role == "user" else "🤖"
        message_id = msg.get("message_id", f"msg_{idx}")

        with st.chat_message(role, avatar=avatar):
            # Show attached image if any
            if msg.get("image_bytes") and msg.get("image_mime"):
                render_image_preview(msg["image_bytes"], msg["image_mime"])

            st.markdown(content)

            escaped = content.replace("\\", "\\\\").replace("`", "\\`").replace("'", "\\'")

            if role == "assistant":
                # Display dynamic source indicator
                src_type = msg.get("source_type", "🧠 AI General Knowledge")
                st.markdown(f"""
                <div style="font-size:0.75rem; color:#8e8ea0; margin-top:8px; display:inline-block; 
                            background:rgba(255,255,255,0.04); padding:3px 8px; border-radius:12px; 
                            border:1px solid rgba(255,255,255,0.06);">
                    Source: <strong>{src_type}</strong>
                </div>
                """, unsafe_allow_html=True)
                
                # Response Actions row
                act_cols = st.columns([0.15, 0.08, 0.08, 0.12, 0.3])
                with act_cols[0]:
                    if st.button("🔄 Regen", key=f"regen_{idx}_{message_id[:8]}", help="Regenerate response"):
                        # Truncate messages to this point
                        st.session_state.messages = messages[:idx]
                        if chat_store and active_session_id:
                            all_db = chat_store.get_messages(active_session_id)
                            if len(all_db) > idx:
                                last_ts = all_db[idx]["created_at"]
                                chat_store.delete_messages_from(active_session_id, last_ts)
                        # Re-trigger with prior user prompt
                        user_prompt = messages[idx-1]["content"] if idx > 0 else ""
                        st.session_state.pending_query = user_prompt
                        st.rerun()
                with act_cols[2]:
                    like_lbl = "💚 👍" if msg.get("feedback") == "up" else "👍"
                    if st.button(like_lbl, key=f"up_{idx}_{message_id[:8]}", help="Good response"):
                        if chat_store and message_id:
                            chat_store.update_message_feedback(message_id, "up")
                        st.session_state.messages[idx]["feedback"] = "up"
                        st.rerun()
                with act_cols[3]:
                    dislike_lbl = "💔 👎" if msg.get("feedback") == "down" else "👎"
                    if st.button(dislike_lbl, key=f"dn_{idx}_{message_id[:8]}", help="Bad response"):
                        if chat_store and message_id:
                            chat_store.update_message_feedback(message_id, "down")
                        st.session_state.messages[idx]["feedback"] = "down"
                        st.rerun()
                with act_cols[3]:
                    if st.button("🔗 Share", key=f"share_{idx}_{message_id[:8]}", help="Share this response"):
                        st.session_state.show_share_modal = True
                        st.session_state.share_content = content
                        st.rerun()
                
                # Metadata list
                if msg.get("citations") and src_type == "📄 Knowledge Base":
                    render_citations(msg["citations"])
                if msg.get("web_citations") and src_type == "🌐 Web Search":
                    render_web_citations(msg["web_citations"])
                if msg.get("confidence_score") is not None and src_type == "📄 Knowledge Base":
                    render_confidence_gauge(msg["confidence_score"], msg.get("confidence_desc", ""))

                # Clipboard Copy Row (Javascript)
                st.markdown(f"""
                <div class="msg-actions-container" style="display:flex;align-items:center;gap:6px;margin-top:6px;opacity:0.6;">
                    <button onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{
                        this.innerText='✓ Copied';this.style.color='#10b981';
                        setTimeout(()=>{{this.innerText='📋 Copy';this.style.color='';}},2000);
                    }})" class="msg-action-btn" style="padding: 2px 8px; font-size: 0.72rem; border-radius:4px;">📋 Copy</button>
                </div>
                """, unsafe_allow_html=True)

            else:  # user message — copy + edit in one minimal row
                st.markdown(f"""
                <div class="msg-actions-container" style="display:flex;align-items:center;gap:6px;margin-top:6px;justify-content:flex-end;opacity:0.6;transition:opacity 0.2s;">
                    <button onclick="navigator.clipboard.writeText(`{escaped}`).then(()=>{{
                        this.innerText='✓';this.style.color='#10b981';
                        setTimeout(()=>{{this.innerText='📋';this.style.color='';}},2000);
                    }})" class="msg-action-btn" title="Copy">📋</button>
                </div>
                """, unsafe_allow_html=True)
                
                # Edit prompt button
                _edit_col, _spacer = st.columns([0.15, 0.85])
                with _edit_col:
                    if st.button("✏️ Edit", key=f"edit_{idx}", help="Edit & regenerate",
                                 use_container_width=True):
                        st.session_state.edit_mode = True
                        st.session_state.edit_message_index = idx
                        st.rerun()


def _handle_user_query(
    user_query: str,
    db,
    memory,
    chat_store,
    active_session_id: str,
    sidebar_settings: dict,
    messages: list,
):
    """Processes a new user message and streams the response with fallback priority routing."""

    pending_image = st.session_state.get("pending_image")
    image_bytes = pending_image["bytes"] if pending_image else None
    image_mime = pending_image["mime"] if pending_image else "image/jpeg"

    # Add user message to state
    user_msg = {"role": "user", "content": user_query}
    if pending_image:
        user_msg["image_bytes"] = image_bytes
        user_msg["image_mime"] = image_mime
    st.session_state.messages.append(user_msg)
    memory.add_user_message(user_query)

    # Persist to DB
    if chat_store and active_session_id:
        msg_id = chat_store.add_message(active_session_id, "user", user_query)
        st.session_state.messages[-1]["message_id"] = msg_id

    # Auto-title after first message
    if chat_store and active_session_id:
        session = chat_store.get_session(active_session_id)
        if session and session.get("title") == "New Chat":
            title = generate_chat_title(user_query)
            chat_store.rename_session(active_session_id, title)

    # Render user bubble
    with st.chat_message("user", avatar="👤"):
        if pending_image:
            render_image_preview(image_bytes, image_mime)
        st.markdown(user_query)

    st.session_state.pending_image = None

    # Stream response
    with st.chat_message("assistant", avatar="🤖"):
        response_placeholder = st.empty()
        render_typing_indicator()

        rag_enabled = sidebar_settings.get("rag_enabled", True)
        retriever_k = sidebar_settings.get("retriever_k", 4)
        temperature = sidebar_settings.get("temperature", 0.7)
        model = sidebar_settings.get("model", "gemini-2.5-flash")
        persona = sidebar_settings.get("persona", "")
        
        similarity_threshold = st.session_state.get("similarity_threshold", 0.4)
        gs = st.session_state.get("global_settings", {})
        web_on = sidebar_settings.get("web_search", False)

        # ── ROUTING DECISION ──────────────────────────────────────
        source_type = "🧠 AI General Knowledge"
        best_similarity = 0.0
        citations = []
        avg_similarity = 0.0

        # Step 1: Check Knowledge Base RAG
        if rag_enabled and db is not None:
            # Quickly retrieve chunks to check similarity score
            results = retrieve_relevant_chunks(db, user_query, k=retriever_k)
            if results:
                best_similarity = max(score for doc, score in results)
                if best_similarity >= similarity_threshold:
                    source_type = "📄 Knowledge Base"

        # Step 2: Route to Web Search if KB didn't match and web search is enabled
        if source_type == "🧠 AI General Knowledge" and web_on:
            source_type = "🌐 Web Search"
        
        # ── PIPELINE INITIATION ───────────────────────────────────
        web_citations = []
        if source_type == "📄 Knowledge Base":
            token_generator, citations, avg_similarity = execute_rag_pipeline(
                db,
                memory,
                user_query,
                temperature=temperature,
                retriever_k=retriever_k,
                model=model,
                persona=persona,
                image_bytes=image_bytes,
                image_mime=image_mime,
                web_search=False,
            )
        elif source_type == "🌐 Web Search":
            token_generator, citations, avg_similarity = execute_rag_pipeline(
                None,
                memory,
                user_query,
                temperature=temperature,
                retriever_k=retriever_k,
                model=model,
                persona=persona,
                image_bytes=image_bytes,
                image_mime=image_mime,
                web_search=True,
                web_citations=web_citations,
            )
        else:
            token_generator, citations, avg_similarity = execute_rag_pipeline(
                None,  # Pure LLM (no DB context)
                memory,
                user_query,
                temperature=temperature,
                retriever_k=retriever_k,
                model=model,
                persona=persona,
                image_bytes=image_bytes,
                image_mime=image_mime,
                web_search=False,
            )

        # Stream tokens
        full_response = ""
        for token in token_generator:
            full_response += token
            if gs.get("streaming_enabled", True):
                visible = full_response
                if "<related>" in visible:
                    visible = visible.split("<related>")[0]
                response_placeholder.markdown(visible + "▌")

        # Finalize
        cleaned_text, related_questions = parse_related_questions(full_response)
        response_placeholder.markdown(cleaned_text)

        conf_score, conf_desc = calculate_confidence_score(avg_similarity)

        # Render metadata underneath
        st.markdown(f"""
        <div style="font-size:0.75rem; color:#8e8ea0; margin-top:8px; display:inline-block; 
                    background:rgba(255,255,255,0.04); padding:3px 8px; border-radius:12px; 
                    border:1px solid rgba(255,255,255,0.06);">
            Source: <strong>{source_type}</strong>
        </div>
        """, unsafe_allow_html=True)

        if citations and source_type == "📄 Knowledge Base":
            render_citations(citations)
        if avg_similarity > 0.0 and source_type == "📄 Knowledge Base":
            render_confidence_gauge(conf_score, conf_desc)

        # Save to state + DB
        assistant_msg = {
            "role": "assistant",
            "content": cleaned_text,
            "citations": citations if source_type == "📄 Knowledge Base" else [],
            "web_citations": web_citations if source_type == "🌐 Web Search" else [],
            "confidence_score": conf_score if source_type == "📄 Knowledge Base" else None,
            "confidence_desc": conf_desc if source_type == "📄 Knowledge Base" else "",
            "source_type": source_type,
            "feedback": None,
        }
        st.session_state.messages.append(assistant_msg)
        memory.add_assistant_message(cleaned_text)

        if chat_store and active_session_id:
            db_citations = citations if source_type == "📄 Knowledge Base" else (web_citations if source_type == "🌐 Web Search" else [])
            msg_id = chat_store.add_message(
                active_session_id,
                "assistant",
                cleaned_text,
                citations=db_citations,
                confidence_score=conf_score if source_type == "📄 Knowledge Base" else None,
                confidence_desc=conf_desc if source_type == "📄 Knowledge Base" else "",
            )
            # Update database record with selected source type
            with chat_store._connect() as conn:
                conn.execute(
                    "UPDATE messages SET confidence_desc = ? WHERE message_id = ?",
                    (f"source:{source_type}", msg_id)
                )
                conn.commit()
            st.session_state.messages[-1]["message_id"] = msg_id

        st.session_state.related_questions = related_questions

    st.rerun()



def _render_edit_mode(edit_idx: int, messages: list, db, memory, chat_store,
                      active_session_id, sidebar_settings):
    """Renders inline edit input for a user message and regenerates from that point."""
    original_query = messages[edit_idx]["content"]

    st.markdown("""
    <div style="background:rgba(99,102,241,0.07); border:1px solid rgba(99,102,241,0.2);
                border-radius:12px; padding:16px; margin-bottom:16px;">
        <div style="font-size:0.8rem; color:#a5b4fc; font-weight:600; margin-bottom:8px;">
            ✏️ Edit Message — response will regenerate from this point
        </div>
    """, unsafe_allow_html=True)

    edited_query = st.text_area(
        "Edit your message:",
        value=original_query,
        key="edit_text_area",
        label_visibility="collapsed",
        height=100,
    )

    col_save, col_cancel = st.columns([0.25, 0.75])
    with col_save:
        save_clicked = st.button("🔄 Regenerate", type="primary", use_container_width=True)
    with col_cancel:
        if st.button("✗ Cancel", use_container_width=True):
            st.session_state.edit_mode = False
            st.session_state.edit_message_index = None
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    if save_clicked:
        truncated_messages = messages[:edit_idx]
        st.session_state.messages = truncated_messages

        if chat_store and active_session_id:
            all_db_msgs = chat_store.get_messages(active_session_id)
            user_msg_count = sum(1 for m in messages[:edit_idx] if m["role"] == "user")
            actual_db_user_msgs = [m for m in all_db_msgs if m["role"] == "user"]
            if user_msg_count < len(actual_db_user_msgs):
                cutoff_ts = actual_db_user_msgs[user_msg_count]["created_at"]
                chat_store.delete_messages_from(active_session_id, cutoff_ts)

        from chat_manager import ChatMemory
        new_memory = ChatMemory()
        for m in truncated_messages:
            if m["role"] == "user":
                new_memory.add_user_message(m["content"])
            else:
                new_memory.add_assistant_message(m["content"])
        st.session_state.memory = new_memory

        st.session_state.edit_mode = False
        st.session_state.edit_message_index = None
        st.session_state.pending_query = edited_query
        st.rerun()

    # Show history above edit box
    if messages[:edit_idx]:
        st.markdown("---")
        st.markdown(
            "<div style='color:#6e6e80; font-size:0.78rem; margin-bottom:8px;'>Conversation up to this point:</div>",
            unsafe_allow_html=True
        )
        preview_container = st.container(height=280, border=False)
        with preview_container:
            for msg in messages[:edit_idx]:
                avatar = "👤" if msg["role"] == "user" else "🤖"
                with st.chat_message(msg["role"], avatar=avatar):
                    st.markdown(msg["content"])
