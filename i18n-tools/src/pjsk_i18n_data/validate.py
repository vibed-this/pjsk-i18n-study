from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_wordings_map(wordings: dict[str, str]) -> ValidationReport:
    report = ValidationReport()

    if not wordings:
        report.errors.append("wordings map is empty")
        return report

    for key, value in wordings.items():
        if not key.strip():
            report.errors.append("empty wordingKey")
            continue
        if value is None or not str(value).strip():
            report.warnings.append(f"empty zh value: {key}")

    # spot-check known Frida samples
    for sample in ("WORD_DECIDE", "WORD_CANCEL", "MSG_LIVE_SKIP_BODY"):
        if sample not in wordings:
            report.warnings.append(f"known sample key missing: {sample}")

    return report


def validate_placeholders_preserved(
    jp_map: dict[str, str],
    zh_map: dict[str, str],
) -> ValidationReport:
    """Warn when CN/JP placeholder tokens diverge on shared keys."""
    report = ValidationReport()
    token_re = re.compile(r"(%[sd]|%\d+\$[sd]|\{[0-9]+\})")

    for key in sorted(set(jp_map) & set(zh_map)):
        jp_tokens = token_re.findall(jp_map[key])
        zh_tokens = token_re.findall(zh_map[key])
        if jp_tokens != zh_tokens:
            report.warnings.append(
                f"placeholder mismatch {key}: jp={jp_tokens} zh={zh_tokens}"
            )
    return report