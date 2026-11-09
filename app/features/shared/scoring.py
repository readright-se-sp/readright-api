from decimal import Decimal


def comprehension_level(earned: Decimal, possible: Decimal) -> int:
    """Map a comprehension percentage to the configured three score bands."""
    if possible <= 0:
        return 1
    percentage = earned * Decimal("100") / possible
    if percentage >= Decimal("80"):
        return 3
    if percentage >= Decimal("59"):
        return 2
    return 1
