# 📚 AI Study Buddy

AI Study Buddy is a Streamlit web app that helps students turn class notes into **summaries, multiple-choice quizzes, and flashcards**. It supports Google sign-in and stores study sessions in Supabase so users can return to previous work.

## Features

- Google sign-in through Streamlit authentication
- Upload PDF or TXT notes, or paste notes directly
- Generate an exam-friendly summary
- Generate multiple-choice quiz questions with explanations and score tracking
- Generate flashcards for active recall
- Save, reopen, and delete recent study sessions in Supabase
- Choose an AI provider: Groq or OpenAI

## Tech stack

- Python + Streamlit
- OpenAI Python SDK (used with OpenAI-compatible API endpoints)
- Groq API or OpenAI API
- Supabase (PostgreSQL database)
- Streamlit's built-in authentication with Google OAuth

## Run locally

### 1. Install Python

Use a supported Python version (Python 3.11 is recommended).

### 2. Clone or download this repository

```bash
git clone https://github.com/YOUR-GITHUB-USERNAME/study_buddy.git
cd study_buddy
```

Replace the example GitHub URL with your repository URL.

### 3. Create and activate a virtual environment (recommended)

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure secrets

Create a file at `.streamlit/secrets.toml` and add your own values. Do not commit this file or share its contents.

```toml
GROQ_API_KEY = "YOUR_GROQ_API_KEY"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "YOUR_SUPABASE_SERVER_SECRET_KEY"

[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "YOUR_GOOGLE_OAUTH_CLIENT_ID"
client_secret = "YOUR_GOOGLE_OAUTH_CLIENT_SECRET"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

You only need the key for the AI provider you plan to use. The Google OAuth client must allow the local callback URL `http://localhost:8501/oauth2callback`. For Streamlit Community Cloud, configure the deployed app's callback URL as `https://YOUR-APP-NAME.streamlit.app/oauth2callback` in Google OAuth settings and set the matching `redirect_uri` in Streamlit Secrets.

For deployment, paste the same TOML configuration into **Streamlit Community Cloud → App → Settings → Secrets**. Do not upload `secrets.toml` to GitHub. Never put secret keys in `app.py`, screenshots, README files, or public issues.

### 6. Create the Supabase table

In the Supabase project, open **SQL Editor**, then run the SQL in [`supabase_schema.sql`](supabase_schema.sql). This creates the `study_sessions` table used by the app.

The app currently uses `SUPABASE_KEY` from server-side Streamlit Secrets. Keep that key private and never expose it in browser-side code. Queries in the app filter records by the signed-in user's ID; do not remove those user filters.

### 7. Start the app

```bash
streamlit run app.py
```

Open the local URL shown in the terminal, usually `http://localhost:8501`.

## Deploy on Streamlit Community Cloud

1. Push `app.py`, `requirements.txt`, `README.md`, `.gitignore`, and `supabase_schema.sql` to your GitHub repository.
2. In Streamlit Community Cloud, create or open the app and select the repository, branch, and `app.py` as the main file.
3. Add the secrets in the app's **Settings → Secrets** section.
4. Confirm the Google OAuth redirect URI matches the deployed Streamlit URL.
5. Reboot the app and check the logs if an error appears.

## Repository files

- `app.py` — Streamlit application
- `requirements.txt` — Python dependencies
- `.gitignore` — excludes local secrets and generated files
- `.streamlit/secrets.toml.example` — example configuration with placeholders only
- `supabase_schema.sql` — database table definition
- `runtime.txt` — suggested Python runtime for platforms that support it

## Troubleshooting

- **Missing Supabase configuration:** confirm `SUPABASE_URL` and `SUPABASE_KEY` exist in Streamlit Secrets and that the TOML is valid.
- **Google login/redirect error:** confirm `client_id`, `client_secret`, `redirect_uri`, and the authorized redirect URI in Google Cloud match exactly.
- **Permission denied on `study_sessions`:** confirm the database grants and the key type are correct. Do not publish the server secret key. Use least privilege where possible.
- **AI request fails:** check that the chosen provider's key is configured and that the selected model is available to your account.
- **PDF has no extracted text:** scanned/image-only PDFs may require OCR; this app extracts selectable text from PDFs.

## Security

- Never commit `.streamlit/secrets.toml`, API keys, OAuth secrets, or database server keys.
- If a secret is accidentally shared, revoke/rotate it immediately and update the deployment secrets.
- Use only test data while developing and ensure every user's saved sessions are scoped to that user's account.
