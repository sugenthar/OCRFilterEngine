"""Convert calculated installment amounts to the required words format."""

ONES = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine")
TEENS = ("Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")
TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def integer_to_words(value: int) -> str:
    if value < 10:
        return ONES[value]
    if value < 20:
        return TEENS[value - 10]
    if value < 100:
        return TENS[value // 10] + (" " + ONES[value % 10] if value % 10 else "")
    if value < 1000:
        suffix = integer_to_words(value % 100) if value % 100 else ""
        return ONES[value // 100] + " Hundred" + (" " + suffix if suffix else "")
    if value < 1_000_000:
        suffix = integer_to_words(value % 1000) if value % 1000 else ""
        return integer_to_words(value // 1000) + " Thousand" + (" " + suffix if suffix else "")
    raise ValueError("Amount is too large to convert")


def amount_to_words(amount: str | float | int) -> str:
    """Preserve both decimal digits, including a trailing zero."""
    if isinstance(amount, (float, int)):
        amount = f"{amount:.2f}"
    str_amount = str(amount).strip()
    if not str_amount:
        return ""
    if "." not in str_amount:
        str_amount = f"{str_amount}.00"
    whole_str, decimal_str = str_amount.split(".", 1)
    decimal_str = decimal_str.ljust(2, "0")[:2]
    whole_val = int(whole_str) if whole_str.isdigit() else 0
    d1 = int(decimal_str[0]) if decimal_str[0].isdigit() else 0
    d2 = int(decimal_str[1]) if decimal_str[1].isdigit() else 0
    return f"{integer_to_words(whole_val)} Point {ONES[d1]} {ONES[d2]}"
