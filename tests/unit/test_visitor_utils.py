"""Tests matching embeddings visiteurs (reconnaissance faciale, Phase 2 face-presence)."""

import math

from sdk.visitor_utils import (
    cosine_similarity,
    dimension_of,
    find_best_match,
    validate_embedding,
)


def test_cosine_similarity_identical_vectors() -> None:
    assert cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == 1.0


def test_cosine_similarity_orthogonal_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_opposite_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0


def test_cosine_similarity_zero_norm_returns_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_similarity_mismatched_length_returns_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_validate_embedding_accepts_finite_values() -> None:
    assert validate_embedding([0.1, -0.2, 0.3]) is True


def test_validate_embedding_rejects_empty() -> None:
    assert validate_embedding([]) is False
    assert validate_embedding(None) is False


def test_validate_embedding_rejects_nan_and_inf() -> None:
    assert validate_embedding([0.1, math.nan]) is False
    assert validate_embedding([0.1, math.inf]) is False
    assert validate_embedding([0.1, -math.inf]) is False


def test_validate_embedding_rejects_non_numeric() -> None:
    assert validate_embedding([0.1, "oops"]) is False


def test_dimension_of_returns_first_nonempty() -> None:
    candidates = [("a", []), ("b", [1.0, 2.0, 3.0])]
    assert dimension_of(candidates) == 3


def test_dimension_of_returns_none_when_no_candidates() -> None:
    assert dimension_of([]) is None


def test_find_best_match_above_threshold() -> None:
    candidates = [
        ("alice", [1.0, 0.0, 0.0]),
        ("bob", [0.0, 1.0, 0.0]),
    ]
    visitor_id, score = find_best_match([1.0, 0.0, 0.0], candidates, threshold=0.8)
    assert visitor_id == "alice"
    assert score == 1.0


def test_find_best_match_below_threshold_returns_none() -> None:
    candidates = [("alice", [1.0, 0.0, 0.0])]
    visitor_id, score = find_best_match([0.0, 1.0, 0.0], candidates, threshold=0.8)
    assert visitor_id is None
    assert score == 0.0


def test_find_best_match_dimension_mismatch_returns_none() -> None:
    candidates = [("alice", [1.0, 0.0, 0.0])]
    visitor_id, score = find_best_match([1.0, 0.0], candidates, threshold=0.8)
    assert visitor_id is None
    assert score == 0.0


def test_find_best_match_no_candidates_returns_none() -> None:
    visitor_id, score = find_best_match([1.0, 0.0], [], threshold=0.8)
    assert visitor_id is None
    assert score == 0.0
