"""
citations.py — Citation rendering components for RAG and Web search.
"""
import streamlit as st
from typing import List, Dict, Any

def render_citations(citations: List[Dict[str, Any]]):
    """Renders citation chips for documents used in retrieval."""
    if not citations:
        return
    chips_html = '<div class="citation-container"><span class="citation-label">📚 Sources:</span>'
    seen = set()
    for cite in citations:
        key = f"{cite['source']} P.{cite['page']}"
        if key in seen:
            continue
        seen.add(key)
        snippet = cite.get("snippet", "").replace('"', "&quot;")[:120]
        score_pct = int(cite.get("score", 0) * 100)
        chips_html += f'<div class="citation-chip" title="{snippet} (Relevance: {score_pct}%)">📄 {cite["source"]} · p.{cite["page"]}</div>'
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)

def render_web_citations(citations: List[Dict[str, Any]]):
    """Renders web search source chips with clickable links."""
    if not citations:
        return
    chips_html = '<div class="web-citation-container"><span class="citation-label">🌐 Web Sources:</span>'
    for cite in citations[:5]:
        title = cite.get("title", "Web Source")[:40]
        uri = cite.get("uri", "#")
        chips_html += f'<a class="web-citation-chip" href="{uri}" target="_blank" title="{cite.get("title","")}">🔗 {title}</a>'
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)
