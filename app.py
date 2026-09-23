"""
AI Study Buddy
--------------
A simple Streamlit app that lets a student upload notes (PDF or .txt),
then uses the OpenAI API to generate:
  1. A clean summary
  2. A multiple-choice quiz
  3. A set of flashcards

Run it with:
    streamlit run app.py

You will need an OpenAI API key. You can either:
  - paste it into the sidebar box when the app opens, or
  - set it as an environment variable called OPENAI_API_KEY before launching.
"""

import json
import os

import streamlit as st
from openai import OpenAI
from pypdf import PdfReader


# =========================================================
# 1. PAGE SETUP
# =========================================================

st.set_page_config(page_title="AI Study Buddy", page_icon="📚", layout="wide")

# Values that need to survive between button clicks live in st.session_state.
# Without this, Streamlit would forget the notes/summary/quiz every time
# you interact with the page.
defaults = {
    "notes_text": "",
    "summary": "",
    "quiz": None,
    "flashcards": None,
    "quiz_submitted": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 2. HELPER FUNCTIONS
# =========================================================

def extract_text_from_pdf(uploaded_file) -> str:
    """Pull all the text out of an uploaded PDF file."""
    reader = PdfReader(uploaded_file)
    pages_text = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    return "\n".join(pages_text)


# Providers that speak the OpenAI-compatible chat API. Groq's free tier
# needs no credit card at all, which is why it's listed first/default.
PROVIDERS = {
    "Groq (Free \u2014 no card needed)": {
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["openai/gpt-oss-20b", "openai/gpt-oss-120b"],
        "key_url": "https://console.groq.com/keys",
    },
    "OpenAI (paid)": {
        "base_url": None,  # None = use OpenAI's default endpoint
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
        "key_url": "https://platform.openai.com/api-keys",
    },
}


def get_client(api_key: str, base_url: str | None) -> OpenAI:
    """Create a client for whichever provider was selected."""
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def ask_openai(client: OpenAI, model: str, system_prompt: str, user_prompt: str) -> str:
    """Send one system+user prompt to the OpenAI chat API and return the text reply."""
    response = client.chat.completions.create(
        model=model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


def parse_json_safely(raw_text: str):
    """
    The model is asked to return JSON, but it sometimes wraps it in
    ```json ... ``` code fences. This strips those off and parses it.
    Returns None if the text still isn't valid JSON.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---- The three "study buddy" prompts -----------------------------------

def generate_summary(client, model, notes_text):
    system_prompt = (
        "You are a friendly, encouraging study assistant. You turn messy "
        "student notes into clear, well-organized summaries."
    )
    user_prompt = f"""Summarize the following notes for a student who is studying for an exam.

Formatting rules:
- Use short Markdown headings to group related ideas.
- Use bullet points, not long paragraphs.
- **Bold** key terms and definitions.
- Keep it concise: aim for roughly a third the length of the original notes.

NOTES:
\"\"\"
{notes_text}
\"\"\"
"""
    return ask_openai(client, model, system_prompt, user_prompt)


def generate_quiz(client, model, notes_text, num_questions):
    system_prompt = (
        "You are a study assistant that writes multiple-choice quiz questions. "
        "You respond with ONLY valid JSON, no explanations, no markdown fences."
    )
    user_prompt = f"""Read the notes below and write {num_questions} multiple-choice questions
that test understanding of the material (not just trivial recall).

Return ONLY a JSON array, formatted exactly like this example:
[
  {{
    "question": "What is ...?",
    "options": ["A) first option", "B) second option", "C) third option", "D) fourth option"],
    "correct_answer": "A",
    "explanation": "One short sentence explaining why."
  }}
]

NOTES:
\"\"\"
{notes_text}
\"\"\"
"""
    raw = ask_openai(client, model, system_prompt, user_prompt)
    return parse_json_safely(raw)


def generate_flashcards(client, model, notes_text, num_cards):
    system_prompt = (
        "You are a study assistant that writes flashcards for active-recall practice. "
        "You respond with ONLY valid JSON, no explanations, no markdown fences."
    )
    user_prompt = f"""Read the notes below and create {num_cards} flashcards.
Each flashcard has a short "front" (a question or term) and a short "back" (the answer or definition).

Return ONLY a JSON array, formatted exactly like this example:
[
  {{"front": "What is photosynthesis?", "back": "The process plants use to turn light into energy."}}
]

NOTES:
\"\"\"
{notes_text}
\"\"\"
"""
    raw = ask_openai(client, model, system_prompt, user_prompt)
    return parse_json_safely(raw)


# =========================================================
# 3. SIDEBAR — SETTINGS
# =========================================================

with st.sidebar:
    st.header("⚙️ Settings")

    provider_name = st.selectbox("Provider", list(PROVIDERS.keys()), index=0)
    provider = PROVIDERS[provider_name]

    default_key = os.environ.get("OPENAI_API_KEY", "") if "OpenAI" in provider_name else ""
    api_key = st.text_input(
        "API key",
        value=default_key,
        type="password",
        help=f"Get a free key at {provider['key_url']}. It is only used for this session and is not stored.",
    )
    st.caption(f"🔑 Get a key: {provider['key_url']}")

    model = st.selectbox("Model", provider["models"], index=0)

    st.divider()
    num_quiz_questions = st.slider("Number of quiz questions", 3, 15, 5)
    num_flashcards = st.slider("Number of flashcards", 5, 25, 10)

    st.divider()
    st.caption(
        "Your notes and API key are used only to call the OpenAI API for this "
        "session — nothing is saved to disk."
    )


# =========================================================
# 4. MAIN PAGE — TITLE + NOTES INPUT
# =========================================================

st.title("📚 AI Study Buddy")
st.write("Upload your notes, then generate a summary, a quiz, and flashcards — all in one place.")

MAX_CHARS = 20000  # keeps requests fast and affordable

st.subheader("1. Add your notes")
tab_upload, tab_paste = st.tabs(["📄 Upload a file", "✍️ Paste text"])

with tab_upload:
    uploaded_file = st.file_uploader("Upload a PDF or .txt file", type=["pdf", "txt"])
    if uploaded_file is not None:
        if uploaded_file.type == "application/pdf":
            extracted = extract_text_from_pdf(uploaded_file)
        else:
            extracted = uploaded_file.read().decode("utf-8", errors="ignore")

        if extracted.strip():
            st.session_state.notes_text = extracted
            st.success(f"Loaded {len(extracted):,} characters from **{uploaded_file.name}**.")
        else:
            st.error("Couldn't find any text in that file. Try a different file or paste text instead.")

with tab_paste:
    pasted = st.text_area("Paste your notes here", height=200, value="")
    if st.button("Use this text"):
        if pasted.strip():
            st.session_state.notes_text = pasted
            st.success(f"Loaded {len(pasted):,} characters of pasted text.")
        else:
            st.warning("Please paste some text first.")

# Show a preview + length check
if st.session_state.notes_text:
    with st.expander("Preview loaded notes"):
        st.text(st.session_state.notes_text[:2000] + ("..." if len(st.session_state.notes_text) > 2000 else ""))

    if len(st.session_state.notes_text) > MAX_CHARS:
        st.warning(
            f"Your notes are {len(st.session_state.notes_text):,} characters long. "
            f"Only the first {MAX_CHARS:,} characters will be used, to keep things fast and affordable."
        )

st.divider()

# =========================================================
# 5. GENERATE BUTTONS
# =========================================================

st.subheader("2. Generate study materials")

notes_ready = bool(st.session_state.notes_text.strip())
key_ready = bool(api_key.strip())

if not notes_ready:
    st.info("Add your notes above to unlock the buttons below.")
elif not key_ready:
    st.info("Enter your OpenAI API key in the sidebar to unlock the buttons below.")

col1, col2, col3 = st.columns(3)
notes_for_ai = st.session_state.notes_text[:MAX_CHARS]

with col1:
    if st.button("📝 Generate Summary", use_container_width=True, disabled=not (notes_ready and key_ready)):
        with st.spinner("Summarizing your notes..."):
            client = get_client(api_key, provider["base_url"])
            st.session_state.summary = generate_summary(client, model, notes_for_ai)

with col2:
    if st.button("❓ Generate Quiz", use_container_width=True, disabled=not (notes_ready and key_ready)):
        with st.spinner("Writing quiz questions..."):
            client = get_client(api_key, provider["base_url"])
            st.session_state.quiz = generate_quiz(client, model, notes_for_ai, num_quiz_questions)
            st.session_state.quiz_submitted = False

with col3:
    if st.button("🃏 Generate Flashcards", use_container_width=True, disabled=not (notes_ready and key_ready)):
        with st.spinner("Making flashcards..."):
            client = get_client(api_key, provider["base_url"])
            st.session_state.flashcards = generate_flashcards(client, model, notes_for_ai, num_flashcards)

st.divider()

# =========================================================
# 6. RESULTS — SUMMARY / QUIZ / FLASHCARDS
# =========================================================

result_tabs = st.tabs(["📝 Summary", "❓ Quiz", "🃏 Flashcards"])

# --- Summary tab ---------------------------------------------------------
with result_tabs[0]:
    if st.session_state.summary:
        st.markdown(st.session_state.summary)
    else:
        st.caption("Your summary will appear here once you click 'Generate Summary'.")

# --- Quiz tab -------------------------------------------------------------
with result_tabs[1]:
    quiz = st.session_state.quiz
    if quiz is None:
        st.caption("Your quiz will appear here once you click 'Generate Quiz'.")
    elif isinstance(quiz, list) and len(quiz) == 0:
        st.warning("The quiz came back empty. Try generating it again.")
    elif not isinstance(quiz, list):
        st.error("Something went wrong reading the quiz. Try generating it again.")
    else:
        with st.form("quiz_form"):
            user_answers = {}
            for i, q in enumerate(quiz):
                st.markdown(f"**{i + 1}. {q.get('question', '')}**")
                options = q.get("options", [])
                # store just the letter (A/B/C/D) the user picked
                choice = st.radio(
                    label="Choose one:",
                    options=[opt[0] for opt in options],  # "A", "B", "C", "D"
                    format_func=lambda letter, opts=options: next(
                        (o for o in opts if o.startswith(letter)), letter
                    ),
                    key=f"quiz_q_{i}",
                    index=None,
                    label_visibility="collapsed",
                )
                user_answers[i] = choice
                st.write("")

            submitted = st.form_submit_button("✅ Check my answers")
            if submitted:
                st.session_state.quiz_submitted = True

        if st.session_state.quiz_submitted:
            score = 0
            st.markdown("### Results")
            for i, q in enumerate(quiz):
                correct = q.get("correct_answer", "")
                given = user_answers.get(i)
                is_correct = given == correct
                score += int(is_correct)
                icon = "✅" if is_correct else "❌"
                st.markdown(f"{icon} **Q{i + 1}:** correct answer is **{correct}** — {q.get('explanation', '')}")
            st.success(f"Score: {score} / {len(quiz)}")

# --- Flashcards tab ---------------------------------------------------------
with result_tabs[2]:
    cards = st.session_state.flashcards
    if cards is None:
        st.caption("Your flashcards will appear here once you click 'Generate Flashcards'.")
    elif isinstance(cards, list) and len(cards) == 0:
        st.warning("The flashcards came back empty. Try generating them again.")
    elif not isinstance(cards, list):
        st.error("Something went wrong reading the flashcards. Try generating them again.")
    else:
        st.caption("Click a card to reveal the answer.")
        # Show cards in a simple two-column grid using expanders as "flip" cards.
        left, right = st.columns(2)
        for i, card in enumerate(cards):
            target_col = left if i % 2 == 0 else right
            with target_col:
                with st.expander(f"🃏 {card.get('front', '')}"):
                    st.write(card.get("back", ""))