"""Referans modeller (R0, R1, R2), LightGBM ve Platt kalibrasyonu.

Her model yalnız kendisine verilen eğitim satırlarından, kalibratör yalnız ayrı
kalibrasyon satırlarından öğrenir. Doğrulama, saklı test ve etiket dosyalarını bu
modül bilmez; hangi satırın hangi dilime gireceğine çağıran karar verir.
"""

import platform
from dataclasses import dataclass

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import NotFittedError
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    OneHotEncoder,
    OrdinalEncoder,
    StandardScaler,
)
from sklearn.utils.validation import check_is_fitted

NUMERIC_FIELDS = (
    "log_return_1d",
    "log_return_7d",
    "log_return_14d",
    "log_return_30d",
    "ratio_min_7d",
    "ratio_min_30d",
    "ratio_mean_30d",
    "volatility_30d",
    "change_count_30d",
    "days_since_drop_30d",
    "drop_observed_30d",
    "history_days",
    "missing_ratio_30d",
)
CATEGORICAL_FIELDS = ("weekday", "brand", "family", "segment", "capacity")
COLUMNS = NUMERIC_FIELDS + CATEGORICAL_FIELDS
NUMERIC_INDEXES = list(range(len(NUMERIC_FIELDS)))
CATEGORICAL_INDEXES = list(range(len(NUMERIC_FIELDS), len(COLUMNS)))
R1_COLUMN = COLUMNS.index("ratio_min_30d")

R1_UPPER_EDGES = (1.0, 1.02, 1.05, 1.10)
R1_PRIOR_ROWS = 20
LOG_ODDS_CLIP = 1e-9
LOGISTIC_PARAMS = dict(C=1.0, l1_ratio=0.0, solver="lbfgs", max_iter=1000)
LIGHTGBM_PARAMS = dict(
    objective="binary",
    n_estimators=200,
    learning_rate=0.05,
    num_leaves=15,
    min_child_samples=100,
    reg_lambda=1.0,
    n_jobs=1,
    deterministic=True,
    force_row_wise=True,
    random_state=42,
    verbosity=-1,
)

MODEL_RULES = {
    "version": 1,
    "numeric_features": list(NUMERIC_FIELDS),
    "categorical_features": list(CATEGORICAL_FIELDS),
    "not_used": ["month", "product_key", "product_id", "source"],
    "r0": "training_positive_rate",
    "r1": dict(
        feature="ratio_min_30d",
        upper_edges=list(R1_UPPER_EDGES),
        prior_rows=R1_PRIOR_ROWS,
        rule="(positives + prior_rows * r0) / (rows + prior_rows)",
    ),
    "r2": dict(
        LOGISTIC_PARAMS,
        numeric="median_impute_missing_indicator_standardize",
        categorical="one_hot_unknown_ignored",
    ),
    "lightgbm": dict(
        LIGHTGBM_PARAMS,
        numeric="native_nan",
        categorical="ordinal_codes_unknown_nan",
        class_weight=None,
    ),
    "calibration": dict(
        method="platt_sigmoid",
        score="log_odds_of_frozen_model_probability",
        log_odds_clip=LOG_ODDS_CLIP,
        calibrated_models=["r1", "r2", "lightgbm"],
        fitted_on="separate_calibration_slice",
    ),
}

RAW_NAMES = ("r0", "r1", "r2", "lightgbm")
PLATT_NAMES = ("r1", "r2", "lightgbm")
PREDICTION_NAMES = RAW_NAMES + tuple(f"{name}_platt" for name in PLATT_NAMES)


def design_matrix(rows):
    """FeatureValues satırlarını model girdisine çevirir; NULL sayıda NaN olur."""
    matrix = np.empty((len(rows), len(COLUMNS)), dtype=object)
    for index, row in enumerate(rows):
        for column, name in enumerate(NUMERIC_FIELDS):
            value = getattr(row, name)
            matrix[index, column] = np.nan if value is None else float(value)
        for column, name in zip(CATEGORICAL_INDEXES, CATEGORICAL_FIELDS):
            matrix[index, column] = getattr(row, name)
    return matrix


class PriorRate(ClassifierMixin, BaseEstimator):
    """R0: eğitim dilimindeki olumlu oran; girdiye bakmaz."""

    def fit(self, X, y):
        self.classes_ = np.array([0, 1])
        self.rate_ = float(np.mean(y))
        return self

    def predict_proba(self, X):
        rate = np.full(len(X), self.rate_)
        return np.column_stack([1 - rate, rate])


class BucketRule(ClassifierMixin, BaseEstimator):
    """R1: dibe uzaklık kovalarının eğitimdeki olumlu oranı, R0'a doğru çekilmiş."""

    @staticmethod
    def _buckets(X):
        ratio = np.asarray(X[:, R1_COLUMN], dtype=np.float64)
        if not np.all(np.isfinite(ratio)):
            raise ValueError("R1 girdisi sonlu olmalı")
        # Üst sınır dahildir: tam 1,02 ikinci kovaya girer.
        return np.searchsorted(R1_UPPER_EDGES, ratio, side="left")

    def fit(self, X, y):
        y = np.asarray(y, dtype=np.float64)
        buckets = self._buckets(X)
        size = len(R1_UPPER_EDGES) + 1
        self.classes_ = np.array([0, 1])
        self.prior_rate_ = float(y.mean())
        self.rows_ = np.bincount(buckets, minlength=size)
        self.positives_ = np.bincount(buckets, weights=y, minlength=size)
        self.rates_ = (self.positives_ + R1_PRIOR_ROWS * self.prior_rate_) / (
            self.rows_ + R1_PRIOR_ROWS
        )
        return self

    def predict_proba(self, X):
        rate = self.rates_[self._buckets(X)]
        return np.column_stack([1 - rate, rate])


class LogOdds(ClassifierMixin, BaseEstimator):
    """Eğitilmiş modelin olasılığını log-odds skoruna çevirir.

    Platt kalibrasyonu bu skor üzerinde öğrenilir. Sarmalayıcı olmadan scikit-learn
    yalnız R2'de `decision_function` bulur; LightGBM ve R1 olasılık değerinin
    kendisiyle kalibre edilir ve üç modelin kalibrasyonu birbirine benzemezdi.
    """

    classes_ = np.array([0, 1])

    def __init__(self, model):
        self.model = model

    def fit(self, X, y=None):
        return self

    def __sklearn_is_fitted__(self):
        try:
            check_is_fitted(self.model)
        except NotFittedError:
            return False
        return True

    def predict_proba(self, X):
        return self.model.predict_proba(X)

    def predict(self, X):
        # scikit-learn'ün kalibrasyon altyapısı bu yöntemin varlığını arar.
        return (self.model.predict_proba(X)[:, 1] >= 0.5).astype(np.int64)

    def decision_function(self, X):
        probability = np.clip(
            self.model.predict_proba(X)[:, 1], LOG_ODDS_CLIP, 1 - LOG_ODDS_CLIP
        )
        return np.log(probability / (1 - probability))


def _as_float(values):
    return np.asarray(values, dtype=np.float64)


def build_logistic():
    """R2: ölçeksiz girdiler, eğitimde öğrenilen doldurma/ölçekleme, L2 lojistik."""
    numeric = Pipeline(
        [
            (
                "impute",
                SimpleImputer(
                    strategy="median", add_indicator=True, keep_empty_features=True
                ),
            ),
            ("scale", StandardScaler()),
        ]
    )
    prepare = ColumnTransformer(
        [
            ("numeric", numeric, NUMERIC_INDEXES),
            (
                "category",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_INDEXES,
            ),
        ],
        verbose_feature_names_out=False,
    )
    return Pipeline(
        [("prepare", prepare), ("model", LogisticRegression(**LOGISTIC_PARAMS))]
    )


def build_lightgbm():
    """LightGBM: NULL yerleşik eksik değer olarak kalır; kategoriler kod olur."""
    from lightgbm import LGBMClassifier

    prepare = ColumnTransformer(
        [
            (
                "numeric",
                FunctionTransformer(_as_float, feature_names_out="one-to-one"),
                NUMERIC_INDEXES,
            ),
            (
                "category",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=np.nan
                ),
                CATEGORICAL_INDEXES,
            ),
        ],
        verbose_feature_names_out=False,
    )
    return Pipeline(
        [("prepare", prepare), ("model", LGBMClassifier(**LIGHTGBM_PARAMS))]
    )


@dataclass(frozen=True)
class FoldModels:
    raw: dict
    platt: dict


def _checked(matrix, labels, title):
    if matrix.ndim != 2 or matrix.shape[1] != len(COLUMNS):
        raise ValueError(f"{title} girdisi {len(COLUMNS)} sütunlu olmalı")
    y = np.asarray(labels)
    if y.shape != (len(matrix),) or not np.isin(y, (0, 1)).all():
        raise ValueError(f"{title} etiketleri satır sayısında ve 0/1 olmalı")
    if len(set(y.tolist())) != 2:
        raise ValueError(f"{title} diliminde iki sınıf da olmalı")
    return y.astype(np.int64)


def fit_models(train_x, train_labels, calibration_x, calibration_labels):
    train_y = _checked(train_x, train_labels, "Eğitim")
    calibration_y = _checked(calibration_x, calibration_labels, "Kalibrasyon")
    raw = {
        "r0": PriorRate(),
        "r1": BucketRule(),
        "r2": build_logistic(),
        "lightgbm": build_lightgbm(),
    }
    for model in raw.values():
        model.fit(train_x, train_y)
    platt = {
        name: CalibratedClassifierCV(
            FrozenEstimator(LogOdds(raw[name])), method="sigmoid"
        ).fit(calibration_x, calibration_y)
        for name in PLATT_NAMES
    }
    return FoldModels(raw, platt)


def predict_models(models, x):
    """Ham ve Platt sonrası olasılıklar; her satır ötekilerden bağımsız hesaplanır."""
    result = {name: model.predict_proba(x)[:, 1] for name, model in models.raw.items()}
    for name, model in models.platt.items():
        result[f"{name}_platt"] = model.predict_proba(x)[:, 1]
    return {name: result[name] for name in PREDICTION_NAMES}


def describe_models(models):
    """Katın öğrendiklerini JSON'a yazılabilir sayılara döker."""
    r1, r2, boosted = (models.raw[name] for name in ("r1", "r2", "lightgbm"))
    names = list(COLUMNS)
    logistic = r2.named_steps["model"]
    classifier = boosted.named_steps["model"]
    gains = classifier.booster_.feature_importance(importance_type="gain")
    uppers = [*R1_UPPER_EDGES, None]
    platt = {}
    for name, model in models.platt.items():
        calibrator = model.calibrated_classifiers_[0].calibrators[0]
        # p = 1 / (1 + exp(a·skor + b)); a < 0 ise sıralama korunur.
        platt[name] = dict(
            slope=float(calibrator.a_),
            intercept=float(calibrator.b_),
            order_preserved=bool(calibrator.a_ < 0),
        )
    return dict(
        r0=dict(rate=models.raw["r0"].rate_),
        r1=dict(
            prior_rate=r1.prior_rate_,
            buckets=[
                dict(
                    upper=uppers[index],
                    rows=int(r1.rows_[index]),
                    positives=int(r1.positives_[index]),
                    probability=float(r1.rates_[index]),
                )
                for index in range(len(uppers))
            ],
        ),
        r2=dict(
            intercept=float(logistic.intercept_[0]),
            coefficients={
                name: float(value)
                for name, value in zip(
                    r2[:-1].get_feature_names_out(names), logistic.coef_[0]
                )
            },
            iterations=int(logistic.n_iter_[0]),
            converged=bool(logistic.n_iter_[0] < LOGISTIC_PARAMS["max_iter"]),
        ),
        lightgbm=dict(
            trees=int(classifier.booster_.num_trees()),
            gain_importance={
                name: float(value)
                for name, value in zip(boosted[:-1].get_feature_names_out(names), gains)
            },
        ),
        platt=platt,
    )


def library_versions():
    import lightgbm
    import sklearn

    return dict(
        python=platform.python_version(),
        numpy=np.__version__,
        scikit_learn=sklearn.__version__,
        lightgbm=lightgbm.__version__,
    )
