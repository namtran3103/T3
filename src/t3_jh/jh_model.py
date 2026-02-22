import numpy as np
import lightgbm as lgb

from .jh_benchmarked_query import BenchmarkedQuery
from .jh_features import FeatureMapper
from .jh_query_plan import QueryPlan


class PerTupleTreeModel:
    """Predicts execution time per tuple in pipeline (Johannes-style)."""

    def __init__(self, tree: lgb.Booster):
        self.tree = tree
        self._feature_mapper = FeatureMapper()

    def estimate_runtime(self, query: BenchmarkedQuery) -> float:
        return sum(self.estimate_pipeline_runtime(query))

    def estimate_pipeline_runtime(self, query: BenchmarkedQuery) -> list:
        x = query.get_feature_matrix(self._feature_mapper)
        scan_sizes = self._feature_mapper.get_pipeline_scan_sizes(query.query_plan)
        pred = self.predict(x, scan_sizes)
        return [max(0.0, float(e)) for e in pred]

    def predict(self, x: np.ndarray, scan_sizes: np.ndarray) -> np.ndarray:
        mask = np.any(x != 0, axis=1)
        pred = self.tree.predict(x).flatten()
        pred = np.exp(-pred)
        scan_sizes = np.maximum(scan_sizes, 1)
        pred = pred * scan_sizes
        pred *= mask
        pred = np.maximum(pred, 0.0)
        return pred

    def get_feature_mapper(self) -> FeatureMapper:
        return self._feature_mapper
