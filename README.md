# TaxonomyML — Auto Taxonomy Creation

Build a site taxonomy from a list of keywords, provided via CSV file upload, or by connecting to a Google Search Console property. Uses OpenAI (GPT-5.5 / GPT-5.4-mini) for taxonomy creation.

Created by **Adnan Akram**.

---

## Deploy on Streamlit Cloud

### 1. Push this repo to GitHub

### 2. Go to [share.streamlit.io](https://share.streamlit.io)

- Click **New app**
- Select your repo, branch, and set the main file to `streamlit_app.py`

### 3. Add Secrets

In the Streamlit Cloud dashboard, go to **App Settings → Secrets** and add:

```toml
OPENAI_API_KEY = "sk-your-openai-api-key-here"

# Optional: GSC Service Account (paste the full JSON content)
[gsc_credentials]
type = "service_account"
project_id = "your-project-id"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "taxonomy@your-project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/..."
```

### 4. Done! Your app is live.

---

## Run Locally

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## Connecting Google Search Console

1. **Create a Google Cloud project** at [console.cloud.google.com](https://console.cloud.google.com/)
2. **Enable the Search Console API** — Go to *APIs & Services → Library*, search for "Google Search Console API", and enable it
3. **Create a Service Account** — Go to *APIs & Services → Credentials → Create Credentials → Service Account*
4. **Download the JSON key** — Click the service account → *Keys* tab → *Add Key → JSON*
5. **Grant access in GSC** — Go to [Search Console](https://search.google.com/search-console) → *Settings → Users and permissions → Add User* → paste the `client_email` from the JSON → set permission to **Full**
6. **Use in the app** — Upload the JSON file in the app, or paste it into Streamlit Cloud Secrets under `[gsc_credentials]`

---

## Usage as a Library

### Example with CSV

```python
from taxonomyml import create_taxonomy

taxonomy, df, samples = create_taxonomy(
    "domain_data.csv",
    text_column="keyword",
    search_volume_column="search_volume",
    website_subject="This website is about X",
    cross_encoded=True,
    min_df=5,
    brand_terms=["brand"],
    openai_api_key="sk-..."
)

df.to_csv("taxonomy.csv", index=False)
```

### Example with Google Search Console

```python
import os
from taxonomyml import create_taxonomy
from taxonomyml.lib import gsc, gauth
os.environ["OPENAI_API_KEY"] = "sk-..."

auth_manager = gauth.GoogleServiceAccManager(
    scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    credentials_path="service_account.json",
)
gsc_client = gsc.GoogleSearchConsole(auth_manager=auth_manager)

taxonomy, df, samples = create_taxonomy(
    "https://www.example.com/",
    gsc_client=gsc_client,
    days=30,
    website_subject="This website is about X",
    min_df=2,
    brand_terms=["brand"],
    limit_queries_per_page=5,
)

df.to_csv("domain_taxonomy.csv", index=False)
```

---

## Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data` | str / DataFrame | *required* | GSC property URL, CSV filename, or DataFrame |
| `text_column` | str | None | Column name for keywords (CSV only) |
| `search_volume_column` | str | None | Column name for search volume (CSV only) |
| `website_subject` | str | "" | Context about the website for GPT |
| `openai_api_key` | str | env var | OpenAI API key |
| `brand_terms` | list | None | Brand terms to strip from queries |
| `days` | int | 30 | Days of GSC data to pull |
| `min_df` | int | 5 | Minimum ngram document frequency |
| `ngram_range` | tuple | (1, 5) | N-gram range for scoring |
| `cross_encoded` | bool | False | Use cross-encoder matching (slower, better) |
| `cluster_embeddings_model` | str | "local" | "local" or "openai" |

---

## License

MIT
