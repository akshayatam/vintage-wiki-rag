# vintage-wiki-rag ⌨️

A retrieval-augmented generation (RAG) app for exploring **vintage mechanical keyboard knowledge**.  
Built on embeddings + FAISS vector search, it lets you query the Mechanical Keyboard Club Wiki (the community-driven successor to Deskthority).  

https://github.com/user-attachments/assets/bfaa6a53-e3d5-4b40-98c3-a9e6471d4963

---

## 🔍 Current Features
- Indexed **~160 Alps Electric switch pages** (e.g., SKCL, SKCM, plate spring, magnetic reed).
- Semantic search using dense embeddings with **FAISS** vector indexing.
- Ranked top-k retrieval with direct links back to original wiki sources.
- **FastAPI backend** serving retrieval endpoints.
- **Streamlit UI** for interactive querying and exploration.

## 🧠 System Overview
- Unstructured wiki pages are embedded using **SentenceTransformers**.
- Embeddings are stored and queried via a **FAISS** vector index.
- A FastAPI service handles retrieval and ranking.
- A Streamlit frontend allows users to issue natural-language queries and inspect results.

This design separates ingestion, retrieval, and UI concerns, making the system easy to extend or deploy in different environments.

## 🛠️ Tech Stack
- **Python** (3.11+)
- **FastAPI** – backend API
- **Streamlit** – interactive UI
- **SentenceTransformers** – embedding generation
- **FAISS** – vector similarity search
- **Uvicorn** – ASGI server

## 🐧 Environment
- Developed and tested on **Arch Linux**
- Designed to run in any Linux or macOS environment

---

## ▶️ Running the Project Locally

### 1. Clone the repository
```bash
git clone https://github.com/akshayatam/vintage-wiki-rag.git
cd vintage-wiki-rag
```

### 2. Create and activate a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Start the application
```bash
chmod +x run.sh
./run.sh
```

The script (`run.sh`):
- Initializes the virtual environment
- Installs dependencies
- Starts the FastAPI backend with Uvicorn
- Launches the Streamlit UI

## 🧪 Coding Sample Note

This repository is intended as a coding sample demonstrating:
- Python development in a Linux environment
- Backend + frontend integration
- Handling of structured and unstructured data
- Practical application of ML concepts (embeddings, retrieval)
- Clean project structure and reproducible setup
- A demo video of the application running on Linux is included above.

## 🚧 Future Work

- Expand ingestion to include all Mechanical Keyboard Club Wiki pages, including Cherry, Topre, and other switch families (~3,000+ pages).
- Add retrieval evaluation metrics such as Recall@k and Mean Reciprocal Rank (MRR).
- Improve answer synthesis with source-aware citations.
- Transition from pure document retrieval to a ReAct-style agentic RAG system, where the model can reason, decide actions, and iteratively query tools.
- Evolve the system into a chatbot-style interface, enabling multi-turn interactions instead of one-shot semantic search queries.

📌 Motivation

This project combines personal interest with applied AI engineering to explore how modern retrieval and agent-based techniques can unlock value from large, messy, community-driven knowledge bases.

---