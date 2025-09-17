# vintage-wiki-rag ⌨️

A retrieval-augmented generation (RAG) app for exploring **vintage mechanical keyboard knowledge**.  
Built on embeddings + FAISS vector search, it lets you query the Mechanical Keyboard Club Wiki (the community-driven successor to Deskthority).  

https://github.com/user-attachments/assets/bfaa6a53-e3d5-4b40-98c3-a9e6471d4963

---

### 🔎 Current Features
- Indexed **~160 Alps Electric switch pages** (e.g. SKCL, SKCM, plate spring, magnetic reed).
- Fast semantic search with top-k ranked answers.
- Streamlit UI + FastAPI backend, linking directly to source wiki pages.

### 🚧 Working On
- Expanding to **Cherry switches** -> full keyboard data (~3,000 pages).
- Adding **evaluation metrics** (Recall@k, MRR) for retrieval quality.
- Enabling broader RAG workflows (answer synthesis, citations).

---

### 🛠️ Tech Stack
- **Python**, **Streamlit**, **FastAPI**  
- **SentenceTransformers** for embeddings  
- **FAISS** for vector search  
