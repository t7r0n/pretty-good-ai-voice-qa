from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Iterable


@lru_cache(maxsize=2)
def _model(model_name: str):
    from fastembed import TextEmbedding

    return TextEmbedding(model_name=model_name)


def embed_texts(texts: Iterable[str], model_name: str) -> list[list[float]]:
    text_list = list(texts)
    if model_name == "local-hash-v1":
        return [_hash_embedding(text, dimensions=384) for text in text_list]
    model = _model(model_name)
    return [list(vector) for vector in model.embed(text_list)]


TOKEN_RE = re.compile(r"[a-zA-Z0-9_./:-]{2,}")


def _hash_embedding(text: str, dimensions: int) -> list[float]:
    vector = [0.0] * dimensions
    lowered = text.lower()
    tokens = TOKEN_RE.findall(lowered)
    features: list[str] = []
    features.extend(tokens)
    features.extend(f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False))
    compact = re.sub(r"\s+", " ", lowered)
    features.extend(compact[idx : idx + 4] for idx in range(max(0, len(compact) - 3)))
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + min(len(feature), 32) / 64.0
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
