from __future__ import annotations


def normalize_literal_escapes(text: str) -> str:
    """Convert literal \\n / \\t / \\r sequences to control characters.

    CN sekai-master-db-cn-diff wordings occasionally store escaped newlines
    as the two characters backslash + n instead of U+000A.
    """
    if "\\" not in text:
        return text
    return (
        text.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\r")
        .replace("\\t", "\t")
    )