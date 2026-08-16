"""Multi-pass OCR consensus analysis."""

from typing import List, Tuple
from ocr.tokens import OCRToken


def merge_ocr_pass_tokens(pass_tokens_list: List[List[OCRToken]]) -> List[OCRToken]:
    """Select the highest-confidence token set or combine non-conflicting tokens."""
    if not pass_tokens_list:
        return []
    if len(pass_tokens_list) == 1:
        return pass_tokens_list[0]

    # Calculate mean confidence for each pass
    pass_scores: List[Tuple[float, int, List[OCRToken]]] = []
    for idx, tokens in enumerate(pass_tokens_list):
        if not tokens:
            pass_scores.append((0.0, 0, []))
            continue
        avg_conf = sum(t.confidence for t in tokens) / len(tokens)
        pass_scores.append((avg_conf, len(tokens), tokens))

    # Sort passes by best score (average confidence + token count weight)
    pass_scores.sort(key=lambda item: (item[0] * min(item[1], 100)), reverse=True)
    return pass_scores[0][2]
