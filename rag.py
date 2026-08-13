"""
rag_pipeline.py — Full RAG pipeline with model selector, image support, persona injection,
and general-purpose ChatGPT-style answering.
"""
import os
import base64
from typing import Generator, Dict, Any, Tuple, List, Optional
# pyright: ignore [missing-import]
from google import genai
# pyright: ignore [missing-import]
from google.genai import types
from langchain_community.vectorstores import FAISS  # pyright: ignore
from config.prompts import RAG_SYSTEM_PROMPT, CONDENSE_QUESTION_PROMPT
from src.retriever import retrieve_relevant_chunks, format_retrieved_context
from chat_manager import ChatMemory
from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"


def _get_client() -> genai.Client:
    """Returns a google.genai Client.
    Supports both standard API keys (AIza...) and OAuth access tokens (AQ...).
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is not set. Please configure it in your .env file.")

    # OAuth access token (AQ. prefix) — use as Bearer token via Credentials
    if api_key.startswith("AQ."):
        try:
            from google.oauth2.credentials import Credentials
            credentials = Credentials(token=api_key)
            return genai.Client(credentials=credentials)
        except ImportError:
            pass  # fall through to api_key mode

    # Standard REST API key (AIza...)
    return genai.Client(api_key=api_key)



def execute_rag_pipeline(
    db: Optional[FAISS],
    memory: ChatMemory,
    question: str,
    temperature: float = 0.7,
    retriever_k: int = 4,
    model: str = DEFAULT_MODEL,
    persona: str = "",
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg",
    web_search: bool = False,
    web_citations: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Generator[str, None, None], List[Dict[str, Any]], float]:
    """
    Runs the full RAG pipeline for a user question.

    Args:
        db: FAISS vector store (None = pure LLM mode without document retrieval).
        memory: ChatMemory with prior conversation.
        question: The raw user question.
        temperature: LLM temperature (0.0 = factual, 1.0 = creative).
        retriever_k: Number of document chunks to retrieve.
        model: Gemini model name to use.
        persona: Optional custom system persona/instructions.
        image_bytes: Optional image bytes for multimodal queries.
        image_mime: MIME type of the image (e.g. 'image/jpeg', 'image/png').
        web_search: Enable Google Search grounding.
        web_citations: List to populate with web search citations.

    Returns:
        token_generator: Generator yielding streamed response tokens.
        citations: List of source citations from the vector store.
        avg_similarity: Average similarity score of retrieved chunks.
    """
    chat_history_str = memory.format_chat_history(limit=6)
    standalone_query = question

    # 1. Condense query if there's chat history and no image (to resolve pronouns / context references)
    if chat_history_str.strip() and not image_bytes:
        logger.info("Found chat history. Condensing user question for vector retrieval...")
        try:
            client = _get_client()
            condense_prompt = CONDENSE_QUESTION_PROMPT.format(
                chat_history=chat_history_str,
                question=question
            )
            condense_config = types.GenerateContentConfig(temperature=0.0)
            standalone_response = client.models.generate_content(
                model=model,
                contents=condense_prompt,
                config=condense_config,
            )
            standalone_query = standalone_response.text.strip()
            logger.info(f"Rephrased standalone query: '{standalone_query}'")
        except Exception as e:
            logger.error(f"Error condensing query, falling back to original: {e}")
            standalone_query = question

    # 2. Retrieve relevant chunks from vector store
    citations = []
    avg_similarity = 0.0
    context_text = "No document context available."

    if db is not None:
        retrieved_results = retrieve_relevant_chunks(db, standalone_query, k=retriever_k)
        if retrieved_results:
            context_text, citations, avg_similarity = format_retrieved_context(retrieved_results)
            logger.info(f"Retrieved context (avg similarity: {avg_similarity:.4f})")

    # 3. Build system instruction (persona + defaults)
    base_system = persona.strip() if persona.strip() else (
        "You are BotTech AI, a powerful, helpful, and intelligent AI assistant. "
        "Answer any question clearly and thoroughly using Markdown formatting."
    )

    # 4. Build the prompt text
    prompt_text = RAG_SYSTEM_PROMPT.format(
        context=context_text,
        chat_history=chat_history_str if chat_history_str else "No prior history.",
        question=question,
    )

    # 5. Build content list (multimodal if image provided)
    def build_contents():
        if image_bytes:
            # Multimodal: image + text
            return [
                types.Part(
                    inline_data=types.Blob(mime_type=image_mime, data=image_bytes)
                ),
                types.Part(text=prompt_text),
            ]
        else:
            return prompt_text

    # 6. Stream response
    logger.info(f"Calling Gemini ({model}) stream (web_search={web_search})...")

    def token_streamer():
        client = _get_client()
        yielded_any = False
        if web_search:
            try:
                stream_config = types.GenerateContentConfig(
                    temperature=temperature,
                    system_instruction=base_system,
                    max_output_tokens=8192,
                    tools=[{"google_search": {}}],
                )
                for chunk in client.models.generate_content_stream(
                    model=model,
                    contents=build_contents(),
                    config=stream_config,
                ):
                    if chunk.candidates and chunk.candidates[0].grounding_metadata:
                        g_meta = chunk.candidates[0].grounding_metadata
                        if g_meta.grounding_chunks:
                            for gc in g_meta.grounding_chunks:
                                if gc.web:
                                    title = gc.web.title
                                    uri = gc.web.uri
                                    if web_citations is not None:
                                        if not any(wc.get("uri") == uri for wc in web_citations):
                                            web_citations.append({"title": title, "uri": uri})
                    if chunk.text:
                        yielded_any = True
                        yield chunk.text
                return
            except Exception as e:
                logger.warning(f"Web search stream failed: {e}. Falling back to pure LLM.")
                if yielded_any:
                    yield f"\n\n🚨 *Stream interrupted: {str(e)}*"
                    return
                # If we haven't yielded anything yet, we fall through to pure LLM.

        # Pure LLM
        try:
            stream_config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=base_system,
                max_output_tokens=8192,
            )
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=build_contents(),
                config=stream_config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Error streaming response from Gemini: {e}")
            yield f"\n\n🚨 *An error occurred: {str(e)}*"

    return token_streamer(), citations, avg_similarity
