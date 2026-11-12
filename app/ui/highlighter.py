from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from app.core.validator import CustomEnricherRule, TokenKind, extract_protected_tokens

_TOKEN_STYLES: dict[TokenKind, tuple[str, bool, bool]] = {
    "handlebars": ("#7c3aed", True, False),
    "enricher": ("#0f766e", True, False),
    "url": ("#2563eb", False, True),
    "html": ("#b45309", False, False),
    "placeholder": ("#db2777", True, False),
}


def _build_token_formats() -> dict[TokenKind, QTextCharFormat]:
    formats: dict[TokenKind, QTextCharFormat] = {}
    for kind, (color_hex, bold, underline) in _TOKEN_STYLES.items():
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if underline:
            fmt.setFontUnderline(True)
        formats[kind] = fmt
    return formats


class TokenHighlighter(QSyntaxHighlighter):
    """Syntax highlighter coloring Foundry enrichers, handlebars, URLs, HTML tags, and placeholders."""

    def __init__(
        self,
        document: QTextDocument,
        custom_enrichers: list[CustomEnricherRule] | None = None,
    ) -> None:
        super().__init__(document)
        self._custom_enrichers = list(custom_enrichers or [])
        self._formats = _build_token_formats()

    def set_custom_enrichers(self, rules: list[CustomEnricherRule]) -> None:
        """Update custom enricher regex rules and trigger rehighlighting."""
        self._custom_enrichers = list(rules)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        tokens = extract_protected_tokens(text, custom_enrichers=self._custom_enrichers)
        for tok in tokens:
            fmt = self._formats.get(tok.kind)
            if fmt is not None and tok.end > tok.start:
                self.setFormat(tok.start, tok.end - tok.start, fmt)
