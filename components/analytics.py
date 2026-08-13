"""
analytics.py — Full-page Chat Analytics Dashboard.

Renders KPI summary cards and interactive Plotly charts based on
data from ChatStore.get_analytics(). Integrates with the existing
BotTech AI glassmorphic dark theme.
"""
# pyright: ignore [missing-import]
import streamlit as st
import datetime
from src.logger import get_logger

logger = get_logger(__name__)


# ── PLOTLY DARK LAYOUT DEFAULTS ────────────────────────────────────────────────
_PLOTLY_BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#ececec", size=12),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(
        bgcolor="rgba(255,255,255,0.03)",
        bordercolor="rgba(255,255,255,0.08)",
        borderwidth=1,
        font=dict(color="#8e8ea0", size=11),
    ),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.08)",
        tickfont=dict(color="#8e8ea0"),
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.08)",
        tickfont=dict(color="#8e8ea0"),
    ),
)

_ACCENT_COLORS = {
    "indigo": "#6366f1",
    "sky": "#38bdf8",
    "emerald": "#10b981",
    "amber": "#f59e0b",
    "rose": "#f43f5e",
    "violet": "#a78bfa",
    "cyan": "#22d3ee",
}

_SOURCE_COLORS = {
    "Knowledge Base": "#38bdf8",
    "Web Search": "#34d399",
    "AI General": "#a78bfa",
}


def _card(icon: str, label: str, value: str, subtitle: str = "", color: str = "#6366f1"):
    """Renders a single KPI metric card."""
    st.markdown(f"""
    <div class="analytics-kpi-card" style="border-top: 3px solid {color};">
        <div class="analytics-kpi-icon">{icon}</div>
        <div class="analytics-kpi-value" style="color:{color};">{value}</div>
        <div class="analytics-kpi-label">{label}</div>
        {f'<div class="analytics-kpi-sub">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def _chart_header(title: str, subtitle: str = ""):
    st.markdown(f"""
    <div class="analytics-chart-header">
        <div class="analytics-chart-title">{title}</div>
        {f'<div class="analytics-chart-subtitle">{subtitle}</div>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def _build_daily_activity_chart(daily_messages: list, daily_sessions: list):
    """Bar chart: messages and sessions per day over last 14 days."""
    try:
        import plotly.graph_objects as go

        today = datetime.date.today()
        date_range = [(today - datetime.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]

        msg_map = {r["day"]: r["cnt"] for r in daily_messages}
        sess_map = {r["day"]: r["cnt"] for r in daily_sessions}

        msg_vals = [msg_map.get(d, 0) for d in date_range]
        sess_vals = [sess_map.get(d, 0) for d in date_range]
        labels = [d[5:] for d in date_range]  # MM-DD

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels, y=msg_vals, name="Messages",
            marker_color=_ACCENT_COLORS["indigo"], marker_line_width=0, opacity=0.85,
        ))
        fig.add_trace(go.Bar(
            x=labels, y=sess_vals, name="New Sessions",
            marker_color=_ACCENT_COLORS["cyan"], marker_line_width=0, opacity=0.85,
        ))
        layout = dict(**_PLOTLY_BASE_LAYOUT)
        layout.update(
            barmode="group", height=260, title=None,
            xaxis=dict(**_PLOTLY_BASE_LAYOUT["xaxis"], title=None),
            yaxis=dict(**_PLOTLY_BASE_LAYOUT["yaxis"], title="Count"),
        )
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        logger.warning(f"Error building daily activity chart: {e}")
        return None


def _build_source_donut_chart(source_distribution: dict):
    """Donut chart: distribution of response source types."""
    try:
        import plotly.graph_objects as go

        labels = list(source_distribution.keys())
        values = list(source_distribution.values())
        colors = [_SOURCE_COLORS.get(lbl, "#6366f1") for lbl in labels]

        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.58,
            marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0.3)", width=2)),
            textfont=dict(color="#ececec", size=12),
            hovertemplate="<b>%{label}</b><br>%{value} responses (%{percent})<extra></extra>",
        ))
        layout = dict(**_PLOTLY_BASE_LAYOUT)
        layout.update(
            height=280, showlegend=True,
            legend=dict(**_PLOTLY_BASE_LAYOUT["legend"], orientation="v", x=0.75, y=0.5),
            annotations=[dict(
                text="Source<br>Mix", x=0.5, y=0.5,
                font=dict(size=13, color="#ececec", family="Outfit, sans-serif"),
                showarrow=False,
            )],
        )
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        logger.warning(f"Error building source donut chart: {e}")
        return None


def _build_confidence_trend_chart(daily_confidence: list):
    """Line chart: average confidence score trend over last 14 days."""
    try:
        import plotly.graph_objects as go

        today = datetime.date.today()
        date_range = [(today - datetime.timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
        conf_map = {r["day"]: round(r["avg_score"] or 0, 1) for r in daily_confidence}
        labels = [d[5:] for d in date_range]
        values = [conf_map.get(d, None) for d in date_range]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=labels, y=values, mode="lines+markers", name="Avg Confidence",
            line=dict(color=_ACCENT_COLORS["emerald"], width=2.5, shape="spline"),
            marker=dict(size=6, color=_ACCENT_COLORS["emerald"],
                        line=dict(color="rgba(0,0,0,0.5)", width=1)),
            fill="tozeroy", fillcolor="rgba(16,185,129,0.08)",
            hovertemplate="<b>%{x}</b><br>Avg Score: %{y:.1f}%<extra></extra>",
            connectgaps=False,
        ))
        fig.add_hline(
            y=80, line_dash="dot", line_color="rgba(245,158,11,0.4)",
            annotation_text="Target 80%",
            annotation_font=dict(color="#f59e0b", size=10),
        )
        layout = dict(**_PLOTLY_BASE_LAYOUT)
        layout.update(
            height=240,
            xaxis=dict(**_PLOTLY_BASE_LAYOUT["xaxis"], title=None),
            yaxis=dict(**_PLOTLY_BASE_LAYOUT["yaxis"], title="Score (%)", range=[0, 105]),
        )
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        logger.warning(f"Error building confidence trend chart: {e}")
        return None


def _build_feedback_chart(feedback_by_source: dict):
    """Horizontal stacked bar: thumbs up/down by source type."""
    try:
        import plotly.graph_objects as go

        sources = list(feedback_by_source.keys())
        ups = [feedback_by_source[s]["up"] for s in sources]
        downs = [feedback_by_source[s]["down"] for s in sources]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=sources, x=ups, orientation="h", name="Helpful",
            marker_color=_ACCENT_COLORS["emerald"], opacity=0.85,
            hovertemplate="<b>%{y}</b><br>Helpful: %{x}<extra></extra>",
        ))
        fig.add_trace(go.Bar(
            y=sources, x=downs, orientation="h", name="Not Helpful",
            marker_color=_ACCENT_COLORS["rose"], opacity=0.85,
            hovertemplate="<b>%{y}</b><br>Not Helpful: %{x}<extra></extra>",
        ))
        layout = dict(**_PLOTLY_BASE_LAYOUT)
        layout.update(
            barmode="stack", height=220,
            xaxis=dict(**_PLOTLY_BASE_LAYOUT["xaxis"], title="Responses"),
            yaxis=dict(**_PLOTLY_BASE_LAYOUT["yaxis"], title=None),
        )
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        logger.warning(f"Error building feedback chart: {e}")
        return None


def _build_model_usage_chart(model_usage: list):
    """Horizontal bar chart: sessions by model."""
    try:
        import plotly.graph_objects as go

        if not model_usage:
            return None

        models = [r["model"].replace("gemini-", "Gemini ") for r in model_usage]
        counts = [r["cnt"] for r in model_usage]
        bar_colors = [_ACCENT_COLORS["violet"], _ACCENT_COLORS["indigo"],
                      _ACCENT_COLORS["sky"], _ACCENT_COLORS["amber"]]

        fig = go.Figure(go.Bar(
            y=models, x=counts, orientation="h",
            marker=dict(color=bar_colors[:len(models)], line=dict(width=0)),
            opacity=0.85,
            hovertemplate="<b>%{y}</b><br>%{x} sessions<extra></extra>",
        ))
        layout = dict(**_PLOTLY_BASE_LAYOUT)
        layout.update(
            height=max(160, 60 + len(models) * 50), showlegend=False,
            xaxis=dict(**_PLOTLY_BASE_LAYOUT["xaxis"], title="Sessions"),
            yaxis=dict(**_PLOTLY_BASE_LAYOUT["yaxis"], title=None),
        )
        fig.update_layout(**layout)
        return fig
    except Exception as e:
        logger.warning(f"Error building model usage chart: {e}")
        return None


def render_analytics_dashboard():
    """Renders the full Chat Analytics Dashboard page."""

    chat_store = st.session_state.get("chat_store")
    if not chat_store:
        st.error("ChatStore not initialized. Cannot load analytics.")
        return

    # ── PAGE HEADER ──────────────────────────────────────────────────────────────
    col_title, col_back = st.columns([6, 1])
    with col_title:
        st.markdown("""
        <div class="analytics-page-header">
            <span class="analytics-page-icon">📊</span>
            <div>
                <div class="analytics-page-title">Chat Analytics</div>
                <div class="analytics-page-sub">Usage insights &amp; performance trends</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_back:
        st.markdown("<div style='padding-top:14px;'>", unsafe_allow_html=True)
        if st.button("← Back to Chat", key="analytics_back_btn", use_container_width=True):
            st.session_state.show_analytics = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── FETCH DATA ───────────────────────────────────────────────────────────────
    with st.spinner("Loading analytics…"):
        try:
            data = chat_store.get_analytics()
        except Exception as e:
            st.error(f"Failed to load analytics data: {e}")
            logger.error(f"Analytics load error: {e}")
            return

    total_sessions = data.get("total_sessions", 0)
    total_messages = data.get("total_messages", 0)
    user_messages = data.get("user_messages", 0)
    thumbs_up = data.get("thumbs_up", 0)
    thumbs_down = data.get("thumbs_down", 0)
    avg_confidence = data.get("avg_confidence", 0)
    avg_resp_len = data.get("avg_response_length", 0)
    total_feedback = thumbs_up + thumbs_down
    satisfaction = int((thumbs_up / total_feedback) * 100) if total_feedback > 0 else 100

    # ── KPI CARDS ────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card("💬", "Total Sessions", str(total_sessions),
              "Conversations started", _ACCENT_COLORS["indigo"])
    with c2:
        _card("📩", "Total Messages", str(total_messages),
              f"{user_messages} from users", _ACCENT_COLORS["sky"])
    with c3:
        avg_conf_display = f"{avg_confidence:.0f}%" if avg_confidence else "N/A"
        conf_color = (_ACCENT_COLORS["emerald"] if avg_confidence >= 75
                      else _ACCENT_COLORS["amber"] if avg_confidence >= 50
                      else _ACCENT_COLORS["rose"])
        _card("⭐", "Avg Confidence", avg_conf_display,
              "Response quality score", conf_color)
    with c4:
        sat_color = (_ACCENT_COLORS["emerald"] if satisfaction >= 80
                     else _ACCENT_COLORS["amber"] if satisfaction >= 50
                     else _ACCENT_COLORS["rose"])
        _card("👍", "Satisfaction Rate", f"{satisfaction}%",
              f"{thumbs_up} up  {thumbs_down} down feedback", sat_color)
    with c5:
        _card("📝", "Avg Response", f"{avg_resp_len:,}",
              "chars per reply", _ACCENT_COLORS["violet"])

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # ── ROW 1: Daily Activity + Source Distribution ───────────────────────────
    chart_config = {"displayModeBar": False, "responsive": True}
    col_act, col_src = st.columns([3, 2], gap="medium")

    with col_act:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("📈 Daily Activity", "Messages and new sessions — last 14 days")
        fig = _build_daily_activity_chart(
            data.get("daily_messages", []),
            data.get("daily_sessions", []),
        )
        if fig:
            st.plotly_chart(fig, use_container_width=True, config=chart_config)
        else:
            st.info("No activity data yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_src:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("🎯 Source Distribution", "How queries are answered")
        source_dist = data.get("source_distribution", {})
        total_resp = sum(source_dist.values())
        if total_resp > 0:
            fig = _build_source_donut_chart(source_dist)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config=chart_config)
        else:
            st.markdown("""
            <div style='text-align:center; padding:60px 0; color:#6e6e80;
                        font-size:0.85rem; font-style:italic;'>
                No responses yet to analyze.
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── ROW 2: Confidence Trend + Feedback by Source ─────────────────────────
    col_conf, col_fb = st.columns([3, 2], gap="medium")

    with col_conf:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("📉 Confidence Trend", "Avg score per day — last 14 days")
        daily_conf = data.get("daily_confidence", [])
        if daily_conf:
            fig = _build_confidence_trend_chart(daily_conf)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config=chart_config)
        else:
            st.markdown("""
            <div style='text-align:center; padding:60px 0; color:#6e6e80;
                        font-size:0.85rem; font-style:italic;'>
                No confidence scores recorded yet.
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_fb:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("🗣️ Feedback by Source", "Helpfulness ratings per source type")
        feedback_data = data.get("feedback_by_source", {})
        has_fb = any(v["up"] + v["down"] > 0 for v in feedback_data.values())
        if has_fb:
            fig = _build_feedback_chart(feedback_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config=chart_config)
        else:
            st.markdown("""
            <div style='text-align:center; padding:60px 0; color:#6e6e80;
                        font-size:0.85rem; font-style:italic;'>
                No feedback recorded yet.
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

    # ── ROW 3: Model Usage + Top Sessions ────────────────────────────────────
    col_model, col_top = st.columns([2, 3], gap="medium")

    with col_model:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("🤖 Model Usage", "Sessions by LLM")
        model_usage = data.get("model_usage", [])
        if model_usage:
            fig = _build_model_usage_chart(model_usage)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config=chart_config)
        else:
            st.markdown("""
            <div style='text-align:center; padding:40px 0; color:#6e6e80;
                        font-size:0.85rem; font-style:italic;'>
                No session data yet.
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_top:
        st.markdown("""<div class="analytics-glass-card">""", unsafe_allow_html=True)
        _chart_header("🏆 Most Active Sessions", "Top 5 conversations by message count")
        top_sessions = data.get("top_sessions", [])
        if top_sessions:
            rows_html = ""
            for i, s in enumerate(top_sessions, 1):
                title = (s.get("title") or "New Chat")[:30]
                model_short = (s.get("model") or "").replace("gemini-", "Gemini ")
                try:
                    created = datetime.datetime.fromisoformat(
                        s.get("created_at", "")
                    ).strftime("%b %d, %Y")
                except Exception:
                    created = s.get("created_at", "")[:10]
                msg_count = s.get("msg_count", 0)
                badge_color = (
                    "#10b981" if msg_count >= 20 else
                    "#f59e0b" if msg_count >= 10 else "#6366f1"
                )
                badge_bg = (
                    "16,185,129" if msg_count >= 20 else
                    "245,158,11" if msg_count >= 10 else "99,102,241"
                )
                rows_html += f"""
                <tr>
                    <td style="color:#6e6e80; font-weight:700;">{i}</td>
                    <td style="color:#ececec; font-weight:500;">{title}</td>
                    <td style="color:#a78bfa; font-size:0.75rem;">{model_short}</td>
                    <td style="color:#6e6e80; font-size:0.75rem;">{created}</td>
                    <td>
                        <span style="background:rgba({badge_bg},0.15); color:{badge_color};
                               padding:2px 10px; border-radius:99px;
                               font-size:0.78rem; font-weight:700;">{msg_count}</span>
                    </td>
                </tr>"""
            st.markdown(f"""
            <table class="analytics-table">
                <thead>
                    <tr>
                        <th>#</th><th>Session Title</th><th>Model</th>
                        <th>Created</th><th>Messages</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style='text-align:center; padding:40px 0; color:#6e6e80;
                        font-size:0.85rem; font-style:italic;'>
                No session data yet.
            </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:32px;'></div>", unsafe_allow_html=True)
