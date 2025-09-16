# ui/app.py
import streamlit as st
import requests
import textwrap 

API = st.secrets.get("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Vintage Wiki RAG", page_icon="⌨️") 

# Function to intitate search when pressed Enter/Return 
def do_search(): 
    q = st.session_state.query_input.strip()
    k = st.session_state.get("k_results", 5)
    if not q:
        return
    try:
        r = requests.post(f"{API}/search", json={"query": q, "k": k}, timeout=30)
        r.raise_for_status()
        data = r.json()
        st.session_state.history.append((q, data["passages"]))
    except Exception as e:
        st.error(f"Request failed: {e}")

# Tiny CSS just for centering the title/caption
st.markdown("""
<style>
.centered-title { text-align:center; font-weight:800; font-size:4.1rem; }
.centered-caption { text-align:center; margin-top:4px; opacity:0.9; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="centered-title">⌨️ Vintage Wiki RAG</div>', unsafe_allow_html=True)
st.markdown('<div class="centered-caption">Search the community wiki with citations</div>', unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = [] 

st.write("### Ask a question about vintage keyboards")
q = st.text_input(
    "Question",
    placeholder="e.g., Which Apple keyboards used Orange Alps?",
    label_visibility="collapsed",
    help="Tip: include switch name + model for better citations.", 
    key="query_input", 
    on_change=do_search
)

k = st.slider("Results", 3, 10, 5)

col1, col2 = st.columns([1, 2])
with col1:
    if st.button("Search"):
        try:
            r = requests.post(f"{API}/search", json={"query": q, "k": k}, timeout=30)
            r.raise_for_status()
            data = r.json()
            st.session_state.history.append((q, data["passages"]))
        except Exception as e:
            st.error(f"Request failed: {e}")

with col2:
    st.write("")

for qi, (qq, passages) in enumerate(reversed(st.session_state.history), 1):
    st.subheader(f"Q: {qq}")
    for i, p in enumerate(passages, 1):
        with st.expander(f"[{i}] {p['title']} — {p['section']} (score={p['score']:.3f})", expanded=(i==1)):
            st.markdown(f"[Open source]({p['url']})")
            st.write(textwrap.shorten(p["text"].replace("\n", " "), width=900, placeholder=" ..."))
    st.markdown("---")
