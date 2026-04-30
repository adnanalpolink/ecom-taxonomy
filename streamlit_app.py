"""Streamlit demo for taxonomyml.

Run locally with:
    pip install "taxonomyml[streamlit]"
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import io
from typing import List

import pandas as pd
import streamlit as st

from taxonomyml import create_taxonomy

st.set_page_config(
    page_title="TaxonomyML",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _render_taxonomy(structure: List[str]) -> str:
    """Render a flat list of 'A > B > C' paths as an indented markdown bullet list."""
    seen: set[str] = set()
    lines: list[str] = []
    for path in structure:
        parts = [p.strip() for p in path.split(">") if p.strip()]
        for depth in range(len(parts)):
            prefix = " > ".join(parts[: depth + 1])
            if prefix in seen:
                continue
            seen.add(prefix)
            lines.append(f"{'  ' * depth}- {parts[depth]}")
    return "\n".join(lines)


def _to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def _default_api_key() -> str:
    try:
        return st.secrets.get("OPENAI_API_KEY", "")  # type: ignore[no-any-return]
    except (FileNotFoundError, AttributeError):
        return ""


with st.sidebar:
    st.title("⚙️ Settings")
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        value=_default_api_key(),
        help="Used only for this session. Falls back to st.secrets['OPENAI_API_KEY'].",
    )

    st.markdown("**Brand terms** (one per line) — stripped from queries.")
    brand_text = st.text_area("Brand terms", placeholder="acme\nacme corp", height=100)

    st.markdown("---")
    st.subheader("Fine-tuning")
    min_df = st.slider("Minimum document frequency", 1, 20, 5)
    cross_encoded = st.checkbox(
        "Use cross-encoder matching (slower, more accurate)", value=False
    )
    max_input_rows = st.number_input(
        "Max input rows", min_value=100, max_value=200_000, value=50_000, step=1000
    )

st.title("🗂️ TaxonomyML")
st.caption(
    "Build a high-level website taxonomy from a CSV of keywords and search volumes."
)

uploaded = st.file_uploader("Upload a CSV file", type=["csv"])

col1, col2 = st.columns(2)
with col1:
    text_column = st.text_input("Text (keyword) column name", value="keyword")
with col2:
    sv_column = st.text_input("Search volume column name", value="search_volume")

website_subject = st.text_area(
    "Website subject",
    placeholder="This website is about...",
    help="A short description of what the site sells or covers.",
    height=100,
)

if uploaded is not None:
    try:
        preview_df = pd.read_csv(uploaded, nrows=10)
        st.markdown("**Preview**")
        st.dataframe(preview_df, use_container_width=True)
        uploaded.seek(0)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not read CSV: {exc}")

run = st.button("🚀 Build taxonomy", type="primary", use_container_width=True)

if run:
    if uploaded is None:
        st.error("Please upload a CSV file first.")
        st.stop()
    if not website_subject.strip():
        st.error("Please provide a website subject.")
        st.stop()
    if not api_key.strip():
        st.error("Please provide an OpenAI API key in the sidebar.")
        st.stop()

    brand_terms = [b.strip() for b in brand_text.splitlines() if b.strip()] or None

    with st.spinner("Building taxonomy — this can take a few minutes…"):
        try:
            df_input = pd.read_csv(uploaded)
            structure, df_out, query_data = create_taxonomy(
                df_input,
                text_column=text_column,
                search_volume_column=sv_column,
                website_subject=website_subject,
                cross_encoded=cross_encoded,
                min_df=int(min_df),
                brand_terms=brand_terms,
                openai_api_key=api_key,
                max_input_rows=int(max_input_rows),
            )
        except Exception as exc:  # noqa: BLE001
            st.error(f"Taxonomy generation failed: {exc}")
            st.stop()

    st.success(f"Generated {len(structure)} taxonomy entries.")

    tab_tax, tab_data, tab_queries = st.tabs(
        ["📚 Taxonomy", "🏷️ Categorized data", "🔎 Query data"]
    )
    with tab_tax:
        st.markdown(_render_taxonomy(structure))
    with tab_data:
        st.dataframe(df_out, use_container_width=True, height=500)
        st.download_button(
            "Download CSV",
            data=_to_csv_bytes(df_out),
            file_name="taxonomy.csv",
            mime="text/csv",
        )
    with tab_queries:
        st.markdown(query_data)
