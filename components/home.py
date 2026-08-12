"""
home.py — Enhanced ChatGPT-style welcome screen with animated logo,
          capability cards, and smart starter prompts.
"""
# pyright: ignore [missing-import]
import streamlit as st


def render_welcome_screen():
    """
    Renders the centered welcome screen shown when a session has no messages.
    Features: animated floating logo, gradient title, capability cards, starter prompts.
    """
    st.markdown("""
    <div class="welcome-container">
        <div class="welcome-logo">🤖</div>
        <div class="welcome-title">How can I help you?</div>
        <div class="welcome-subtitle">
            Ask me anything — code, writing, math, analysis, research, and more.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── SUGGESTION CARDS ─────────────────────────────────────────
    suggestions = [
        {
            "icon": "💻",
            "title": "Write & Debug Code",
            "desc": "Python, JS, SQL, React — any language, any problem.",
            "query": "Write a Python FastAPI server with JWT authentication and CRUD endpoints for a users table.",
            "key": "sg_code",
        },
        {
            "icon": "📝",
            "title": "Write & Edit",
            "desc": "Emails, essays, reports, marketing copy, or creative writing.",
            "query": "Write a compelling LinkedIn post about launching a new AI product for a startup.",
            "key": "sg_write",
        },
        {
            "icon": "🧠",
            "title": "Explain Concepts",
            "desc": "Break down complex topics simply and clearly.",
            "query": "Explain how large language models work — from tokens to transformers to RLHF — in simple terms.",
            "key": "sg_explain",
        },
        {
            "icon": "📊",
            "title": "Analyze & Summarize",
            "desc": "Summarize documents, compare ideas, extract insights.",
            "query": "What are the key differences between LangChain, LlamaIndex, and Haystack for building RAG systems?",
            "key": "sg_analyze",
        },
        {
            "icon": "🔢",
            "title": "Math & Science",
            "desc": "Solve equations, proofs, statistics, or physics problems.",
            "query": "Solve and explain the derivation of the softmax function gradient used in neural network backpropagation.",
            "key": "sg_math",
        },
        {
            "icon": "🎨",
            "title": "Creative Tasks",
            "desc": "Stories, poems, brainstorming, and creative projects.",
            "query": "Write a short science fiction story set in 2150 where AI and humans co-govern Earth.",
            "key": "sg_creative",
        },
    ]

    col1, col2, col3 = st.columns(3)
    cols = [col1, col2, col3, col1, col2, col3]

    for i, s in enumerate(suggestions):
        with cols[i]:
            st.markdown(f"""
            <div class="suggestion-card">
                <div class="suggestion-card-title">{s['icon']} {s['title']}</div>
                <div class="suggestion-card-desc">{s['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"→ {s['title']}", key=s["key"], use_container_width=True):
                st.session_state.pending_query = s["query"]
                st.rerun()

    # ── CAPABILITIES ROW ──────────────────────────────────────────
    st.markdown("""
    <div style="margin-top: 32px; display: flex; justify-content: center; gap: 20px;
                flex-wrap: wrap; max-width: 700px; margin-left: auto; margin-right: auto;
                animation: fadeInUp 0.5s ease-out 0.4s both;">
        <div style="display:flex;align-items:center;gap:6px;color:#6e6e80;font-size:0.78rem;">
            🌐 <span>Web Search</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;color:#6e6e80;font-size:0.78rem;">
            🖼️ <span>Image Understanding</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;color:#6e6e80;font-size:0.78rem;">
            📄 <span>Document Analysis</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;color:#6e6e80;font-size:0.78rem;">
            🎤 <span>Voice Input</span>
        </div>
        <div style="display:flex;align-items:center;gap:6px;color:#6e6e80;font-size:0.78rem;">
            💻 <span>Code Execution Help</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_home_page():
    """Legacy wrapper kept for backward compat."""
    render_welcome_screen()
