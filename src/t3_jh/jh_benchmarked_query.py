from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from .jh_features import FeatureMapper
from .jh_operators import OperatorType
from .jh_query_plan import QueryPlan


@dataclass
class BenchmarkedQuery:
    query_plan: QueryPlan
    total_runtimes: list  # in seconds
    name: str
    query_text: str
    query_category: Optional[str]
    feature_matrix: Optional[np.ndarray] = None
    pipeline_runtimes: Optional[list] = None
    source_path: Optional[str] = None  # full path to JSON file (for debug/zeroshot matching)
    plan_index: Optional[int] = None  # index of plan in file (for debug/zeroshot matching)

    def get_total_runtime(self) -> float:
        return float(np.median(self.total_runtimes))

    def get_analyze_plan_runtime(self) -> float:
        all_times = [x for p in self.query_plan.pipelines for x in (p.start, p.stop)]
        if not all_times:
            return 1e-6
        start, stop = min(all_times), max(all_times)
        if start >= stop:
            return 1e-6
        return (stop - start) / 1000.0  # start/stop in ms -> seconds

    def check_pipeline_overlap(self):
        pipelines = sorted(self.query_plan.pipelines, key=lambda p: (p.start, p.stop))
        for i, p in enumerate(pipelines[:-1]):
            p2 = pipelines[i + 1]
            if p.stop <= p2.start:
                continue
            ids1 = {o.operator.op_id for o in p.operators}
            ids2 = {o.operator.op_id for o in p2.operators}
            common = ids1 & ids2
            if not common:
                continue
            common_ops = [o for o in p.operators if o.operator.op_id in common]
            if len(common_ops) == 1 and common_ops[0].operator.type == OperatorType.SetOperation:
                p.stop = p2.start
                p2.stop = max(p.stop, p2.stop)
            else:
                pass  # allow overlap in parsed plans

    def get_pipeline_runtimes(self, verbose: bool = False) -> list:
        if self.pipeline_runtimes is not None:
            return self.pipeline_runtimes
        total_time = self.get_total_runtime()
        analyze_plan_runtime = self.get_analyze_plan_runtime()
        self.check_pipeline_overlap()
        result = []
        for p in self.query_plan.pipelines:
            result.append((p.stop - p.start) / 1000.0 / max(1e-9, analyze_plan_runtime) * total_time)
        pipeline_times_sum = sum(result)
        if pipeline_times_sum == 0:
            result = [total_time / max(1, len(result))] * len(result)
        else:
            correction_factor = total_time / pipeline_times_sum
            result = [x * correction_factor for x in result]
        self.pipeline_runtimes = result
        return self.pipeline_runtimes

    def get_per_tuple_pipeline_runtimes(self) -> list:
        result = []
        for pipeline, runtime in zip(
            self.query_plan.pipelines, self.get_pipeline_runtimes()
        ):
            card = pipeline.get_pipeline_scan_cardinality()
            result.append(runtime if card == 0 else runtime / card)
        return result

    def get_pipeline_runtime_data(
        self, feature_mapper: FeatureMapper
    ) -> list[Tuple[np.ndarray, float]]:
        features = feature_mapper.get_pipeline_estimation_matrix(self.query_plan)
        targets = self.get_pipeline_runtimes()
        return list(zip(features, targets))

    def get_per_tuple_pipeline_runtime_data(
        self, feature_mapper: FeatureMapper
    ) -> list[Tuple[np.ndarray, float]]:
        features = self.get_feature_matrix(feature_mapper)
        targets = self.get_per_tuple_pipeline_runtimes()
        return list(zip(features, targets))

    def get_feature_matrix(self, feature_mapper: FeatureMapper) -> np.ndarray:
        if self.feature_matrix is None:
            self.feature_matrix = feature_mapper.get_pipeline_estimation_matrix(
                self.query_plan
            )
        return self.feature_matrix
