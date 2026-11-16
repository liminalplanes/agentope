"""IPS, SNIPS, effective sample size and the bootstrap interval.

No weight clipping: clipping trades bias for variance silently. Problems are
reported through diagnostics and the verdict instead.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

_CHUNK_CELLS = 4_000_000  # resample indices held in memory at once


def ips(weights: Sequence[float], rewards: Sequence[float]) -> float:
    return math.fsum(w * r for w, r in zip(weights, rewards, strict=True)) / len(weights)


def snips(weights: Sequence[float], rewards: Sequence[float]) -> float | None:
    """Self-normalized IPS; None when every weight is zero."""
    total = math.fsum(weights)
    if total == 0:
        return None
    return math.fsum(w * r for w, r in zip(weights, rewards, strict=True)) / total


def effective_sample_size(weights: Sequence[float]) -> float:
    sq = math.fsum(w * w for w in weights)
    return 0.0 if sq == 0 else math.fsum(weights) ** 2 / sq


def bootstrap_difference_ci(
    weights: Sequence[float],
    rewards: Sequence[float],
    clusters: Sequence[str],
    n_boot: int,
    seed: int,
    level: float = 0.95,
) -> tuple[tuple[float, float] | None, int]:
    """Percentile interval for SNIPS minus the logging policy's mean outcome.

    Resamples whole clusters (join keys), so decisions that share an outcome are
    resampled together. Decisions with weight 0 still count toward the logging
    mean. Returns (interval, resamples where SNIPS was undefined).
    """
    w = np.asarray(weights, dtype=np.float64)
    r = np.asarray(rewards, dtype=np.float64)
    _, cluster = np.unique(np.asarray(clusters, dtype=object), return_inverse=True)
    g = int(cluster.max()) + 1
    wr = np.bincount(cluster, weights=w * r, minlength=g)
    ws = np.bincount(cluster, weights=w, minlength=g)
    rs = np.bincount(cluster, weights=r, minlength=g)
    ns = np.bincount(cluster, minlength=g).astype(np.float64)

    rng = np.random.default_rng(seed)
    chunk = max(1, _CHUNK_CELLS // g)
    diffs = []
    for start in range(0, n_boot, chunk):
        idx = rng.integers(0, g, size=(min(chunk, n_boot - start), g))
        sw = ws[idx].sum(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            diffs.append(wr[idx].sum(axis=1) / sw - rs[idx].sum(axis=1) / ns[idx].sum(axis=1))
    d = np.concatenate(diffs)
    defined = d[np.isfinite(d)]
    undefined = int(d.size - defined.size)
    if defined.size == 0:
        return None, undefined
    tail = (1 - level) / 2
    lo, hi = np.quantile(defined, [tail, 1 - tail])
    return (float(lo), float(hi)), undefined
