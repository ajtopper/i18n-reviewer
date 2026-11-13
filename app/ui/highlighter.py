from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from app.core.validator import CustomEnricherRule, TokenKind, extract_protected_tokens
from app.ui.theme import LIGHT_TOKENS, ThemeTokens


def _build_token_formats(tokens: ThemeTokens) -> dict[TokenKind, QTextCharFormat]:
    formats: dict[TokenKind, QTextCharFormat] = {}
    for kind_str, (color_hex, bold, underline) in tokens.token_styles.items():
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if underline:
            fmt.setFontUnderline(True)
        kind: TokenKind = kind_str  # type: ignore[assignment]
        formats[kind] = fmt
    return formats


class TokenHighlighter(QSyntaxHighlighter):
    """Syntax highlighter coloring Foundry enrichers, handlebars, URLs, HTML tags, and placeholders."""

    def __init__(
        self,
        document: QTextDocument,
        custom_enrichers: list[CustomEnricherRule] | None = None,
        tokens: ThemeTokens | None = None,
    ) -> None:
        super().__init__(document)
        self._custom_enrichers = list(custom_enrichers or [])
        self._tokens = tokens or LIGHT_TOKENS
        self._formats = _build_token_formats(self._tokens)

    def set_theme(self, tokens: ThemeTokens) -> None:
        """Update syntax token colors from ThemeTokens and rehighlight."""
        self._tokens = tokens
        self._formats = _build_token_formats(tokens)
        self.rehighlight()

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
