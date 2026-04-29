from pathlib import Path
import anthropic
import instructor
from models.schema import DocumentExtraction

_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_MODEL = "claude-sonnet-4-6"

# Lazy-loaded to avoid import-time side effects in tests
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = instructor.from_anthropic(anthropic.Anthropic())
    return _client


def extract(text: str, strict: bool = False) -> DocumentExtraction:
    """Call Claude via instructor and return a guaranteed-schema DocumentExtraction."""
    prompt_file = "extract_strict.md" if strict else "extract.md"
    system_prompt = (_PROMPT_DIR / prompt_file).read_text()

    return _get_client().messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Document:\n\n{text}"}],
        response_model=DocumentExtraction,
    )
