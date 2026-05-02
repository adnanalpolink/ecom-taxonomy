"""
TaxonomyML — Streamlit Cloud App
Build a site taxonomy from a list of keywords (CSV upload) or Google Search Console data.
Designed for deployment on Streamlit Community Cloud.
"""

import sys
import os
import json
import tempfile

# Ensure the src directory is on the Python path so taxonomyml can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
import pandas as pd
from loguru import logger

# Enable taxonomyml logging so progress is visible
logger.enable("taxonomyml")


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_secret(key: str, default: str = "") -> str:
    """Read a value from st.secrets (Streamlit Cloud) or fall back to env var."""
    try:
        return st.secrets[key]
    except (KeyError, FileNotFoundError):
        return os.getenv(key, default)


def get_gsc_credentials_from_secrets() -> dict | None:
    """Try to load GSC service account JSON from st.secrets['gsc_credentials']."""
    try:
        creds = dict(st.secrets["gsc_credentials"])
        # st.secrets returns AttrDict — convert nested items to plain dicts too
        return json.loads(json.dumps(creds))
    except (KeyError, FileNotFoundError):
        return None


# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TaxonomyML — Auto Taxonomy Builder",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .block-container { max-width: 1100px; }
    .stAlert { margin-top: 0.5rem; }
    div[data-testid="stSidebar"] { min-width: 340px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🗂️ TaxonomyML")
    st.caption("Auto-generate website taxonomies from keyword data using AI.")
    st.divider()

    # Pre-fill from secrets if available
    default_key = get_secret("OPENAI_API_KEY")
    if default_key:
        st.success("OpenAI API key loaded from secrets.", icon="✅")
        openai_api_key = default_key
    else:
        openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            placeholder="sk-...",
            help="Required. Set in Streamlit Cloud Secrets or type here.",
        )

    st.divider()
    st.subheader("📁 Data Source")
    data_source = st.radio(
        "Choose your data source:",
        options=["CSV Upload", "Google Search Console"],
        index=0,
        horizontal=True,
    )

    st.divider()
    st.subheader("⚙️ Settings")

    website_subject = st.text_area(
        "Website Subject",
        placeholder="e.g. This website sells running shoes and athletic apparel.",
        help="Give GPT context about what the website is about.",
        height=80,
    )

    brand_terms_input = st.text_input(
        "Brand Terms (comma-separated)",
        placeholder="e.g. nike, adidas",
        help="Brand names to strip from queries before analysis.",
    )

    with st.expander("Advanced Options"):
        min_df = st.slider("Min Document Frequency", 1, 20, 5, help="Minimum ngram frequency to keep.")
        ngram_range_max = st.slider("Max N-gram Size", 2, 8, 5, help="Upper bound of ngram range.")
        cross_encoded = st.checkbox(
            "Use Cross-Encoder Matching",
            value=False,
            help="Improves category matching quality but takes longer.",
        )
        cluster_model_choice = st.selectbox(
            "Embedding Model",
            options=["local", "openai"],
            index=0,
            help="'local' uses sentence-transformers (free, runs on CPU). 'openai' uses OpenAI embeddings (costs money).",
        )
        limit_queries = st.number_input(
            "Limit Queries per Page (GSC only)", min_value=1, max_value=50, value=5
        )

# ── CSV-specific inputs ──────────────────────────────────────────────────────
csv_file = None
text_column = None
sv_column = None

if data_source == "CSV Upload":
    st.header("📄 Upload CSV")
    st.info(
        "Upload a CSV with at least a **keyword/query column** and a **search volume column**.",
        icon="ℹ️",
    )
    csv_file = st.file_uploader("Choose a CSV file", type=["csv"])

    if csv_file is not None:
        try:
            df_preview = pd.read_csv(csv_file, nrows=100)
            csv_file.seek(0)  # reset for later re-read
            cols = df_preview.columns.tolist()

            col1, col2 = st.columns(2)
            with col1:
                text_column = st.selectbox("Text / Keyword Column", options=cols, index=0)
            with col2:
                sv_column = st.selectbox(
                    "Search Volume Column",
                    options=cols,
                    index=min(1, len(cols) - 1),
                )

            st.markdown("**Preview (first 10 rows):**")
            st.dataframe(df_preview.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ── GSC-specific inputs ──────────────────────────────────────────────────────
gsc_property = None
gsc_credentials_file = None
gsc_credentials_from_secrets = None
gsc_days = 30

if data_source == "Google Search Console":
    st.header("🔍 Google Search Console")

    # Check if credentials are in secrets
    gsc_credentials_from_secrets = get_gsc_credentials_from_secrets()

    if gsc_credentials_from_secrets:
        st.success("GSC service account loaded from Streamlit Secrets.", icon="✅")
    else:
        st.info(
            "Upload a **service account JSON** file, or add it to your "
            "[Streamlit Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management) "
            "under the key `[gsc_credentials]`.",
            icon="ℹ️",
        )
        gsc_credentials_file = st.file_uploader(
            "Service Account JSON", type=["json"]
        )

    gsc_property = st.text_input(
        "GSC Property URL",
        placeholder="https://www.example.com/ or sc-domain:example.com",
    )
    gsc_days = st.number_input("Days of data to pull", min_value=1, max_value=540, value=30)

    with st.expander("ℹ️ How to connect Google Search Console"):
        st.markdown("""
### Step-by-step Guide

1. **Create a Google Cloud project** at [console.cloud.google.com](https://console.cloud.google.com/)
2. **Enable the Search Console API**
   - Go to *APIs & Services → Library*
   - Search for **Google Search Console API** and click **Enable**
3. **Create a Service Account**
   - Go to *APIs & Services → Credentials*
   - Click **Create Credentials → Service Account**
   - Give it a name (e.g. `taxonomy-gsc`) and click **Done**
4. **Download the JSON key**
   - Click the new service account → **Keys** tab
   - Click **Add Key → Create new key → JSON** → **Create**
   - Save the downloaded `.json` file
5. **Grant access in Google Search Console**
   - Go to [search.google.com/search-console](https://search.google.com/search-console)
   - Select your property → **Settings → Users and permissions**
   - Click **Add User**
   - Paste the service account email (found in the JSON, field `client_email`)
   - Set permission to **Full** and click **Add**
6. **Use in this app**
   - **Option A (upload):** Upload the JSON file above
   - **Option B (secrets):** Paste the entire JSON content into your Streamlit Cloud Secrets under `[gsc_credentials]`

> **Tip:** The service account email looks like `name@project.iam.gserviceaccount.com`
        """)


# ── Run Button ───────────────────────────────────────────────────────────────
st.divider()
can_run = False

if not openai_api_key:
    st.warning("⬅️ Enter your **OpenAI API Key** in the sidebar to begin.", icon="🔑")
elif not website_subject:
    st.warning("⬅️ Enter a **Website Subject** in the sidebar.", icon="📝")
elif data_source == "CSV Upload" and csv_file is None:
    st.warning("Upload a **CSV file** above to continue.", icon="📄")
elif data_source == "Google Search Console" and (
    not gsc_property
    or (gsc_credentials_file is None and gsc_credentials_from_secrets is None)
):
    st.warning("Provide **GSC credentials and property URL** above.", icon="🔍")
else:
    can_run = True

run_clicked = st.button(
    "🚀  Generate Taxonomy",
    type="primary",
    use_container_width=True,
    disabled=not can_run,
)

# ── Execution ────────────────────────────────────────────────────────────────
if run_clicked and can_run:
    brand_terms = (
        [b.strip() for b in brand_terms_input.split(",") if b.strip()]
        if brand_terms_input
        else None
    )

    with st.status("Building taxonomy…", expanded=True) as status:
        try:
            # ── CSV path ─────────────────────────────────────────────────
            if data_source == "CSV Upload":
                st.write("📂 Reading CSV…")
                df_input = pd.read_csv(csv_file, nrows=1_000_000)

                st.write("🧠 Running TaxonomyML pipeline…")
                from taxonomyml import create_taxonomy

                taxonomy, df_result, samples = create_taxonomy(
                    data=df_input,
                    text_column=text_column,
                    search_volume_column=sv_column,
                    website_subject=website_subject,
                    brand_terms=brand_terms,
                    min_df=min_df,
                    ngram_range=(1, ngram_range_max),
                    cross_encoded=cross_encoded,
                    cluster_embeddings_model=cluster_model_choice,
                    openai_api_key=openai_api_key,
                )

            # ── GSC path ─────────────────────────────────────────────────
            else:
                st.write("🔐 Setting up Google Auth…")
                from taxonomyml.lib import gsc as gsc_module, gauth

                # Resolve credentials: secrets → uploaded file
                if gsc_credentials_from_secrets:
                    cred_dict = gsc_credentials_from_secrets
                else:
                    cred_bytes = gsc_credentials_file.read()
                    cred_dict = json.loads(cred_bytes)

                # Write to temp file (google-auth requires a file path)
                tmp_cred = tempfile.NamedTemporaryFile(
                    delete=False, suffix=".json", mode="w"
                )
                json.dump(cred_dict, tmp_cred)
                tmp_cred.close()

                auth_manager = gauth.GoogleServiceAccManager(
                    scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
                    credentials_path=tmp_cred.name,
                )
                gsc_client = gsc_module.GoogleSearchConsole(auth_manager=auth_manager)

                st.write("🧠 Running TaxonomyML pipeline…")
                from taxonomyml import create_taxonomy

                taxonomy, df_result, samples = create_taxonomy(
                    data=gsc_property,
                    gsc_client=gsc_client,
                    days=gsc_days,
                    website_subject=website_subject,
                    brand_terms=brand_terms,
                    min_df=min_df,
                    ngram_range=(1, ngram_range_max),
                    cross_encoded=cross_encoded,
                    cluster_embeddings_model=cluster_model_choice,
                    limit_queries_per_page=limit_queries,
                    openai_api_key=openai_api_key,
                )

                # Clean up temp file
                os.unlink(tmp_cred.name)

            status.update(label="✅ Taxonomy generated!", state="complete")

        except Exception as e:
            status.update(label="❌ Error", state="error")
            st.error(f"An error occurred: {e}")
            st.exception(e)
            st.stop()

    # ── Results ───────────────────────────────────────────────────────────
    st.divider()
    st.header("📊 Results")

    # Taxonomy tree
    tab1, tab2, tab3 = st.tabs(["🌳 Taxonomy", "📋 Full Data", "📈 Topic Scores"])

    with tab1:
        st.subheader("Generated Taxonomy")
        if taxonomy:
            for item in taxonomy:
                depth = item.count(" > ")
                indent = "&nbsp;" * (depth * 6)
                parts = item.split(" > ")
                st.markdown(f"{indent}{'📁' if depth == 0 else '📄'} **{parts[-1]}**", unsafe_allow_html=True)
        else:
            st.warning("No taxonomy was generated.")

    with tab2:
        st.subheader("Classified Data")
        st.dataframe(df_result, use_container_width=True, height=500)

        csv_output = df_result.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️  Download CSV",
            data=csv_output,
            file_name="taxonomy_results.csv",
            mime="text/csv",
            type="primary",
        )

    with tab3:
        st.subheader("Topic Scores (input to GPT)")
        st.markdown(samples)

# ── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Powered by [TaxonomyML](https://github.com/adnanalpolink/ecom-taxonomy) · "
    "Created by Adnan Akram"
)
