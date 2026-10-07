"""LightGBM-based flight delay predictor.

Binary classification: P(dep_delay_minutes >= 15 min).
Threshold defaults to 0.5 but can be tuned for recall/precision trade-off.
"""

from __future__ import annotations

import logging
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

log = logging.getLogger(__name__)

_LGB_PARAMS: dict = {
    "objective": "binary",
    "metric": ["binary_logloss", "auc"],
    "num_leaves": 63,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "min_child_samples": 20,
    "verbose": -1,
    "seed": 42,
}


class DelayPredictor:
    """LightGBM binary classifier: P(flight delay >= 15 min).

    predict_proba()  — probability of delay (0.0–1.0)
    predict_delayed() — boolean flag at decision_threshold
    """

    def __init__(self, decision_threshold: float = 0.5) -> None:
        self._model: lgb.Booster | None = None
        self.decision_threshold = decision_threshold

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame | None = None,
        y_val: pd.Series | None = None,
        num_boost_round: int = 600,
    ) -> dict[str, float]:
        """Train the classifier. Returns AUC and log-loss on train (and optionally val)."""
        # Compensate for class imbalance: scale weight of positive class
        pos_rate = float(y_train.mean())
        scale_pos_weight = (1.0 - pos_rate) / pos_rate if pos_rate > 0 else 1.0
        params = {**_LGB_PARAMS, "scale_pos_weight": scale_pos_weight}

        train_ds = lgb.Dataset(
            X_train, label=y_train, categorical_feature="auto", free_raw_data=False
        )

        callbacks: list = [lgb.log_evaluation(period=100)]
        valid_sets: list = [train_ds]
        valid_names: list[str] = ["train"]

        if X_val is not None and y_val is not None:
            val_ds = lgb.Dataset(X_val, label=y_val, reference=train_ds)
            valid_sets.append(val_ds)
            valid_names.append("val")
            callbacks.append(lgb.early_stopping(stopping_rounds=50, verbose=False))

        self._model = lgb.train(
            params,
            train_ds,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )

        train_proba = self.predict_proba(X_train)
        metrics: dict[str, float] = {
            "train_auc": float(roc_auc_score(y_train, train_proba)),
        }
        if X_val is not None and y_val is not None:
            val_proba = self.predict_proba(X_val)
            metrics["val_auc"] = float(roc_auc_score(y_val, val_proba))
        return metrics

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return P(delay >= 15 min) for each flight."""
        if self._model is None:
            raise RuntimeError("Model not trained — call fit() or load() first.")
        return self._model.predict(X)

    def predict_delayed(self, X: pd.DataFrame) -> np.ndarray:
        """Return bool array using decision_threshold."""
        return self.predict_proba(X) >= self.decision_threshold

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
        """Binary classification metrics on held-out data."""
        proba = self.predict_proba(X)
        pred = (proba >= self.decision_threshold).astype(int)
        y_np = y.to_numpy()

        return {
            "roc_auc": float(roc_auc_score(y_np, proba)),
            "avg_precision": float(average_precision_score(y_np, proba)),
            "precision": float(precision_score(y_np, pred, zero_division=0)),
            "recall": float(recall_score(y_np, pred, zero_division=0)),
            "f1": float(f1_score(y_np, pred, zero_division=0)),
            "delay_rate_actual": float(y_np.mean()),
            "delay_rate_predicted": float(pred.mean()),
        }

    def tune_threshold(
        self,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        metric: str = "f1",
    ) -> float:
        """Find the decision threshold that maximises F1 (or recall/precision) on X_val.

        Sets self.decision_threshold and returns the chosen value.
        """
        proba = self.predict_proba(X_val)
        y_np = y_val.to_numpy()

        best_score, best_t = 0.0, self.decision_threshold
        for t in np.arange(0.05, 0.80, 0.01):
            pred = (proba >= t).astype(int)
            if metric == "f1":
                score = float(f1_score(y_np, pred, zero_division=0))
            elif metric == "recall":
                score = float(recall_score(y_np, pred, zero_division=0))
            else:
                score = float(precision_score(y_np, pred, zero_division=0))
            if score > best_score:
                best_score, best_t = score, t

        self.decision_threshold = float(best_t)
        return self.decision_threshold

    def feature_importance(self, top_n: int = 15) -> pd.DataFrame:
        if self._model is None:
            raise RuntimeError("Model not trained.")
        return (
            pd.DataFrame(
                {
                    "feature": self._model.feature_name(),
                    "importance_gain": self._model.feature_importance("gain"),
                    "importance_split": self._model.feature_importance("split"),
                }
            )
            .sort_values("importance_gain", ascending=False)
            .head(top_n)
            .reset_index(drop=True)
        )

    def save(self, path: Path) -> None:
        if self._model is None:
            raise RuntimeError("No model to save.")
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._model.save_model(str(p))
        log.info("Saved model -> %s", p)

    @classmethod
    def load(cls, path: Path) -> DelayPredictor:
        predictor = cls()
        predictor._model = lgb.Booster(model_file=str(path))
        return predictor
