"""Machine learning model factories, training routines, and inference."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor

RANDOM_STATE = 42
MAX_TRAIN_SAMPLES = 200_000


def get_model_instances(
    n_estimators_override: int | None = None, rf_jobs: int = -1
) -> dict[str, Any]:
    """Instantiate the standard evaluation models with fixed random state."""
    rf_trees = n_estimators_override if n_estimators_override is not None else 100
    gb_trees = n_estimators_override if n_estimators_override is not None else 200

    return {
        "LR": LinearRegression(),
        "DT": DecisionTreeRegressor(
            max_depth=8,
            min_samples_leaf=20,
            random_state=RANDOM_STATE,
        ),
        "RF": RandomForestRegressor(
            n_estimators=rf_trees,
            max_depth=12,
            min_samples_leaf=20,
            random_state=RANDOM_STATE,
            n_jobs=rf_jobs,
        ),
        "GB": GradientBoostingRegressor(
            loss="squared_error",
            n_estimators=gb_trees,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=RANDOM_STATE,
        ),
        "GBR_q95": GradientBoostingRegressor(
            loss="quantile",
            alpha=0.95,
            n_estimators=gb_trees,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=RANDOM_STATE,
        ),
    }


def fit_model(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    max_samples: int = MAX_TRAIN_SAMPLES,
) -> Any:
    """Fit a model on training data with seeded subsampling if sample count exceeds cap."""
    n_samples = len(X_train)
    if n_samples == 0:
        raise ValueError("Cannot train model on empty training data.")

    if n_samples > max_samples:
        rng = np.random.default_rng(RANDOM_STATE)
        chosen_indices = rng.choice(n_samples, size=max_samples, replace=False)
        X_fit = X_train[chosen_indices]
        y_fit = y_train[chosen_indices]
    else:
        X_fit = X_train
        y_fit = y_train

    model.fit(X_fit, y_fit)
    return model
