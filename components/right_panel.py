"""
right_panel.py — Collapsible Right Side Panel.
Contains:
  - Sources used in the last response (Knowledge Base or Web Search links)
  - Confidence metric (visual gauge/percentage)
  - Conversation details (ID, Message count, creation timestamp)
  - Uploaded files in the current session
  - Knowledge Base metadata (Vector store index, chunk count, model)
  - AI Persona details (active system instructions)
  - Current session settings summary
  - Mini Analytics snapshot (total chats, total messages, positive feedback ratio)
"""
# pyright: ignore [missing-import]
import streamlit as st
import datetime
from src.logger import get_logger

logger = get_logger(__name__)


def render_right_panel():
    """Renders the collateral sidebar details for the active conversation."""
    
    st.markdown("""
    <div style="padding: 14px 16px 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); 
                background: rgba(15, 17, 26, 0.4); backdrop-filter: blur(10px);">
        <div style="font-size: 1.1rem; font-weight: 700; color: #ececec; font-family: 'Outfit', sans-serif;">
            📋 Chat Details
        </div>
    </div>
    <div style="height: 12px;"></div>
    """, unsafe_allow_html=True)
    
    messages = st.session_state.get("messages", [])
    chat_store = st.session_state.get("chat_store")
    active_session_id = st.session_state.get("active_session_id")
    sidebar_settings = st.session_state.get("sidebar_settings", {})
    gs = st.session_state.get("global_settings", {})
    
    # Fetch last assistant message for Sources and Confidence
    last_assistant_msg = None
    if messages:
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                last_assistant_msg = msg
                break

    # 1. SOURCES & CONFIDENCE CARD
    if last_assistant_msg:
        citations = last_assistant_msg.get("citations", [])
        web_citations = last_assistant_msg.get("web_citations", [])
        conf_score = last_assistant_msg.get("confidence_score")
        conf_desc = last_assistant_msg.get("confidence_desc", "")
        
        # Determine Source Type
        if citations:
            source_type_label = "📄 Knowledge Base"
            source_color = "#38bdf8"
        elif web_citations:
            source_type_label = "🌐 Web Search"
            source_color = "#34d399"
        else:
            source_type_label = "🧠 AI General Knowledge"
            source_color = "#a78bfa"
            
        st.markdown(f"""
        <div class="glass-card" style="margin: 0 12px 14px 12px; border-left: 4px solid {source_color};">
            <div style="font-size: 0.72rem; color: #8e8ea0; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Source Type</div>
            <div style="font-size: 0.95rem; font-weight: 700; color: #ececec; margin-top: 2px;">{source_type_label}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Confidence
        if conf_score is not None:
            dot_color = "#10b981" if conf_score >= 85 else "#f59e0b" if conf_score >= 65 else "#ef4444"
            st.markdown(f"""
            <div class="glass-card" style="margin: 0 12px 14px 12px;">
                <div style="font-size: 0.72rem; color: #8e8ea0; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">Confidence Score</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 6px;">
                    <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: {dot_color}; box-shadow: 0 0 6px {dot_color};"></span>
                    <span style="font-size: 1.1rem; font-weight: 700; color: #ececec;">{conf_score}%</span>
                </div>
                <div style="font-size: 0.76rem; color: #6e6e80; margin-top: 4px;">{conf_desc}</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Sources List
        if citations or web_citations:
            with st.expander("📚 Sources Retrieved", expanded=True):
                if citations:
                    for i, cite in enumerate(citations[:4]):
                        st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); 
                                    border-radius: 8px; padding: 8px; margin-bottom: 6px; font-size: 0.78rem;">
                            <div style="font-weight: 600; color: #38bdf8;">[{i+1}] {cite['source']} (Page {cite['page']})</div>
                            <div style="color: #8e8ea0; margin-top: 3px; font-style: italic; line-height: 1.3;">
                                "{cite.get('snippet', '')[:120]}..."
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                if web_citations:
                    for i, cite in enumerate(web_citations[:4]):
                        st.markdown(f"""
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); 
                                    border-radius: 8px; padding: 8px; margin-bottom: 6px; font-size: 0.78rem;">
                            <div style="font-weight: 600; color: #34d399;">
                                <a href="{cite.get('uri', '#')}" target="_blank" style="color: #34d399; text-decoration: none;">🔗 {cite.get('title', 'Web Source')[:45]}</a>
                            </div>
                            <div style="color: #6e6e80; font-size: 0.7rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px;">
                                {cite.get('uri', '')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align: center; padding: 24px 12px; color: #6e6e80; font-size: 0.8rem; font-style: italic;">
            No message generated yet. Send a query to see metadata.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='padding: 0 12px;'><hr style='border:none; border-top: 1px solid rgba(255,255,255,0.07); margin: 8px 0;'></div>", unsafe_allow_html=True)

    # 2. CONVERSATION DETAILS
    with st.expander("💬 Conversation Details", expanded=False):
        if chat_store and active_session_id:
            sess = chat_store.get_session(active_session_id)
            if sess:
                msg_count = chat_store.get_message_count(active_session_id)
                # Formatted dates
                try:
                    created_dt = datetime.datetime.fromisoformat(sess["created_at"])
                    created_str = created_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    created_str = sess["created_at"]
                
                st.markdown(f"""
                <div style="font-size: 0.8rem; line-height: 1.6; color: #8e8ea0;">
                    <div style="display:flex; justify-content:space-between;">
                        <span>Session Title:</span>
                        <strong style="color:#ececec;">{sess.get('title')}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span>Messages:</span>
                        <strong style="color:#ececec;">{msg_count}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span>Model Active:</span>
                        <strong style="color:#ececec;">{sess.get('model', 'gemini-2.5-flash').replace('gemini-','Gemini ')}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between;">
                        <span>Created At:</span>
                        <strong style="color:#ececec;">{created_str}</strong>
                    </div>
                    <div style="font-size:0.65rem; color:#4a4a5a; margin-top:8px; overflow:hidden; text-overflow:ellipsis;">
                        ID: {active_session_id}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # 3. UPLOADED FILES IN SESSION
    with st.expander("📎 Uploaded Files in Session", expanded=False):
        uploaded_files = st.session_state.get("uploaded_files", [])
        if not uploaded_files:
            st.markdown("<div style='font-size:0.78rem; color:#6e6e80; font-style:italic;'>No files uploaded in this session yet.</div>", unsafe_allow_html=True)
        else:
            for f in uploaded_files:
                st.markdown(f"""
                <div class="file-pill" style="display:flex; align-items:center; gap:8px; margin-bottom:5px; width:100%; border-radius:8px;">
                    <span>{f.get('icon', '📎')}</span>
                    <div style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:0.75rem;">{f.get('name')}</div>
                    <span style="color:#6e6e80; font-size:0.68rem;">({f.get('size')})</span>
                </div>
                """, unsafe_allow_html=True)

    # 4. KNOWLEDGE BASE METADATA
    with st.expander("📚 Knowledge Base Info", expanded=False):
        db = st.session_state.get("db")
        db_status = "🟢 Vector Store Loaded" if db is not None else "🔴 Vector Store Empty/Offline"
        
        # Check chunk sizes
        import os
        from config.settings import VECTOR_STORE_DIR
        index_size_mb = 0.0
        faiss_file = VECTOR_STORE_DIR / "index.faiss"
        if faiss_file.exists():
            index_size_mb = os.path.getsize(str(faiss_file)) / (1024 * 1024)
            
        st.markdown(f"""
        <div style="font-size: 0.8rem; line-height: 1.6; color: #8e8ea0;">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                <span>DB Status:</span>
                <strong style="color:#10b981;">{db_status}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Embeddings:</span>
                <strong style="color:#ececec;">MiniLM-L6-v2</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>FAISS Index Size:</span>
                <strong style="color:#ececec;">{index_size_mb:.2f} MB</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Chunk Size:</span>
                <strong style="color:#ececec;">800 chars</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Chunk Overlap:</span>
                <strong style="color:#ececec;">150 chars</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 5. AI PERSONA DETAILS
    with st.expander("🎭 AI Persona Instructions", expanded=False):
        persona = sidebar_settings.get("persona", "")
        if not persona:
            st.markdown("<div style='font-size:0.78rem; color:#6e6e80; font-style:italic;'>No active system persona (Default BotTech).</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(168, 85, 247, 0.05); border: 1px solid rgba(168, 85, 247, 0.15); 
                        border-radius: 8px; padding: 10px; font-size: 0.76rem; color: #c084fc; max-height: 150px; overflow-y: auto; line-height: 1.4;">
                {persona}
            </div>
            """, unsafe_allow_html=True)

    # 6. ACTIVE SETTINGS SUMMARY
    with st.expander("⚙️ Parameters Summary", expanded=False):
        rag_on = "Enabled" if sidebar_settings.get("rag_enabled", True) else "Disabled"
        web_on = "Enabled" if sidebar_settings.get("web_search", False) else "Disabled"
        hybrid_on = "Enabled" if gs.get("hybrid_search", True) else "Disabled"
        
        st.markdown(f"""
        <div style="font-size: 0.8rem; line-height: 1.6; color: #8e8ea0;">
            <div style="display:flex; justify-content:space-between;">
                <span>Temperature:</span>
                <strong style="color:#ececec;">{sidebar_settings.get('temperature', 0.7)}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Top P:</span>
                <strong style="color:#ececec;">{gs.get('top_p', 0.95)}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Max Tokens:</span>
                <strong style="color:#ececec;">{gs.get('max_tokens', 4096)}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Doc Retrieval RAG:</span>
                <strong style="color:#ececec;">{rag_on}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Web Search Grounding:</span>
                <strong style="color:#ececec;">{web_on}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Hybrid Fallback Routing:</span>
                <strong style="color:#ececec;">{hybrid_on}</strong>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span>Top-K Chunks:</span>
                <strong style="color:#ececec;">{sidebar_settings.get('retriever_k', 4)}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 7. ANALYTICS MINI SNAPSHOT
    with st.expander("📈 Analytics Snapshot", expanded=False):
        if chat_store:
            analytics_data = chat_store.get_analytics()
            t_sessions = analytics_data.get("total_sessions", 0)
            t_messages = analytics_data.get("total_messages", 0)
            t_up = analytics_data.get("thumbs_up", 0)
            t_down = analytics_data.get("thumbs_down", 0)
            t_fb = t_up + t_down
            satisfaction = int((t_up / t_fb) * 100) if t_fb > 0 else 100
            
            st.markdown(f"""
            <div style="font-size: 0.8rem; line-height: 1.6; color: #8e8ea0;">
                <div style="display:flex; justify-content:space-between;">
                    <span>Total Conversations:</span>
                    <strong style="color:#ececec;">{t_sessions}</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Total Messages Sent:</span>
                    <strong style="color:#ececec;">{t_messages}</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Response Feedback:</span>
                    <strong style="color:#ececec;">👍 {t_up}  👎 {t_down}</strong>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span>Helpful Ratio:</span>
                    <strong style="color:#10b981;">{satisfaction}%</strong>
                </div>
            </div>
            """, unsafe_allow_html=True)
