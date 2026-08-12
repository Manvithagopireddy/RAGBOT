import os
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import GEMINI_MODEL_NAME, DEFAULT_TEMPERATURE, DEFAULT_MAX_OUTPUT_TOKENS
from src.logger import get_logger

logger = get_logger(__name__)

def get_llm(temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS) -> ChatGoogleGenerativeAI:
    """Initializes and returns a LangChain ChatGoogleGenerativeAI model.
    Reads GOOGLE_API_KEY from environment variables.
    """
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        # Fallback to system environment, or log warning
        logger.warning("GOOGLE_API_KEY not set in .env. Attempting to run with system-wide environment variables.")

    logger.info(f"Initializing Gemini model: {GEMINI_MODEL_NAME} with temperature={temperature}")
    try:
        # Note: ChatGoogleGenerativeAI utilizes the official Google Generative AI SDK
        llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL_NAME,
            temperature=temperature,
            max_output_tokens=max_tokens,
            google_api_key=api_key,
            streaming=True  # Enables real-time streaming of response tokens
        )
        return llm
    except Exception as e:
        logger.error(f"Error initializing ChatGoogleGenerativeAI: {e}")
        raise e
