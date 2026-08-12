"""
confidence.py — Confidence gauge UI component.
"""
import streamlit as st

def render_confidence_gauge(score: int, description: str):
    """Renders a compact confidence badge under the assistant response."""
    if score >= 85:
        dot_class = "conf-high"
    elif score >= 65:
        dot_class = "conf-med"
    else:
        dot_class = "conf-low"

    st.markdown(f"""
    <div class="confidence-gauge">
        <span class="confidence-dot {dot_class}"></span>
        <span>Confidence: <strong style="color:#60a5fa;">{score}%</strong></span>
        <span style="color:#4a4a5a;">·</span>
        <span style="color:#6e6e80;font-size:0.7rem;">{description}</span>
    </div>
    """, unsafe_allow_html=True)

