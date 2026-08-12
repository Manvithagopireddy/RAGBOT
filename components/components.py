"""
components.py — Reusable UI components for BotTech AI.
ALL JavaScript is injected inside a hidden div so it never renders as visible content.
"""
# pyright: ignore [missing-import]
import streamlit as st
from typing import List, Dict, Any


def inject_custom_css(css_path: str):
    """Loads and injects local CSS file into Streamlit page, along with dynamic variables."""
    # Ensure global settings exist
    gs = st.session_state.get("global_settings", {
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
    })
    accent_color = gs.get("accent_color", "#6366f1")
    font_size_label = gs.get("font_size", "Medium")
    rounded_corners = gs.get("rounded_corners", 12)
    animations = gs.get("animations_enabled", True)
    density = gs.get("chat_density", "Comfortable")
    theme = gs.get("theme", "Dark")
    
    font_sizes = {
        "Small": "13px",
        "Medium": "15px",
        "Large": "17px"
    }
    fs = font_sizes.get(font_size_label, "15px")
    padding = "16px 22px" if density == "Comfortable" else "8px 14px"
    gap = "12px" if density == "Comfortable" else "6px"
    duration = "0.3s" if animations else "0s"
    drift_duration = "20s" if animations else "0s"
    
    # Check Light Theme adjustments
    if theme == "Light":
        bg_grad = "linear-gradient(145deg, #f7f9fc 0%, #eef2f7 50%, #e2e8f0 100%)"
        text_color = "#1e293b"
        card_bg = "rgba(240, 244, 250, 0.85)"
        card_border = "rgba(0, 0, 0, 0.08)"
        sidebar_bg = "#f1f5f9"
        sidebar_border = "rgba(0, 0, 0, 0.06)"
        avatar_bg = "#ffffff"
        avatar_border = "rgba(0, 0, 0, 0.1)"
    else: # Dark Theme (default)
        bg_grad = "linear-gradient(145deg, #0f111a 0%, #171026 50%, #111a22 100%)"
        text_color = "#ececec"
        card_bg = "rgba(30, 41, 59, 0.6)"
        card_border = "rgba(255, 255, 255, 0.08)"
        sidebar_bg = "#171717"
        sidebar_border = "rgba(255, 255, 255, 0.06)"
        avatar_bg = "#ffffff"
        avatar_border = "rgba(255, 255, 255, 0.08)"
        
    st.markdown(f"""
    <style>
        :root {{
            --primary-color: {accent_color} !important;
            --base-font-size: {fs} !important;
            --border-radius: {rounded_corners}px !important;
            --chat-padding: {padding} !important;
            --chat-gap: {gap} !important;
            --anim-duration: {duration} !important;
            --drift-duration: {drift_duration} !important;
            --bg-gradient: {bg_grad} !important;
            --base-text-color: {text_color} !important;
            --card-bg-color: {card_bg} !important;
            --card-border-color: {card_border} !important;
            --sidebar-bg-color: {sidebar_bg} !important;
            --sidebar-border-color: {sidebar_border} !important;
            --avatar-bg-color: {avatar_bg} !important;
            --avatar-border-color: {avatar_border} !important;
        }}
    </style>
    """, unsafe_allow_html=True)
    
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading styling file: {e}")


def inject_all_js():
    """
    Injects ALL JavaScript (code block enhancer + keyboard shortcuts + voice input)
    in a single hidden div so nothing renders as visible content.
    Must be called ONCE at app startup in app.py.
    """
    st.markdown("""
    <div id="bottech-js-root" style="display:none;height:0;overflow:hidden;position:absolute;left:-9999px;">
    <script>
    (function() {
        /* ── CODE BLOCK ENHANCER ── */
        function enhanceCodeBlocks() {
            document.querySelectorAll('pre').forEach(function(pre) {
                if (pre.dataset.enhanced) return;
                pre.dataset.enhanced = '1';
                var code = pre.querySelector('code');
                var lang = 'code';
                if (code) {
                    var cls = code.className || '';
                    var m = cls.match(/language-([\\w+-]+)/);
                    if (m) lang = m[1];
                }
                var hdr = document.createElement('div');
                hdr.style.cssText = [
                    'display:flex', 'align-items:center', 'justify-content:space-between',
                    'padding:6px 14px', 'background:rgba(255,255,255,0.04)',
                    'border-bottom:1px solid rgba(255,255,255,0.06)',
                    'font-size:0.75rem', 'color:#8e8ea0',
                    'font-family:JetBrains Mono,monospace'
                ].join(';');
                hdr.innerHTML = '<span>' + lang + '</span>' +
                    '<button onclick="(function(b,p){' +
                        'var t=p.querySelector(\\'code\\').innerText;' +
                        'navigator.clipboard.writeText(t).then(function(){' +
                            'b.innerText=\\'✓ Copied\\';b.style.color=\\'#10b981\\';' +
                            'setTimeout(function(){b.innerText=\\'Copy\\';b.style.color=\\'\\';},2000);' +
                        '});' +
                    '})(this,this.closest(\\'pre\\'))" style="' +
                    'background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.1);' +
                    'color:#8e8ea0;border-radius:5px;padding:2px 10px;font-size:0.72rem;' +
                    'cursor:pointer;font-family:Inter,sans-serif;">Copy</button>';
                pre.style.cssText = [
                    'margin:10px 0','border-radius:10px','overflow:hidden',
                    'background:#0d0d0d','border:1px solid rgba(255,255,255,0.08)','padding:0'
                ].join(';');
                if (code) {
                    code.style.cssText = 'display:block;padding:16px;font-size:0.875rem;overflow-x:auto;';
                }
                pre.insertBefore(hdr, pre.firstChild);
            });
        }
        enhanceCodeBlocks();
        new MutationObserver(enhanceCodeBlocks).observe(document.body, {childList:true,subtree:true});

        /* ── KEYBOARD SHORTCUTS ── */
        document.addEventListener('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'N') {
                e.preventDefault();
                var btn = document.querySelector('[data-testid="stSidebar"] button[kind="primary"]');
                if (btn) btn.click();
            }
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                var inp = document.querySelector('[data-testid="stChatInput"] textarea');
                if (inp) inp.focus();
            }
        });
    })();
    </script>
    </div>
    """, unsafe_allow_html=True)


def inject_keyboard_shortcuts():
    """Kept for backward compatibility — all JS now goes through inject_all_js()."""
    pass


def inject_voice_input_js():
    """Kept for backward compatibility — all JS now goes through inject_all_js()."""
    pass


def inject_code_block_enhancer():
    """Kept for backward compatibility — all JS now goes through inject_all_js()."""
    pass


# ── DISPLAY COMPONENTS ─────────────────────────────────────────────────────────

# (Citation and confidence components have been extracted to citations.py and confidence.py)


def render_upload_indicator(filename: str, size_label: str, icon: str = "📎"):
    """Renders a file attachment pill."""
    st.markdown(f"""
    <span class="file-pill">{icon} {filename} <span style="color:#6e6e80;">({size_label})</span></span>
    """, unsafe_allow_html=True)


def render_typing_indicator():
    """Renders an animated 'AI is thinking' indicator."""
    st.markdown("""
    <div class="typing-indicator">
        <span></span><span></span><span></span>
        <span style="margin-left:8px;color:#6e6e80;font-size:0.875rem;">BotTech is thinking…</span>
    </div>
    """, unsafe_allow_html=True)


def render_image_preview(image_bytes: bytes, mime_type: str = "image/jpeg"):
    """Renders a thumbnail preview of an uploaded image."""
    import base64
    b64 = base64.b64encode(image_bytes).decode()
    st.markdown(f"""
    <div class="image-preview-container">
        <img src="data:{mime_type};base64,{b64}" alt="Uploaded image" />
    </div>
    """, unsafe_allow_html=True)
