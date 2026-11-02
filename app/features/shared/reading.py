import re
from typing import Any


_WORDS = re.compile(r"[^\W_]+(?:[’'-][^\W_]+)*", re.UNICODE)
_SENTENCE_END = re.compile(r"[.!?][\"'’”’)]*(?=\s|$)")
_MISCUE_TYPES = {
    "mispronunciation",
    "substitution",
    "omission",
    "insertion",
    "repetition",
    "refusal_to_pronounce",
}


def build_miscue_details(
    events: list[dict[str, Any]],
    passage_text: str,
    passage_tokens: list[dict[str, Any]],
) -> dict[str, list[dict[str, str | None]]]:
    """Build the shared result/dashboard miscue shape with passage context."""
    token_positions = {
        str(token["token_id"]): int(token["position"])
        for token in passage_tokens
        if token.get("token_id") is not None and token.get("position") is not None
    }
    tokens_by_position = {
        int(token["position"]): str(token["token_text"])
        for token in passage_tokens
        if token.get("position") is not None and token.get("token_text") is not None
    }
    character_spans = _token_character_spans(passage_text, passage_tokens)

    details: dict[str, list[dict[str, str | None]]] = {}
    for event in events:
        event_type = event.get("reviewed_type") or event.get("detected_type")
        if not isinstance(event_type, str) or event_type not in _MISCUE_TYPES:
            continue

        start = token_positions.get(str(event.get("expected_start_token_id")))
        end = token_positions.get(str(event.get("expected_end_token_id")))
        expected = ""
        if start is not None and end is not None and end >= start:
            expected = " ".join(
                tokens_by_position[position]
                for position in range(start, end + 1)
                if position in tokens_by_position
            )
        if not expected:
            actual_phrase = event.get("actual_phrase")
            if isinstance(actual_phrase, str):
                expected = actual_phrase

        span = character_spans.get(start) if start is not None else None
        if span is None:
            span = _find_phrase_span(passage_text, expected)
        sentence = _sentence_for_span(passage_text, span) if span else None
        details.setdefault(event_type, []).append(
            {
                "said": event.get("heard_text"),
                "expected": expected,
                "sentence": sentence,
            }
        )
    return details


def _token_character_spans(
    passage_text: str, passage_tokens: list[dict[str, Any]]
) -> dict[int, tuple[int, int]]:
    text_words = list(_WORDS.finditer(passage_text))
    spans: dict[int, tuple[int, int]] = {}
    cursor = 0
    tokens = sorted(
        passage_tokens,
        key=lambda token: int(token.get("position", 0)),
    )
    for token in tokens:
        try:
            position = int(token["position"])
        except (KeyError, TypeError, ValueError):
            continue
        token_words = [
            word.casefold()
            for word in _WORDS.findall(str(token.get("token_text", "")))
        ]
        if not token_words:
            continue
        first_index: int | None = None
        last_index: int | None = None
        search_from = cursor
        matched_count = 0
        for token_word in token_words:
            match_index = next(
                (
                    index
                    for index in range(search_from, len(text_words))
                    if text_words[index].group(0).casefold() == token_word
                ),
                None,
            )
            if match_index is None:
                break
            first_index = match_index if first_index is None else first_index
            last_index = match_index
            search_from = match_index + 1
            matched_count += 1
        if (
            first_index is None
            or last_index is None
            or matched_count != len(token_words)
        ):
            continue
        spans[position] = (text_words[first_index].start(), text_words[last_index].end())
        cursor = last_index + 1
    return spans


def _find_phrase_span(text: str, phrase: str) -> tuple[int, int] | None:
    words = _WORDS.findall(phrase)
    if not words:
        return None
    pattern = r"(?<!\w)" + r"\W+".join(re.escape(word) for word in words) + r"(?!\w)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.UNICODE)
    return (match.start(), match.end()) if match else None


def _sentence_for_span(text: str, span: tuple[int, int]) -> str | None:
    start, end = span
    endings = list(_SENTENCE_END.finditer(text))
    sentence_start = max(
        (ending.end() for ending in endings if ending.end() <= start), default=0
    )
    sentence_end = next(
        (ending.end() for ending in endings if ending.start() >= end), len(text)
    )
    sentence = text[sentence_start:sentence_end].strip()
    return sentence or None
