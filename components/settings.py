import streamlit as st
from config.settings import AVAILABLE_MODELS
from src.logger import get_logger

logger = get_logger(__name__)

PRESET_PERSONAS = {
    "🧠 General Assistant": "You are BotTech AI, a helpful, intelligent, and general-purpose AI assistant. Answer the user's questions clearly, accurately, and thoroughly using Markdown formatting.",
    "💻 Software Engineer": "You are a Senior Software Engineer. Explain programming concepts, review code, debug issues, and write clean, typed, modular, and production-ready code with appropriate comments.",
    "🤖 AI Engineer": "You are an AI Engineer. Assist the user with large language models, retrieval-augmented generation (RAG), vector databases, agentic workflows, embeddings, and prompt engineering.",
    "📊 Data Engineer": "You are a Senior Data Engineer. Assist with data modeling, database design, SQL queries, data warehousing, ETL/ELT pipelines, streaming data, and big data technologies.",
    "🎓 Teacher": "You are a patient and empathetic teacher. Break down complex topics into simple steps, using analogies, examples, and structured explanations suitable for a student. Ask questions to check understanding.",
    "🔬 Researcher": "You are an academic researcher. Help the user draft papers, summarize literature, design research methodologies, analyze data, and formulate scientific hypotheses.",
    "📈 Business Analyst": "You are a Business Analyst. Help analyze business processes, gather technical requirements, formulate user stories, create business cases, and analyze business intelligence datasets.",
    "📝 Technical Writer": "You are a professional Technical Writer. Assist in creating clean documentation, API reference guides, user tutorials, readme files, and architectural designs.",
    "💼 Career Coach": "You are a Career Coach. Help the user optimize their resume, write cover letters, prepare for technical and behavioral interviews, and plan career moves.",
    "⚙️ Custom...": "__custom__",
}

@st.dialog("Settings")
def render_settings_modal():
    """Renders the advanced settings modal (General, AI Model, Search, Appearance, Archived Chats)."""
    
    chat_store = st.session_state.get("chat_store")
    active_session_id = st.session_state.get("active_session_id")
    sidebar_settings = st.session_state.get("sidebar_settings", {})
    
    # Ensure global settings exist in session state
    if "global_settings" not in st.session_state:
        st.session_state.global_settings = {
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
    
    gs = st.session_state.global_settings
    
    tab_gen, tab_ai, tab_search, tab_app, tab_archive = st.tabs([
        "⚙️ General", "🤖 AI Config", "🔍 Search", "🎨 Appearance", "📦 Archived Chats"
    ])
    
    # ── GENERAL TAB ──────────────────────────────────────────
    with tab_gen:
        st.markdown("### General Preferences")
        
        selected_theme = st.selectbox(
            "Theme Mode",
            ["Dark", "Light"],
            index=0 if gs.get("theme", "Dark") == "Dark" else 1,
            help="Choose the base theme for the application."
        )
        
        selected_font = st.selectbox(
            "Font Size",
            ["Small", "Medium", "Large"],
            index=["Small", "Medium", "Large"].index(gs.get("font_size", "Medium")),
            help="Change the conversation base font size."
        )
        
        sidebar_w = st.slider(
            "Sidebar Width (px)",
            min_value=200, max_value=400, value=gs.get("sidebar_width", 260), step=10,
            help="Drag to adjust the left navigation sidebar width."
        )
        
        compact = st.toggle(
            "Compact Sidebar List",
            value=gs.get("compact_mode", False),
            help="Enable compact padding for chat items in the history list."
        )
        
        anims = st.toggle(
            "Enable UI Animations",
            value=gs.get("animations_enabled", True),
            help="Toggle micro-interactions, page slides, and background effects."
        )
        
        st.markdown("---")
        st.markdown("#### Danger Zone")
        if st.button("🗑️ Delete All Conversations", use_container_width=True, type="primary", key="clear_all_settings_btn"):
            if chat_store:
                chat_store.clear_all_sessions()
                from components.sidebar import _start_new_chat
                _start_new_chat()
    
    # ── AI MODEL TAB ─────────────────────────────────────────
    with tab_ai:
        st.markdown("### AI Model parameters")
        
        current_model = sidebar_settings.get("model", "gemini-2.5-flash")
        model_labels = list(AVAILABLE_MODELS.keys())
        model_index = 0
        for i, val in enumerate(AVAILABLE_MODELS.values()):
            if val == current_model:
                model_index = i
                break
                
        selected_label = st.selectbox(
            "Model",
            model_labels,
            index=model_index,
            help="Choose which Gemini model powers your chat."
        )
        new_model = AVAILABLE_MODELS[selected_label]
        
        temp = st.slider(
            "Temperature",
            min_value=0.0, max_value=1.0, value=sidebar_settings.get("temperature", 0.7), step=0.05,
            help="Lower = more precise & factual. Higher = more creative & varied."
        )
        
        top_p = st.slider(
            "Top P",
            min_value=0.0, max_value=1.0, value=gs.get("top_p", 0.95), step=0.05,
            help="Nucleus sampling threshold."
        )
        
        max_tok = st.slider(
            "Max Response Tokens",
            min_value=256, max_value=8192, value=gs.get("max_tokens", 4096), step=128,
            help="Limit the length of generated answers."
        )
        
        stream_on = st.toggle(
            "Enable Streaming Responses",
            value=gs.get("streaming_enabled", True),
            help="Stream back response tokens in real-time as they generate."
        )
        
        st.markdown("#### Persona / System Instructions")
        persona_choice = st.selectbox(
            "Choose a persona for this chat:",
            list(PRESET_PERSONAS.keys()),
            index=0,
        )

        persona_text = st.session_state.get("persona_text", "")
        if persona_choice == "Custom...":
            persona_text = st.text_area(
                "Custom system instruction prompt:",
                value=persona_text,
                placeholder="You are a helpful assistant...",
                height=100,
            )
        elif PRESET_PERSONAS[persona_choice]:
            persona_text = PRESET_PERSONAS[persona_choice]
        else:
            persona_text = ""
            
        st.session_state.persona_text = persona_text
        
    # ── SEARCH / RETRIEVAL TAB ───────────────────────────────
    with tab_search:
        st.markdown("### Search & Hybrid Logic")
        
        rag_enabled = st.toggle(
            "📚 Document RAG (Knowledge Base)",
            value=sidebar_settings.get("rag_enabled", True),
            help="Query FAISS vector database for uploaded documents."
        )
        
        retriever_k = st.slider(
            "Context Chunks (Top-K)",
            min_value=1, max_value=12, value=sidebar_settings.get("retriever_k", 4), step=1,
            help="Number of document chunks retrieved per query."
        )
        
        similarity_threshold = st.slider(
            "Relevance Similarity Threshold",
            min_value=0.0, max_value=1.0, value=st.session_state.get("similarity_threshold", 0.4), step=0.05,
            help="Minimum vector similarity score required to answer from documents (higher is stricter)."
        )
        st.session_state.similarity_threshold = similarity_threshold
        
        web_search_enabled = st.toggle(
            "🌐 Web Search Grounding",
            value=sidebar_settings.get("web_search", False),
            help="Enable internet search via Google grounding when no relevant document exists."
        )
        
        hybrid_fallback = st.toggle(
            "🔄 Hybrid Fallback Mode",
            value=gs.get("hybrid_search", True),
            help="Automatically route: Search Docs -> Fallback to Web Search -> Fallback to General AI knowledge."
        )
        
    # ── APPEARANCE TAB ───────────────────────────────────────
    with tab_app:
        st.markdown("### Visual Styles & Branding")
        
        accent_color = st.color_picker(
            "Accent Color",
            value=gs.get("accent_color", "#6366f1"),
            help="Customize the primary theme color (links, highlights, sliders)."
        )
        
        density = st.selectbox(
            "Chat Density",
            ["Comfortable", "Compact"],
            index=["Comfortable", "Compact"].index(gs.get("chat_density", "Comfortable")),
            help="Adjust padding and spacings in the conversation screen."
        )
        
        rounded = st.slider(
            "UI Rounded Corners (px)",
            min_value=0, max_value=24, value=gs.get("rounded_corners", 12), step=2,
            help="Adjust border radius of cards, buttons, and message bubbles."
        )
        
    # ── ARCHIVED CHATS TAB ───────────────────────────────────
    with tab_archive:
        st.markdown("### Archived Conversations")
        st.markdown("View and restore your archived chats here.")
        
        if chat_store:
            archived = chat_store.get_archived_sessions()
            if not archived:
                st.info("No conversations archived.")
            else:
                for a_sess in archived:
                    a_sid = a_sess["session_id"]
                    a_title = a_sess.get("title", "Untitled Chat")
                    
                    col_title, col_rest, col_del = st.columns([0.6, 0.2, 0.2])
                    with col_title:
                        st.markdown(f"**📄 {a_title}**\n*(Archived)*")
                    with col_rest:
                        if st.button("Restore", key=f"restore_{a_sid}", use_container_width=True):
                            chat_store.toggle_session_archive(a_sid)
                            st.success("Chat restored!")
                            st.rerun()
                    with col_del:
                        if st.button("Delete", key=f"pdel_{a_sid}", type="primary", use_container_width=True):
                            chat_store.delete_session(a_sid)
                            st.success("Chat deleted permanently!")
                            st.rerun()

    # Save logic
    if st.button("Apply Settings", use_container_width=True, type="primary", key="save_settings_modal_btn"):
        # Save to global settings
        st.session_state.global_settings = {
            "theme": selected_theme,
            "font_size": selected_font,
            "sidebar_width": sidebar_w,
            "compact_mode": compact,
            "animations_enabled": anims,
            "top_p": top_p,
            "max_tokens": max_tok,
            "streaming_enabled": stream_on,
            "hybrid_search": hybrid_fallback,
            "accent_color": accent_color,
            "chat_density": density,
            "rounded_corners": rounded,
        }
        
        # Save to active session settings
        st.session_state.sidebar_settings = {
            "model": new_model,
            "temperature": temp,
            "retriever_k": retriever_k,
            "rag_enabled": rag_enabled,
            "web_search": web_search_enabled,
            "persona": persona_text,
        }
        
        if chat_store and active_session_id:
            chat_store.update_session_settings(
                active_session_id,
                temp, retriever_k, rag_enabled,
                model=new_model,
                persona=persona_text,
                web_search=web_search_enabled,
            )
        st.rerun()
