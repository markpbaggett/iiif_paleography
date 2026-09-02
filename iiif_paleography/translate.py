"""
Language detection and translation helpers for the iiif-paleography package.

When transcriptions come back in a language other than English, this module
provides the utilities to (1) detect that and (2) translate the text to
English using whichever LLM provider the transcriber is already configured
with.
"""
import re

from langdetect import detect as _detect
from langdetect.lang_detect_exception import LangDetectException

# Regex to strip HTML tags while keeping the visible text content.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags from *text*, returning plain text.

    Structural labels like ``[Header]`` or ``[Margin: foo]`` are preserved
    because they don't look like HTML tags.
    """
    if not text:
        return ""
    return _HTML_TAG_RE.sub(" ", text).strip()


def detect_language(text: str) -> str:
    """Return the ISO-639-1 language code for *text*.

    HTML tags are stripped before detection so that markup-heavy transcriptions
    (which contain ``<p>``, ``<br>``, ``<sup>``, etc.) are analysed on their
    textual content.

    On any failure (empty string, detection error) ``"en"`` is returned so that
    callers default to treating the text as English and simply skip translation.
    """
    cleaned = strip_html(text)
    if not cleaned or len(cleaned) < 3:
        return "en"
    try:
        return _detect(cleaned)
    except LangDetectException:
        return "en"


def translate_with_transcriber(transcriber, text: str) -> str:
    """Translate *text* to English using *transcriber*.

    Delegates to the transcriber's own ``translate_text`` method, which knows
    how to talk to the underlying provider (direct Gemini API, TAMUS AI Chat,
    or TAMUS AI Gateway).  The transcriber is expected to already be
    authenticated and configured with the desired model.

    Args:
        transcriber: A transcriber instance (``GeminiTranscriber``,
            ``TamuChatTranscriber``, or ``TamuGatewayTranscriber``).
        text: The transcription text (may contain HTML markup).

    Returns:
        The translated text, or an empty string if translation could not be
        performed.
    """
    return transcriber.translate_text(text)
