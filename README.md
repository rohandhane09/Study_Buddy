# 📚 AI Study Buddy

A simple Streamlit app that turns your notes into a summary, a quiz, and flashcards using the OpenAI API.

## Setup

1. **Install Python packages** (from this folder):
   ```bash
   pip install -r requirements.txt
   ```

2. **Get an API key — free option available:**
   - **Groq (free, no credit card):** sign up at https://console.groq.com/keys
     and create a key. Groq's free tier gives you fast access to open models
     like Llama 3.3 70B — plenty for summaries, quizzes, and flashcards.
   - **OpenAI (paid):** get a key at https://platform.openai.com/api-keys.
     Note the OpenAI API is billed separately from ChatGPT Plus, and requires
     you to add credit before it will respond.

3. **Run the app**:
   ```bash
   streamlit run app.py
   ```
   This opens the app in your browser, usually at `http://localhost:8501`.

4. In the sidebar, pick your **Provider** (Groq or OpenAI) and paste your key.
   You can also set it as an environment variable so you don't have to paste
   it each time (only picked up automatically for the OpenAI provider):
   ```bash
   export OPENAI_API_KEY="sk-..."      # Mac/Linux
   setx OPENAI_API_KEY "sk-..."        # Windows
   ```

## How to use it

1. Upload a PDF or `.txt` file of your notes, or paste text directly.
2. Click **Generate Summary**, **Generate Quiz**, or **Generate Flashcards**.
3. Switch between the **Summary / Quiz / Flashcards** tabs to view results.
4. For the quiz, pick an answer for each question and click **Check my answers** to see your score.
5. For flashcards, click each card to flip it and reveal the answer.

## Notes on cost and limits

- The app uses `gpt-4o-mini` by default (fast and inexpensive). You can switch
  models in the sidebar.
- Notes longer than 20,000 characters are trimmed to keep requests fast and
  affordable — a heads-up is shown if this happens.
- Nothing is saved to disk; your notes and API key only live in the browser
  session while the app is open.

## Customizing

- Change `MAX_CHARS` in `app.py` to allow longer notes.
- Adjust the number of quiz questions/flashcards with the sidebar sliders.
- Edit the prompt text inside `generate_summary`, `generate_quiz`, and
  `generate_flashcards` in `app.py` to change tone, format, or difficulty.
