"""Level 3: estimate the logging policy from logged (context, chosen) pairs (spec §5.3).

A conditional (multinomial) logit: each action has a weight vector and an
intercept, and probabilities are a softmax over the decision's own candidates.
Actions never chosen anywhere in the logs get probability 0. The model is
cross-fitted, so no decision's propensity comes from a model that saw its own
choice. Folds are formed by join key, so decisions that share an outcome stay
in the same fold. Deterministic for a fixed seed.
"""

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import optimize, sparse

from .decisions import Decision, Scalar

type SparseRow = tuple[tuple[int, float], ...]


def _category(value: Scalar) -> tuple[str, Scalar]:
    return (type(value).__name__, value)


class FeatureEncoder:
    """Turns flat context dicts into sparse numeric rows.

    strings (and mixed types) → one-hot · booleans → 0/1 · numbers → standardized ·
    nulls/missing keys → an indicator feature. Constant features are dropped.
    """

    def __init__(self, contexts: Sequence[Mapping[str, Scalar]]):
        self._plan: list[tuple[str, str, object]] = []
        self.feature_keys: list[str] = []
        n = 0
        for key in sorted({k for c in contexts for k in c}):
            values = [c.get(key) for c in contexts]
            present = [v for v in values if v is not None]
            if not present:
                continue
            start = n
            if all(isinstance(v, bool) for v in present):
                if len(set(present)) > 1:
                    self._plan.append((key, "bool", n))
                    n += 1
            elif all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
                mean = math.fsum(present) / len(present)  # type: ignore[arg-type]
                var = math.fsum((v - mean) ** 2 for v in present) / len(present)  # type: ignore[operator]
                if var > 0:
                    self._plan.append((key, "num", (n, mean, math.sqrt(var))))
                    n += 1
            else:
                cats = sorted({_category(v) for v in present}, key=repr)
                if len(cats) > 1:
                    self._plan.append((key, "cat", {c: n + i for i, c in enumerate(cats)}))
                    n += len(cats)
            if len(present) < len(values):
                self._plan.append((key, "null", n))
                n += 1
            if n > start:
                self.feature_keys.append(key)
        self.n_features = n

    def encode(self, ctx: Mapping[str, Scalar]) -> SparseRow:
        row: list[tuple[int, float]] = []
        for key, kind, info in self._plan:
            v = ctx.get(key)
            if kind == "null":
                if v is None:
                    row.append((info, 1.0))  # type: ignore[arg-type]
            elif v is None:
                continue
            elif kind == "bool":
                if v is True:
                    row.append((info, 1.0))  # type: ignore[arg-type]
            elif kind == "num":
                idx, mean, std = info  # type: ignore[misc]
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    z = (v - mean) / std
                    if z:
                        row.append((idx, z))
            else:
                idx = info.get(_category(v))  # type: ignore[attr-defined]
                if idx is not None:
                    row.append((idx, 1.0))
        return tuple(row)

    def matrix(self, contexts: Sequence[Mapping[str, Scalar]]) -> sparse.csr_array:
        data, cols, indptr = [], [], [0]
        for ctx in contexts:
            for j, v in self.encode(ctx):
                cols.append(j)
                data.append(v)
            indptr.append(len(cols))
        return sparse.csr_array(
            (np.asarray(data, dtype=np.float64), np.asarray(cols, dtype=np.int64), indptr),
            shape=(len(contexts), self.n_features),
        )


class ConditionalLogit:
    """Softmax over each decision's candidates, with an L2 penalty (a N(0, 1/l2) prior
    on every coefficient). Fitted with L-BFGS on the mean penalized log loss."""

    def __init__(self, n_classes: int, l2: float = 1.0):
        self.n_classes = n_classes
        self.l2 = l2
        self.coef: np.ndarray | None = None  # (n_classes, n_features)
        self.intercept: np.ndarray | None = None  # (n_classes,)
        self.converged = False
        self.iterations = 0

    def _scores(self, X: sparse.csr_array, W: np.ndarray, b: np.ndarray) -> np.ndarray:
        if X.shape[1] == 0:
            return np.broadcast_to(b, (X.shape[0], b.size)).copy()
        return np.asarray(X @ W.T) + b

    def fit(self, X: sparse.csr_array, mask: np.ndarray, y: np.ndarray) -> ConditionalLogit:
        n, f = X.shape
        k = self.n_classes
        onehot = np.zeros((n, k))
        onehot[np.arange(n), y] = 1.0
        XT = X.T.tocsr()
        l2 = self.l2

        def objective(theta: np.ndarray) -> tuple[float, np.ndarray]:
            W = theta[: k * f].reshape(k, f)
            b = theta[k * f :]
            S = np.where(mask, self._scores(X, W, b), -np.inf)
            m = S.max(axis=1, keepdims=True)
            E = np.exp(S - m)
            Z = E.sum(axis=1, keepdims=True)
            lse = m[:, 0] + np.log(Z[:, 0])
            loss = lse.sum() - (onehot * np.where(mask, S, 0.0)).sum()
            G = E / Z - onehot
            gW = np.asarray(XT @ G).T if f else np.zeros((k, 0))
            grad = np.concatenate([gW.ravel(), G.sum(axis=0)])
            return (loss + 0.5 * l2 * theta @ theta) / n, (grad + l2 * theta) / n

        result = optimize.minimize(
            objective,
            np.zeros(k * (f + 1)),
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": 2000, "gtol": 1e-8, "ftol": 1e-12},
        )
        self.coef = result.x[: k * f].reshape(k, f)
        self.intercept = result.x[k * f :]
        self.converged = bool(result.success)
        self.iterations = int(result.nit)
        return self

    def predict(self, X: sparse.csr_array, mask: np.ndarray) -> np.ndarray:
        """Probabilities (n, n_classes); 0 outside each row's candidates."""
        assert self.coef is not None and self.intercept is not None
        S = np.where(mask, self._scores(X, self.coef, self.intercept), -np.inf)
        E = np.exp(S - S.max(axis=1, keepdims=True))
        return E / E.sum(axis=1, keepdims=True)


def assign_folds(keys: Sequence[str], folds: int, seed: int) -> list[int]:
    """Fold index per item; items sharing a key share a fold."""
    unique = sorted(set(keys))
    random.Random(seed).shuffle(unique)
    k = max(1, min(folds, len(unique)))
    fold_of_key = {key: i % k for i, key in enumerate(unique)}
    return [fold_of_key[key] for key in keys]


def _calibration_error(p: np.ndarray, y: np.ndarray, bins: int = 10) -> float:
    if p.size == 0:
        return 0.0
    b = np.minimum((p * bins).astype(np.int64), bins - 1)
    gap = np.bincount(b, weights=p, minlength=bins) - np.bincount(b, weights=y, minlength=bins)
    return float(np.abs(gap).sum() / p.size)


@dataclass(frozen=True, slots=True)
class PropensityModelResult:
    distributions: list[dict[str, float]]
    """Held-out logging distribution over each decision's candidates."""
    propensities: list[float]
    folds: int
    feature_keys: list[str]
    n_features: int
    converged: bool
    log_loss: float
    baseline_log_loss: float
    """Log loss of context-free action frequencies, for comparison."""
    calibration_error: float
    """Expected calibration error over (decision, candidate) pairs, 10 bins."""


def fit_logging_policy(
    decisions: Sequence[Decision], folds: int = 5, seed: int = 0, l2: float = 1.0
) -> PropensityModelResult:
    n = len(decisions)
    encoder = FeatureEncoder([d.context for d in decisions])
    classes = sorted({d.chosen for d in decisions})
    index = {a: i for i, a in enumerate(classes)}
    k = len(classes)
    X = encoder.matrix([d.context for d in decisions])
    mask = np.zeros((n, k), dtype=bool)
    for i, d in enumerate(decisions):
        mask[i, [index[a] for a in d.candidates if a in index]] = True
    y = np.fromiter((index[d.chosen] for d in decisions), dtype=np.int64, count=n)
    fold_of = np.asarray(assign_folds([d.join_key for d in decisions], folds, seed))
    n_folds = int(fold_of.max()) + 1

    P = np.zeros((n, k))
    baseline = np.zeros(n)
    converged = True
    for fold in range(n_folds):
        test = np.flatnonzero(fold_of == fold)
        train = np.flatnonzero(fold_of != fold) if n_folds > 1 else test
        model = ConditionalLogit(k, l2).fit(X[train], mask[train], y[train])
        converged = converged and model.converged
        P[test] = model.predict(X[test], mask[test])
        counts = np.bincount(y[train], minlength=k) + 0.5
        base = counts * mask[test]
        baseline[test] = base[np.arange(test.size), y[test]] / base.sum(axis=1)

    propensities = P[np.arange(n), y]
    distributions = []
    for i, d in enumerate(decisions):
        row = P[i]
        distributions.append({a: float(row[index[a]]) if a in index else 0.0 for a in d.candidates})
    onehot = np.zeros((n, k))
    onehot[np.arange(n), y] = 1.0
    with np.errstate(divide="ignore"):
        log_loss = float(-np.log(propensities).mean())
    return PropensityModelResult(
        distributions=distributions,
        propensities=[float(p) for p in propensities],
        folds=n_folds,
        feature_keys=encoder.feature_keys,
        n_features=encoder.n_features,
        converged=converged,
        log_loss=log_loss,
        baseline_log_loss=float(-np.log(baseline).mean()),
        calibration_error=_calibration_error(P[mask], onehot[mask]),
    )
