import json, os, re, uuid
from datetime import datetime, timezone
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
from supabase import create_client

st.set_page_config(page_title='AI Study Buddy', page_icon='📚', layout='wide')

# ---------- Login ----------
if not st.user.is_logged_in:
    st.markdown("<div style='text-align:center;padding:70px 20px 30px'><div style='font-size:64px'>📚</div><h1>AI Study Buddy</h1><p>Save your summaries, quizzes and flashcards and continue them later.</p></div>", unsafe_allow_html=True)
    _, c, _ = st.columns([1,2,1])
    with c:
        st.button('🔐 Continue with Google', use_container_width=True, type='primary', on_click=st.login)
    st.stop()

def uv(key, default=''):
    try: return st.user.get(key) or default
    except Exception: return default

USER_ID = uv('sub') or uv('email')
USER_EMAIL = uv('email', 'Unknown email')
USER_NAME = uv('name') or uv('given_name') or 'Student'
if not USER_ID:
    st.error('Could not identify your Google account. Please sign in again.')
    st.stop()

# ---------- Session state ----------
defaults = {
    'notes_text':'', 'summary':'', 'quiz':None, 'flashcards':None,
    'quiz_submitted':False, 'quiz_answers':{}, 'quiz_score':None,
    'current_session_id':None, 'current_session_title':'New Study Session'
}
for k,v in defaults.items():
    if k not in st.session_state: st.session_state[k]=v

def new_session():
    for k,v in defaults.items(): st.session_state[k]=v

def secret(name):
    try: v=st.secrets.get(name)
    except Exception: v=None
    return v or os.environ.get(name,'')

# ---------- Supabase ----------
SUPABASE_URL=secret('SUPABASE_URL')
SUPABASE_KEY=secret('SUPABASE_KEY')
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error('Supabase is not configured. Add SUPABASE_URL and SUPABASE_KEY to Streamlit Secrets.')
    st.stop()
try:
    supabase=create_client(SUPABASE_URL,SUPABASE_KEY)
except Exception as e:
    st.error(f'Could not connect to Supabase: {e}')
    st.stop()

def title_from_notes(text, fallback='New Study Session'):
    lines=[re.sub(r'^[#*\-\d.)\s]+','',x).strip() for x in text.splitlines()]
    lines=[x for x in lines if x]
    if not lines: return fallback
    t=re.sub(r'\s+',' ',lines[0])
    return t[:55].rstrip()+('...' if len(t)>55 else '')

def recent_sessions():
    try:
        r=(supabase.table('study_sessions').select('id,title,updated_at,quiz_score,quiz_total')
           .eq('user_id',USER_ID).order('updated_at',desc=True).limit(20).execute())
        return r.data or []
    except Exception as e:
        st.sidebar.error(f'Could not load sessions: {e}'); return []

def save_session():
    if not st.session_state.notes_text.strip(): return None
    if not st.session_state.current_session_title or st.session_state.current_session_title=='New Study Session':
        st.session_state.current_session_title=title_from_notes(st.session_state.notes_text)
    q=st.session_state.quiz
    payload={
        'user_id':USER_ID,'user_email':USER_EMAIL,'user_name':USER_NAME,
        'title':st.session_state.current_session_title,
        'notes_text':st.session_state.notes_text,
        'summary':st.session_state.summary or '', 'quiz':q,
        'flashcards':st.session_state.flashcards,
        'quiz_submitted':bool(st.session_state.quiz_submitted),
        'quiz_answers':st.session_state.quiz_answers or {},
        'quiz_score':st.session_state.quiz_score,
        'quiz_total':len(q) if isinstance(q,list) else None,
        'updated_at':datetime.now(timezone.utc).isoformat()
    }
    try:
        sid=st.session_state.current_session_id
        if sid:
            r=(supabase.table('study_sessions').update(payload).eq('id',sid).eq('user_id',USER_ID).execute())
            if not r.data: sid=None
        if not sid:
            payload['id']=str(uuid.uuid4())
            r=supabase.table('study_sessions').insert(payload).execute()
            sid=r.data[0]['id']; st.session_state.current_session_id=sid
        return sid
    except Exception as e:
        st.error(f'Could not save session: {e}'); return None

def load_session(sid):
    try:
        r=(supabase.table('study_sessions').select('*').eq('id',sid).eq('user_id',USER_ID).single().execute())
        x=r.data
        if not x: return False
        st.session_state.current_session_id=x['id']; st.session_state.current_session_title=x.get('title') or 'Study Session'
        st.session_state.notes_text=x.get('notes_text') or ''; st.session_state.summary=x.get('summary') or ''
        st.session_state.quiz=x.get('quiz'); st.session_state.flashcards=x.get('flashcards')
        st.session_state.quiz_submitted=bool(x.get('quiz_submitted',False)); st.session_state.quiz_answers=x.get('quiz_answers') or {}
        st.session_state.quiz_score=x.get('quiz_score'); return True
    except Exception as e:
        st.error(f'Could not load session: {e}'); return False

def delete_session(sid):
    try:
        supabase.table('study_sessions').delete().eq('id',sid).eq('user_id',USER_ID).execute()
        if st.session_state.current_session_id==sid: new_session()
        return True
    except Exception as e:
        st.error(f'Could not delete session: {e}'); return False

# ---------- Existing AI logic ----------
def extract_text_from_pdf(f):
    return '\n'.join((p.extract_text() or '') for p in PdfReader(f).pages)

PROVIDERS={
    'Groq (Free — no card needed)':{'base_url':'https://api.groq.com/openai/v1','models':['openai/gpt-oss-20b','openai/gpt-oss-120b']},
    'OpenAI (paid)':{'base_url':None,'models':['gpt-4o-mini','gpt-4o','gpt-4.1-mini']}
}
def client_for(key,url): return OpenAI(api_key=key,base_url=url) if url else OpenAI(api_key=key)
def ask(client,model,system,user):
    r=client.chat.completions.create(model=model,temperature=.4,messages=[{'role':'system','content':system},{'role':'user','content':user}])
    return r.choices[0].message.content
def parse_json(raw):
    t=raw.strip()
    if t.startswith('```'):
        t=t.strip('`')
        if t.lower().startswith('json'): t=t[4:]
    try: return json.loads(t)
    except json.JSONDecodeError: return None

def generate_summary(c,m,n):
    return ask(c,m,'You are a friendly, encouraging study assistant. You turn messy student notes into clear, well-organized summaries.',f'''Summarize the following notes for a student studying for an exam.
- Use short Markdown headings.
- Use bullet points, not long paragraphs.
- Bold key terms and definitions.
- Aim for roughly a third the length of the original.

NOTES:\n"""\n{n}\n"""''')

def generate_quiz(c,m,n,count):
    raw=ask(c,m,'You write multiple-choice quiz questions. Respond ONLY with valid JSON, no markdown fences.',f'''Read these notes and write {count} multiple-choice questions testing understanding.
Return ONLY a JSON array exactly like:
[{{"question":"What is ...?","options":["A) first","B) second","C) third","D) fourth"],"correct_answer":"A","explanation":"One short sentence explaining why."}}]

NOTES:\n"""\n{n}\n"""''')
    return parse_json(raw)

def generate_flashcards(c,m,n,count):
    raw=ask(c,m,'You write concise active-recall flashcards. Respond ONLY with valid JSON, no markdown fences.',f'''Read these notes and create {count} flashcards. Each has a short front and back.
Return ONLY a JSON array like:
[{{"front":"What is photosynthesis?","back":"The process plants use to turn light into energy."}}]

NOTES:\n"""\n{n}\n"""''')
    return parse_json(raw)

# ---------- Sidebar ----------
with st.sidebar:
    st.header('👤 Account')
    st.write(f'**{USER_NAME}**')
    st.caption(USER_EMAIL)
    st.button('🚪 Log out',use_container_width=True,on_click=st.logout)
    st.divider()
    st.header('🕘 Recent Sessions')
    if st.button('➕ New Study Session',use_container_width=True): new_session(); st.rerun()
    rows=recent_sessions()
    if rows:
        options={'— Select a session —':None}
        for r in rows:
            label=r['title']
            if label in options: label=f"{label} ({str(r['id'])[:6]})"
            options[label]=r['id']
        chosen=st.selectbox('Open a previous session',list(options.keys()))
        if options[chosen]:
            a,b=st.columns(2)
            with a:
                if st.button('📂 Open',use_container_width=True):
                    if load_session(options[chosen]): st.rerun()
            with b:
                if st.button('🗑️ Delete',use_container_width=True):
                    if delete_session(options[chosen]): st.rerun()
    else: st.caption('No saved sessions yet.')
    if st.session_state.current_session_id: st.caption(f"Current: **{st.session_state.current_session_title}**")
    st.divider(); st.header('⚙️ Settings')
    provider_name=st.selectbox('Provider',list(PROVIDERS.keys()),index=0); provider=PROVIDERS[provider_name]
    api_key=secret('GROQ_API_KEY' if 'Groq' in provider_name else 'OPENAI_API_KEY')
    if api_key: st.success('🔐 API key loaded securely')
    else: st.error('API key is not configured. Add it to Streamlit Secrets.')
    model=st.selectbox('Model',provider['models'],index=0)
    st.divider(); num_quiz_questions=st.slider('Number of quiz questions',3,15,5); num_flashcards=st.slider('Number of flashcards',5,25,10)

# ---------- Main ----------
st.title('📚 AI Study Buddy')
st.write(f'Welcome, **{USER_NAME}**! Upload notes and create a summary, quiz and flashcards.')
MAX_CHARS=20000
st.subheader('1. Add your notes')
tab_upload,tab_paste=st.tabs(['📄 Upload a file','✍️ Paste text'])
with tab_upload:
    uploaded=st.file_uploader('Upload a PDF or .txt file',type=['pdf','txt'])
    if uploaded:
        text=extract_text_from_pdf(uploaded) if uploaded.type=='application/pdf' else uploaded.read().decode('utf-8',errors='ignore')
        if text.strip():
            st.session_state.notes_text=text
            if not st.session_state.current_session_id or st.session_state.current_session_title=='New Study Session':
                st.session_state.current_session_title=title_from_notes(text,uploaded.name.rsplit('.',1)[0])
            st.success(f'Loaded {len(text):,} characters from **{uploaded.name}**.')
        else: st.error("Couldn't find any text in that file.")
with tab_paste:
    pasted=st.text_area('Paste your notes here',height=200)
    if st.button('Use this text'):
        if pasted.strip():
            st.session_state.notes_text=pasted
            if not st.session_state.current_session_id or st.session_state.current_session_title=='New Study Session': st.session_state.current_session_title=title_from_notes(pasted)
            st.success(f'Loaded {len(pasted):,} characters.')
        else: st.warning('Please paste some text first.')
if st.session_state.notes_text:
    with st.expander('Preview loaded notes'):
        p=st.session_state.notes_text[:2000]; st.text(p+('...' if len(st.session_state.notes_text)>2000 else ''))
    if len(st.session_state.notes_text)>MAX_CHARS: st.warning(f'Only the first {MAX_CHARS:,} characters will be sent to the AI.')
st.divider(); st.subheader('2. Generate study materials')
ready=bool(st.session_state.notes_text.strip()) and bool(api_key.strip()); n=st.session_state.notes_text[:MAX_CHARS]
c1,c2,c3=st.columns(3)
with c1:
    if st.button('📝 Generate Summary',use_container_width=True,disabled=not ready):
        with st.spinner('Summarizing your notes...'): st.session_state.summary=generate_summary(client_for(api_key,provider['base_url']),model,n)
        save_session(); st.success('Summary saved to Recent Sessions.')
with c2:
    if st.button('❓ Generate Quiz',use_container_width=True,disabled=not ready):
        with st.spinner('Writing quiz questions...'): st.session_state.quiz=generate_quiz(client_for(api_key,provider['base_url']),model,n,num_quiz_questions)
        st.session_state.quiz_submitted=False; st.session_state.quiz_answers={}; st.session_state.quiz_score=None; save_session(); st.success('Quiz saved to Recent Sessions.')
with c3:
    if st.button('🃏 Generate Flashcards',use_container_width=True,disabled=not ready):
        with st.spinner('Making flashcards...'): st.session_state.flashcards=generate_flashcards(client_for(api_key,provider['base_url']),model,n,num_flashcards)
        save_session(); st.success('Flashcards saved to Recent Sessions.')
st.divider()

# ---------- Results ----------
t1,t2,t3=st.tabs(['📝 Summary','❓ Quiz','🃏 Flashcards'])
with t1:
   if st.session_state.summary:
    st.markdown(st.session_state.summary)
else:
    st.caption("Your summary will appear here once you click 'Generate Summary'.")
with t2:
    quiz=st.session_state.quiz
    if quiz is None: st.caption("Your quiz will appear here once you click 'Generate Quiz'.")
    elif not isinstance(quiz,list) or not quiz: st.error('The quiz is empty or invalid. Try generating it again.')
    else:
        with st.form('quiz_form'):
            answers={}
            for i,q in enumerate(quiz):
                st.markdown(f"**{i+1}. {q.get('question','')}**"); opts=q.get('options',[])
                answers[i]=st.radio('Choose one:',[o[0] for o in opts],format_func=lambda letter,opts=opts: next((o for o in opts if o.startswith(letter)),letter),key=f"quiz_{st.session_state.current_session_id}_{i}",index=None,label_visibility='collapsed')
            submitted=st.form_submit_button('✅ Check my answers')
        if submitted:
            st.session_state.quiz_answers={str(k):v for k,v in answers.items()}
            st.session_state.quiz_score=sum(answers.get(i)==q.get('correct_answer','') for i,q in enumerate(quiz))
            st.session_state.quiz_submitted=True; save_session(); st.rerun()
        if st.session_state.quiz_submitted:
            score=st.session_state.quiz_score or 0; st.markdown('### Results')
            for i,q in enumerate(quiz):
                given=st.session_state.quiz_answers.get(str(i)); correct=q.get('correct_answer',''); icon='✅' if given==correct else '❌'
                st.markdown(f"{icon} **Q{i+1}:** correct answer is **{correct}** — {q.get('explanation','')}")
            st.success(f'Score: {score} / {len(quiz)}')
with t3:
    cards=st.session_state.flashcards
    if cards is None: st.caption("Your flashcards will appear here once you click 'Generate Flashcards'.")
    elif not isinstance(cards,list) or not cards: st.error('The flashcards are empty or invalid. Try generating them again.')
    else:
        st.caption('Click a card to reveal the answer.'); left,right=st.columns(2)
        for i,card in enumerate(cards):
            with (left if i%2==0 else right):
                with st.expander(f"🃏 {card.get('front','')}"): st.write(card.get('back',''))

if st.session_state.current_session_id:
    st.divider(); st.caption(f"☁️ Saved in Supabase as **{st.session_state.current_session_title}**")
