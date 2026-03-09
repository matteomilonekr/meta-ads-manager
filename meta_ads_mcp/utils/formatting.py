"""Output formatting utilities for Meta Ads MCP."""

from __future__ import annotations

from typing import Any


CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CNY": "¥",
    "CHF": "CHF", "CAD": "CA$", "AUD": "A$", "BRL": "R$", "INR": "₹",
}


def currency_symbol(currency: str) -> str:
    """Return the symbol for a currency code, or the code itself."""
    return CURRENCY_SYMBOLS.get(currency, currency + " ")


def format_currency(amount_cents: int | float | str, currency: str = "USD") -> str:
    """Format a cent/micro amount as currency.

    Meta API returns budgets in cents (e.g., 5000 = $50.00).
    """
    try:
        value = float(amount_cents) / 100
    except (ValueError, TypeError):
        return str(amount_cents)
    return f"{currency} {value:,.2f}"


def format_number(value: int | float | str | None) -> str:
    """Format a number with thousand separators."""
    if value is None:
        return "0"
    try:
        num = float(value)
        if num == int(num):
            return f"{int(num):,}"
        return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: float | str | None) -> str:
    """Format a value as percentage."""
    if value is None:
        return "0.00%"
    try:
        return f"{float(value) * 100:.2f}%"
    except (ValueError, TypeError):
        return str(value)


def format_table_markdown(
    rows: list[dict[str, Any]],
    columns: list[str],
    headers: dict[str, str] | None = None,
) -> str:
    """Build a markdown table from a list of dicts.

    Args:
        rows: Data rows.
        columns: Column keys in display order.
        headers: Optional mapping of column key to display header.

    Returns:
        Markdown table string.
    """
    if not rows:
        return "_No data_"

    hdrs = headers or {c: c for c in columns}
    header_row = "| " + " | ".join(hdrs.get(c, c) for c in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    data_rows = []
    for row in rows:
        cells = [str(row.get(c, "")) for c in columns]
        data_rows.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_row, separator, *data_rows])
