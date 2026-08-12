import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_pdf(filepath: Path, title: str, content: str):
    """Generates a structured PDF file using ReportLab."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(filepath), pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'PDFTitleStyle',
        parent=styles['Heading1'],
        fontSize=22,
        leading=26,
        spaceAfter=15,
        textColor='#1E3A8A' # Dark blue
    )
    
    h2_style = ParagraphStyle(
        'PDFH2Style',
        parent=styles['Heading2'],
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=6,
        textColor='#0D9488' # Teal
    )
    
    body_style = ParagraphStyle(
        'PDFBodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    )
    
    story = []
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 10))
    
    for line in content.strip().split('\n\n'):
        if not line.strip():
            continue
        if line.startswith('## '):
            story.append(Paragraph(line.replace('## ', ''), h2_style))
        else:
            story.append(Paragraph(line.strip(), body_style))
            
    doc.build(story)

# Content dictionary for generating the 14 documents
DOCUMENTS_CONTENT = {
    "AI_Basics.pdf": (
        "Introduction to Artificial Intelligence and Machine Learning",
        "## Core Concepts of AI\n"
        "Artificial Intelligence (AI) refers to the simulation of human intelligence in machines that are programmed to think and learn. "
        "AI spans subfields including Machine Learning (ML), Deep Learning (DL), Natural Language Processing (NLP), and Computer Vision.\n\n"
        "## Machine Learning Paradigms\n"
        "Machine Learning is divided into three primary paradigms:\n"
        "1. Supervised Learning: The model learns from labeled training data (inputs and corresponding targets), such as linear regression, decision trees, and support vector machines.\n"
        "2. Unsupervised Learning: The model finds hidden patterns or intrinsic structures in input data without labels. Examples include K-Means clustering, Principal Component Analysis (PCA), and autoencoders.\n"
        "3. Reinforcement Learning: An agent learns to make decisions by performing actions in an environment to maximize cumulative reward.\n\n"
        "## Deep Learning and Neural Networks\n"
        "Deep Learning utilizes multi-layered artificial neural networks (ANNs) inspired by the human brain. "
        "Key architectures include Convolutional Neural Networks (CNNs) for spatial and image data, and Recurrent Neural Networks (RNNs) for sequential data."
    ),
    "LLM_Guide.pdf": (
        "Comprehensive Guide to Large Language Models (LLMs)",
        "## The Transformer Architecture\n"
        "Large Language Models are based on the Transformer architecture introduced by Vaswani et al. in 2017. "
        "The architecture relies on the Self-Attention mechanism, which computes representations of input sequences by focusing on different parts of the same sequence.\n\n"
        "## Popular LLM Families\n"
        "State-of-the-art LLMs include:\n"
        "- OpenAI GPT: Generative Pre-trained Transformer series (e.g., GPT-4o) trained on large datasets using autoregressive objectives.\n"
        "- Google Gemini: Multimodal native models (Gemini 1.5/2.5 Pro and Flash) capable of parsing text, audio, images, and video.\n"
        "- Anthropic Claude: High-reasoning model family (Claude 3.5 Sonnet) designed around constitutional AI for safety.\n"
        "- Open-Weights Models: Meta's Llama series, Mistral, and Google's Gemma models which can be deployed locally.\n\n"
        "## Fine-Tuning and Parameter-Efficient Adaptation\n"
        "Fine-tuning adapts a pre-trained model to specific tasks. "
        "Parameter-Efficient Fine-Tuning (PEFT) methods, like Low-Rank Adaptation (LoRA), insert small, trainable matrices into Transformer layers while freezing the base weights, reducing VRAM needs."
    ),
    "LangChain.pdf": (
        "LangChain Framework Documentation",
        "## Overview of LangChain\n"
        "LangChain is an open-source framework designed to simplify the creation of applications using Large Language Models. "
        "It provides modular components, integrations, and unified interfaces to build complex chains and agents.\n\n"
        "## Core Elements\n"
        "1. Model I/O: Interfaces for working with Chat Models, LLMs, Prompts, and Output Parsers.\n"
        "2. Retrieval: Standardized tools to load documents (Document Loaders), split text (Text Splitters), generate vectors (Embeddings), and search databases (Vector Stores).\n"
        "3. LangChain Expression Language (LCEL): A declarative language for chaining components together using pipe operators (|), enabling out-of-the-box streaming and batching.\n"
        "4. Chains and Memory: Abstract workflows that combine multiple LLM steps, and memory variables to persist conversation history across user interactions."
    ),
    "LangGraph.pdf": (
        "LangGraph: Building Cyclic Agent Workflows",
        "## Introducing LangGraph\n"
        "LangGraph is an extension of LangChain designed to build stateful, multi-actor applications with cyclic control flows. "
        "Unlike standard linear chains, LangGraph allows modeling loops and complex graphs, which are common in advanced agent architectures.\n\n"
        "## Key Architecture Components\n"
        "- State: A shared schema or dictionary representing the current context, updated dynamically by graph execution nodes.\n"
        "- Nodes: Functions or agent steps that receive the current state, perform operations, and return updates to the state.\n"
        "- Edges: Connections between nodes. Conditional edges determine which node to visit next based on the state output.\n\n"
        "## Human-in-the-Loop Operations\n"
        "LangGraph features native support for interrupts, enabling human approval or manual input correction before proceeding past specific state transitions."
    ),
    "CrewAI.pdf": (
        "CrewAI: Multi-Agent Collaboration Framework",
        "## Overview of CrewAI\n"
        "CrewAI is a framework for orchestrating role-playing, autonomous AI agents. "
        "It enables agents to collaborate, share tasks, and delegate responsibilities to solve complex multi-step problems.\n\n"
        "## Fundamental Concepts\n"
        "- Agent: A structured LLM-powered entity with a specific Role, Goal, Backstory, and set of tools (e.g., search tools, file tools).\n"
        "- Task: A concrete assignment representing work to be done. Tasks have a description, expected output, and can be assigned to specific agents.\n"
        "- Crew: A collection of agents and tasks working together sequentially or hierarchically to achieve a objective.\n\n"
        "## Agent Memory and Delegation\n"
        "CrewAI supports short-term, long-term, and entity memory, allowing agents to retain context. "
        "Agents can also delegate tasks to other agents dynamically within a running Crew structure."
    ),
    "Prompt_Engineering.pdf": (
        "Advanced Prompt Engineering Techniques",
        "## Foundational Strategies\n"
        "Prompt Engineering is the practice of structuring inputs to LLMs to elicit desired outputs. "
        "Standard strategies include Zero-Shot prompting (asking for response with no examples) and Few-Shot prompting (providing input-output examples).\n\n"
        "## Advanced Reasoning Frameworks\n"
        "- Chain-of-Thought (CoT): Encourages the model to output intermediate reasoning steps before the final answer, improving math and logic reasoning.\n"
        "- ReAct (Reason + Act): Combines reasoning traces and action steps, enabling the model to search external databases or use APIs and evaluate results before generating replies.\n"
        "- Tree of Thoughts (ToT): Extends CoT by exploring multiple reasoning paths (branches) and self-evaluating choices at each step.\n\n"
        "## Security Concerns\n"
        "Prompt Injection occurs when adversarial users input text that overrides system instructions, forcing the model to perform unauthorized actions or leak sensitive developer instructions."
    ),
    "HuggingFace.pdf": (
        "Hugging Face Hub and Open-Source Models",
        "## The Hugging Face Ecosystem\n"
        "Hugging Face is the central platform for open-source AI. It hosts models, datasets, and interactive spaces. "
        "The `transformers` library provides APIs to download, load, and run state-of-the-art open models locally.\n\n"
        "## Sentence Transformers and Embeddings\n"
        "Sentence Transformers is a framework to generate high-quality vector representations (embeddings) of sentences, paragraphs, and images. "
        "The model `all-MiniLM-L6-v2` is a lightweight, widely-used transformer model mapping text to 384-dimensional vectors, ideal for local semantic search.\n\n"
        "## Tokenization\n"
        "Tokenizers convert raw text strings into numerical tokens. "
        "Byte-Pair Encoding (BPE) and WordPiece are common tokenization algorithms that segment words to handle out-of-vocabulary terms."
    ),
    "Gemini_API.pdf": (
        "Google Gemini API Developer Guide",
        "## API Introduction\n"
        "The Google Gemini API grants access to Google's highly efficient Gemini model series. "
        "The family is natively multimodal and trained on text, code, audio, image, and video data.\n\n"
        "## Model Offerings\n"
        "- Gemini 2.5 Pro: Flagship model for high-reasoning, complex coding, and multimodal analysis.\n"
        "- Gemini 2.5 Flash: Light, fast, cost-efficient model optimized for low-latency streaming and high volume tasks.\n\n"
        "## Developer Capabilities\n"
        "The Gemini API supports Structured Outputs (forcing JSON schemas), Function Calling (declaring tools that the model can invoke), "
        "and System Instructions to steer the model's persona."
    ),
    "OpenAI_API.pdf": (
        "OpenAI Developer API Documentation",
        "## Core Endpoints\n"
        "OpenAI provides APIs for model inference, text embeddings, image generation (DALL-E), and transcription (Whisper).\n\n"
        "## Chat Completions API\n"
        "The `/v1/chat/completions` endpoint processes conversation history (user, system, and assistant messages) "
        "and returns responses generated by GPT-4o, GPT-4o-mini, or specialized model variants.\n\n"
        "## Assistants API and Vector Search\n"
        "The Assistants API simplifies building agents by natively managing conversational state (Threads) "
        "and integrating file retrieval (File Search) and code execution (Code Interpreter) directly into the API runtime."
    ),
    "AI_Agents.pdf": (
        "Autonomous AI Agent Architectures",
        "## Agent Definition\n"
        "An AI Agent is an autonomous system powered by an LLM that can plan, remember context, and execute actions using external tools.\n\n"
        "## Core Agent Pillars\n"
        "1. Planning: Subgoal decomposition (breaking down complex tasks) and Reflection (refining plans based on environment feedback).\n"
        "2. Memory: Short-term memory (session conversation history) and Long-term memory (reading/writing to vector or relational databases).\n"
        "3. Tools: APIs, search engines, python compilers, and file writers that the model calls to gather info or effect change.\n\n"
        "## Multi-Agent Systems\n"
        "Multi-agent environments divide complex problems into specialized roles. Agents communicate through message buses or structured interfaces, delegating work dynamically."
    ),
    "Vector_Databases.pdf": (
        "Vector Databases and High-Dimensional Indexing",
        "## Purpose of Vector Databases\n"
        "Vector databases store, index, and query high-dimensional embeddings generated by machine learning models. "
        "They enable rapid nearest-neighbor search for semantic comparison.\n\n"
        "## Similarity Metrics\n"
        "Common distance metrics to measure semantic closeness include:\n"
        "- Cosine Similarity: Measures the angle between vectors, ignoring magnitude.\n"
        "- Euclidean Distance (L2): Measures the straight-line distance between points in space.\n"
        "- Dot Product: Measures magnitude and direction alignment.\n\n"
        "## Indexing Algorithms\n"
        "To query millions of vectors in milliseconds, databases use Approximate Nearest Neighbor (ANN) index structures:\n"
        "- FAISS: Facebook AI Similarity Search library, optimized for local dense vector search in RAM.\n"
        "- HNSW: Hierarchical Navigable Small World, creating multi-layer graphs for rapid traversal.\n"
        "- IVF: Inverted File Index, clustering vector spaces to restrict queries to subset partitions."
    ),
    "MCP.pdf": (
        "Model Context Protocol (MCP) Specifications",
        "## Introduction to MCP\n"
        "The Model Context Protocol (MCP) is an open standard designed by Anthropic. "
        "It provides a secure, unified protocol for AI models to access local or remote data sources, environments, and tools.\n\n"
        "## Core Components\n"
        "- MCP Clients: AI applications (like Claude Desktop or IDEs) that connect to MCP servers.\n"
        "- MCP Servers: Lightweight programs that expose specific capabilities, structured under:\n"
        "  1. Resources: Read-only data sources (files, DBs, logs).\n"
        "  2. Tools: Executable functions (terminal run, file edit, API fetch).\n"
        "  3. Prompts: Built-in prompt templates that help clients frame user requests."
    ),
    "RAG.pdf": (
        "Retrieval-Augmented Generation (RAG) Architecture",
        "## Concept of RAG\n"
        "Retrieval-Augmented Generation (RAG) enhances LLMs by retrieving relevant documents from external sources "
        "and injecting them into the LLM context before generation, reducing hallucinations and enabling queries on private data.\n\n"
        "## RAG Life Cycle\n"
        "1. Ingestion: Documents are loaded, parsed, split into smaller chunks, and embedded.\n"
        "2. Indexing: Chunks are stored in a Vector DB index.\n"
        "3. Retrieval: The user query is embedded, and the database returns the top-K similar chunks.\n"
        "4. Generation: Chunks and query are assembled into a prompt. The LLM generates the grounded response.\n\n"
        "## Advanced RAG\n"
        "Advanced strategies include query rewriting, hybrid search (combining dense vector search with BM25 keyword matching), "
        "and reranking (using cross-encoder models to reorder top retrieved documents for better relevance)."
    ),
    "AI_Tools.pdf": (
        "Local and Emerging AI Tool Ecosystem",
        "## Local Execution Tools\n"
        "- Ollama: An open-source tool to run open models (Llama 3, Mistral, Gemma) locally on CPU and GPU with a simple CLI.\n"
        "- LM Studio: A desktop UI application to load and run GGUF format models locally, exposing an OpenAI-compatible API endpoint.\n\n"
        "## MLOps and Evaluation\n"
        "- LangSmith: LangChain's platform to trace, debug, test, and evaluate LLM applications and agent states.\n"
        "- Weights & Biases (W&B): A tool for model tracking, hyperparameter sweeps, and logging training runs."
    )
}

def main():
    knowledge_dir = Path("knowledge_base")
    knowledge_dir.mkdir(exist_ok=True)
    
    print(f"Generating mock PDFs in {knowledge_dir.resolve()}...")
    
    for filename, (title, content) in DOCUMENTS_CONTENT.items():
        filepath = knowledge_dir / filename
        print(f"Generating: {filename}...")
        create_pdf(filepath, title, content)
        
    print("All mock PDFs generated successfully!")

if __name__ == "__main__":
    main()
