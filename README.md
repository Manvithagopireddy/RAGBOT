# 🤖 AI Tech Assistant

### AI-Powered Assistant for Artificial Intelligence, AI Tools & Emerging Technologies using Retrieval-Augmented Generation (RAG)

An advanced, production-ready AI Tech Assistant that provides detailed, cited answers to complex technical questions about Artificial Intelligence, Machine Learning, Generative AI, Large Language Models (LLMs), AI Agents, Prompt Engineering, and Vector Databases. 

It implements a local **Retrieval-Augmented Generation (RAG)** architecture using a **FAISS vector database** populated from PDF documentations, and resolves queries with high factual grounding using the **Google Gemini 2.5 Flash** model.

---

## 🏗️ Architecture

The pipeline processes user questions dynamically to produce cited, high-confidence answers:

```text
                     AI Documentation
                 Research Papers / PDFs
                          │
                          ▼
                  PyPDFLoader (LangChain)
                          │
                          ▼
          RecursiveCharacterTextSplitter
                          │
                          ▼
        HuggingFace Sentence Transformers
                          │
                          ▼
                FAISS Vector Database
                          │
─────────────────────────────────────────────────────
                    User Question
                          │
                          ▼
           Rephrase Standalone Question
                          │
                          ▼
          Convert Question into Embedding
                          │
                          ▼
           Retrieve Relevant Chunks (Top K)
                          │
                          ▼
          Prompt + Retrieved AI Context
                          │
                          ▼
             Google Gemini 2.5 Flash
                          │
                          ▼
               AI Generated Response
```

---

## ✨ Features

- **Interactive AI Chat:** A ChatGPT-style streaming UI with Markdown formatting, clean headers, custom user/assistant avatars, copy/download utilities, and code block formatting.
- **Resilient Hybrid Search Routing:** Dynamically prioritizes local **FAISS Knowledge Base** queries. If similarity scores fall below the configurable threshold, the pipeline automatically falls back to **Google Search Grounding** (if enabled), with a second fail-safe fallback to **pure LLM** generation if search APIs are unsupported or throw errors.
- **Universal Responsiveness:** Designed with custom media queries supporting desktop, tablet, and mobile breakpoints. Stacks columns vertically on tablet/mobile screens (pushing the Details panel cleanly to the bottom) while maintaining inline horizontal action button rows inside chat messages.
- **Persistent State & Citation Restoration:** Persists session settings (model, temperature, active AI persona) and full chat history inside a local **SQLite database**, correctly parsing and restoring source types (`📄 Knowledge Base`, `🌐 Web Search`, `🧠 AI General Knowledge`), web source links, and confidence parameters on load.
- **Dynamic Retrieval Citations:** Highlights precisely which source documents (and which specific pages/URLs) were retrieved to compile the answers.
- **Retrieval Confidence Gauge:** Shows a percentage confidence rating based on vector database distance metrics.
- **Suggested Follow-up Questions:** Dynamically extracts related recommendations from responses, enabling easy conversational progression.
- **Index Management:** Directly rebuild and re-index your vector database from the sidebar configuration panel.
- **Premium Glassmorphic Styling:** A modern, custom dark/light theme complete with fluid transitions, blur filters, and vibrant color gradients.

---

## 📂 Folder Structure

```text
AI_Tech_Assistant/
│
├── app.py                     # Main application entry point
├── requirements.txt           # Project dependencies
├── README.md                  # Project documentation
├── .env                       # Local environment configurations (private)
├── .env.example               # Example configurations
├── .gitignore                 # Files excluded from git
│
├── config/
│   ├── settings.py            # Global variables, paths, and hyperparameters
│   └── prompts.py             # System prompt templates
│
├── knowledge_base/            # Folder containing indexing PDFs
│   ├── AI_Basics.pdf
│   ├── LLM_Guide.pdf
│   └── ...
│
├── vector_store/              # FAISS index binary caches
│   ├── index.faiss
│   └── index.pkl
│
├── src/                       # Backend RAG logic
│   ├── document_loader.py     # PDF parsing loader
│   ├── text_splitter.py       # Recursive text splitter
│   ├── embeddings.py          # Sentence-Transformers embeddings loader
│   ├── vector_store.py        # FAISS manager (build, load, save)
│   ├── retriever.py           # Context retrieval and citation utility
│   ├── llm.py                 # ChatGoogleGenerativeAI instantiator
│   ├── memory.py              # Contextual message logs storage
│   ├── rag_pipeline.py        # End-to-end retrieval and streaming manager
│   ├── utils.py               # Formatting, confidence & parsing utilities
│   └── logger.py              # Central log system
│
├── ui/                        # Frontend components
│   ├── home.py                # Dashboard page with suggestions
│   ├── chat.py                # Main chat window with stream rendering
│   ├── comparison.py          # Tool comparison matrix page
│   ├── sidebar.py             # Control configurations sidebar
│   └── styles.css             # Custom glassmorphic CSS styles
│
└── scripts/                   # Setup and verification tools
    ├── generate_mock_knowledge.py   # Seeding script to create realistic PDFs
    └── test_pipeline.py             # Independent RAG pipeline testing script
```

---

## 🛠️ Technology Stack

| Category              | Technology                        |
| --------------------- | --------------------------------- |
| Programming Language  | Python 3.14                       |
| Frontend              | Streamlit                         |
| LLM                   | Google Gemini 2.5 Flash           |
| Framework             | LangChain                         |
| Embeddings            | HuggingFace Sentence Transformers |
| Vector Database       | FAISS                             |
| Document Loader       | PyPDFLoader                       |
| Text Splitter         | RecursiveCharacterTextSplitter    |
| PDF Processing        | PyPDF                             |
| Environment Variables | python-dotenv                     |
| Styling               | CSS + HTML                        |

---

## 🚀 Setup & Execution

### 1. Create a Virtual Environment

Initialize the virtual environment:
```bash
python -m venv venv
```

Activate it:
- **Windows:**
  ```powershell
  venv\Scripts\activate
  ```
- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

### 2. Install Dependencies

Install all dependencies in the virtual environment:
```bash
pip install -r requirements.txt
```

### 3. Configure API Key

Create a `.env` file in the root directory (based on `.env.example`) and add your Google Gemini API Key:
```env
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
```

### 4. Seed the Knowledge Base

Populate `knowledge_base/` with high-quality technical PDFs:
```bash
python scripts/generate_mock_knowledge.py
```
This script programmatically writes 14 structured, highly-detailed documents concerning Agent workflows, MCP, RAG, embeddings, APIs, and models.

### 5. Run the Backend Diagnostic Test (Optional)

Verify that your vector retrieval and Gemini connections work in isolation:
```bash
python scripts/test_pipeline.py
```

### 6. Run the Application

Launch the Streamlit web server:
```bash
streamlit run app.py
```
This launches a browser session at `http://localhost:8501`.
