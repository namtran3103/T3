from abc import ABC, abstractmethod

import lightgbm as lgb
import numpy as np

from src.features import FeatureMapper
from src.query_plan import QueryPlan


class Model(ABC):
    tree: lgb.Booster

    @abstractmethod
    def estimate_runtime(self, query: "BenchmarkedQuery") -> float:
        pass

    @abstractmethod
    def estimate_pipeline_runtime(self, query: "BenchmarkedQuery") -> list[float]:
        pass

    @abstractmethod
    def get_feature_mapper(self) -> FeatureMapper:
        pass


class TreeModel(Model):
    """
    Predicts execution time of whole pipeline
    """

    def __init__(self, tree):
        super().__init__()
        self.tree: lgb.Booster = tree
        self._feature_mapper = FeatureMapper()

    def estimate_runtime(self, query: "BenchmarkedQuery") -> float:
        x = query.get_feature_matrix(self._feature_mapper)

        pred = np.sum(self.tree.predict(np.array(x)).flatten())
        pred = float(pred)
        return max(1e-6, pred)

    def estimate_pipeline_runtime(self, query: "BenchmarkedQuery") -> list[float]:
        x = query.get_feature_matrix(self._feature_mapper)
        pred = self.tree.predict(np.array(x)).flatten()
        return [max(1e-6, float(e)) for e in pred]

    def get_feature_mapper(self) -> FeatureMapper:
        return self._feature_mapper


class FlatTreeModel:
    """
    Predicts execution time of whole query
    """

    def __init__(self, tree):
        # super().__init__()
        self.tree: lgb.Booster = tree
        self._feature_mapper = FeatureMapper()

    def estimate_runtime(self, query: "BenchmarkedQuery") -> float:
        x = query.get_feature_matrix(self._feature_mapper)
        x = np.sum(x, axis=0)
        pred = self.tree.predict(np.array([x])).flatten()
        pred = float(pred)
        return max(1e-6, pred)

    def get_feature_mapper(self) -> FeatureMapper:
        return self._feature_mapper


class PerTupleTreeModel(Model):
    """
    Predicts execution time of a single tuple in a pipeline
    """

    def __init__(self, tree, feature_mapper=None):
        super().__init__()
        self.tree: lgb.Booster = tree
        self._feature_mapper = feature_mapper if feature_mapper is not None else FeatureMapper()

    def estimate_runtime(self, query: "BenchmarkedQuery") -> float:
        return sum(self.estimate_pipeline_runtime(query))

    def estimate_pipeline_runtime(
        self,
        query: "BenchmarkedQuery",
    ) -> list[float]:
        x = query.get_feature_matrix(self._feature_mapper)
        from src.pg_features import PgFeatureMapper
        if isinstance(self._feature_mapper, PgFeatureMapper) and query.plan_dict is not None:
            scan_sizes = self._feature_mapper.get_pipeline_scan_sizes(query.plan_dict)
        else:
            scan_sizes = self._feature_mapper.get_pipeline_scan_sizes(query.query_plan)
        pred = self.predict(x, scan_sizes)
        return [max(0.0, float(e)) for e in pred]

    def predict(
        self,
        x,
        scan_sizes,
    ) -> np.ndarray:
        mask = np.any(x != 0, axis=1)
        pred = self.tree.predict(x).flatten()
        pred = np.exp(-pred)
        scan_sizes[scan_sizes < 1] = 1
        pred = pred * scan_sizes
        pred *= mask
        pred[pred < 0] = 0.0
        return pred

    def estimate_many(self, queries: list[QueryPlan]) -> list[float]:
        labels = []
        scan_sizes = []
        pipeline_vectors = []
        for i, q in enumerate(queries):
            current_pipeline_vectors = self._feature_mapper.get_pipeline_estimation_matrix(q)
            current_scan_sizes = self._feature_mapper.get_pipeline_scan_sizes(q)
            pipeline_vectors += [v for v in current_pipeline_vectors]
            scan_sizes += [s for s in current_scan_sizes]
            labels += [i] * len(current_scan_sizes)
        scan_sizes = np.array(scan_sizes)
        pipeline_vectors = np.array(pipeline_vectors)
        labels = np.array(labels)
        pred = self.predict(pipeline_vectors, scan_sizes)
        query_preds = np.bincount(labels, weights=pred)
        return query_preds

    def get_feature_mapper(self) -> FeatureMapper:
        return self._feature_mapper
