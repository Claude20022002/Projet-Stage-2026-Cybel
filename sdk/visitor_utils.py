import math
from typing import Any


def validate_embedding(embedding: Any) -> bool:
    """Vecteur non vide, valeurs finies (rejette NaN/Inf/None)."""
    if not isinstance(embedding, (list, tuple)) or len(embedding) == 0:
        return False
    for value in embedding:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return False
        if math.isnan(f) or math.isinf(f):
            return False
    return True


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Similarité cosinus dans [-1, 1]. Retourne 0.0 si l'une des normes est nulle."""
    if len(a) != len(b) or not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def dimension_of(candidates: list[tuple[str, list[float]]]) -> int | None:
    """Dimension d'embedding attendue, déduite du premier candidat (None si aucun)."""
    for _, embedding in candidates:
        if embedding:
            return len(embedding)
    return None


def find_best_match(
    embedding: list[float],
    candidates: list[tuple[str, list[float]]],
    threshold: float,
) -> tuple[str | None, float]:
    """Retourne (id, score) du meilleur candidat si score >= threshold, sinon (None, meilleur_score).

    Protège contre un embedding dont la dimension ne correspond pas à celle des
    visiteurs enregistrés (ex. modèle TFLite changé sans ré-enrôlement) : dans ce
    cas retourne (None, 0.0) plutôt que de planter sur un mismatch de forme.
    """
    expected_dim = dimension_of(candidates)
    if expected_dim is not None and len(embedding) != expected_dim:
        return None, 0.0

    best_id: str | None = None
    best_score = 0.0
    for visitor_id, candidate_embedding in candidates:
        if len(candidate_embedding) != len(embedding):
            continue
        score = cosine_similarity(embedding, candidate_embedding)
        if score > best_score:
            best_score = score
            best_id = visitor_id

    if best_id is not None and best_score >= threshold:
        return best_id, best_score
    return None, best_score
