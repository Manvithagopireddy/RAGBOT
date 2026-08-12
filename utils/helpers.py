import re
import json
import os
from typing import List, Dict, Tuple, Any, Optional
from src.logger import get_logger

logger = get_logger(__name__)


def parse_related_questions(response_text: str) -> Tuple[str, List[str]]:
    """Extracts and parses related questions from the assistant's response.
    Returns:
        cleaned_response: Response text without the `<related>` block.
        questions: List of extracted related questions.
    """
    pattern = r"<related>(.*?)</related>"
    match = re.search(pattern, response_text, re.DOTALL)

    questions = []
    cleaned_response = response_text

    if match:
        block = match.group(1).strip()
        cleaned_response = re.sub(pattern, "", response_text, flags=re.DOTALL).strip()

        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("-") or line.startswith("*") or line.startswith("•"):
                q = line[1:].strip()
                if q:
                    questions.append(q)
            else:
                questions.append(line)

    if not questions:
        questions = []

    return cleaned_response, questions[:3]


def calculate_confidence_score(avg_similarity: float) -> Tuple[int, str]:
    """Calculates a percentage confidence score based on the retrieval similarity score.
    Returns a tuple of (percentage, description).
    """
    if avg_similarity == 0.0:
        return 0, "No context matches. Answering using general knowledge."

    percentage = int(avg_similarity * 100)

    if percentage >= 85:
        desc = "High Confidence (Strong local document matches)"
    elif percentage >= 65:
        desc = "Medium-High Confidence (Moderate document matches)"
    elif percentage >= 45:
        desc = "Medium Confidence (Weak matches or partial details)"
    else:
        desc = "Low Confidence (Answering mainly from general training data)"

    return percentage, desc


def format_chat_export_markdown(messages: List[Dict[str, str]]) -> str:
    """Formats chat history as a clean markdown file for download."""
    md = "# AI Tech Assistant — Conversation Log\n\n"
    for msg in messages:
        role_label = "**User** 👤" if msg["role"] == "user" else "**Assistant** 🤖"
        md += f"### {role_label}\n{msg['content']}\n\n---\n\n"
    return md


def format_chat_export_json(messages: List[Dict[str, str]]) -> str:
    """Formats chat history as formatted JSON for download."""
    return json.dumps(messages, indent=2)


def generate_chat_title(first_message: str) -> str:
    """Generates an instant short, descriptive chat title from the user's first message."""
    return _fallback_title(first_message)


def _fallback_title(message: str) -> str:
    """Generates a fallback title by truncating the first message."""
    words = message.strip().split()
    short = " ".join(words[:6])
    return short if len(short) <= 50 else short[:47] + "..."


