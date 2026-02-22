from typing import Optional

import numpy as np

from .jh_operator_stages import ExecutionPhase, OperatorStage
from .jh_operators import OperatorType
from .jh_query_plan import QueryPlan
from .jh_util import AutoNumber


class Feature(AutoNumber):
    in_card = ()
    in_size = ()
    out_card = ()
    out_size = ()
    empty_output = ()
    pipeline_scan_card = ()
    pipeline_sink_card = ()
    const = ()
    in_percentage = ()
    right_percentage = ()
    out_percentage = ()
    right_card = ()
    like_count = ()
    like_percentage = ()
    compare_count = ()
    compare_percentage = ()
    in_expression_count = ()
    in_expression_percentage = ()
    between_count = ()
    between_percentage = ()
    or_exp_count = ()
    or_exp_percentage = ()
    starts_with_count = ()
    starts_with_percentage = ()
    join_filter_count = ()
    false_count = ()

    @staticmethod
    def get_global_features():
        return [Feature.pipeline_scan_card, Feature.pipeline_sink_card]


class FeatureDim(AutoNumber):
    scan = ()
    sink = ()
    input = ()
    out = ()
    right = ()
    right_card = ()
    input_card = ()
    expressions = ()
    empty_output = ()


class QualifiedFeature:
    pipeline_time_features = {
        OperatorType.TableScan: {
            OperatorStage.Scan: [
                FeatureDim.scan, FeatureDim.out, FeatureDim.expressions, FeatureDim.empty_output,
            ]
        },
        OperatorType.InlineTable: {OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out]},
        OperatorType.PipelineBreakerScan: {OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out]},
        OperatorType.Temp: {OperatorStage.Build: [FeatureDim.sink, FeatureDim.input]},
        OperatorType.EarlyExecution: {OperatorStage.Scan: [FeatureDim.out]},
        OperatorType.Select: {OperatorStage.PassThrough: [FeatureDim.input, FeatureDim.out]},
        OperatorType.Map: {OperatorStage.PassThrough: [FeatureDim.input, FeatureDim.out]},
        OperatorType.MultiWayJoin: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
        },
        OperatorType.HashJoin: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Probe: [FeatureDim.input_card, FeatureDim.right, FeatureDim.out],
        },
        OperatorType.IndexNLJoin: {
            OperatorStage.Probe: [FeatureDim.input, FeatureDim.right_card, FeatureDim.out],
        },
        OperatorType.GroupJoin: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Probe: [FeatureDim.sink, FeatureDim.right, FeatureDim.out],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
        },
        OperatorType.GroupBy: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Scan: [FeatureDim.sink, FeatureDim.out],
        },
        OperatorType.Sort: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input, FeatureDim.out],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
        },
        OperatorType.SetOperation: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
            OperatorStage.PassThrough: [],
        },
        OperatorType.Window: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
        },
        OperatorType.FileOutput: {OperatorStage.Build: [FeatureDim.sink, FeatureDim.input]},
        OperatorType.CsvWriter: {OperatorStage.Build: [FeatureDim.sink, FeatureDim.input]},
        OperatorType.AssertSingle: {OperatorStage.PassThrough: [FeatureDim.input]},
        OperatorType.EarlyProbe: {OperatorStage.PassThrough: [FeatureDim.out]},
        OperatorType.IdxScan: {
            OperatorStage.Probe: [FeatureDim.out, FeatureDim.expressions, FeatureDim.empty_output],
        },
        OperatorType.NLJoin: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Probe: [FeatureDim.input, FeatureDim.right_card, FeatureDim.out],
        },
        OperatorType.MergeJoin: {
            OperatorStage.Probe: [FeatureDim.input, FeatureDim.right_card, FeatureDim.out],
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
        },
        OperatorType.Aggregate: {
            OperatorStage.Build: [FeatureDim.sink, FeatureDim.input],
            OperatorStage.Scan: [FeatureDim.scan, FeatureDim.out],
        },
    }

    def __init__(
        self,
        operator_type: Optional[OperatorType],
        operator_stage: Optional[OperatorStage],
        feature: Feature,
    ):
        self.operator_type = operator_type
        self.operator_stage = operator_stage
        self.feature = feature

    @staticmethod
    def get_dim_features(dim: FeatureDim):
        if dim == FeatureDim.scan:
            return [Feature.in_card, Feature.in_size]
        if dim == FeatureDim.sink:
            return [Feature.out_card, Feature.out_size]
        if dim == FeatureDim.out:
            return [Feature.out_percentage]
        if dim == FeatureDim.input:
            return [Feature.in_percentage]
        if dim == FeatureDim.right:
            return [Feature.right_percentage]
        if dim == FeatureDim.right_card:
            return [Feature.right_card]
        if dim == FeatureDim.input_card:
            return [Feature.in_card]
        if dim == FeatureDim.expressions:
            return [
                Feature.like_percentage, Feature.compare_percentage,
                Feature.in_expression_percentage, Feature.between_percentage,
                Feature.or_exp_percentage, Feature.starts_with_percentage,
            ]
        if dim == FeatureDim.empty_output:
            return [Feature.empty_output]
        raise AssertionError("unhandled dimension")

    @staticmethod
    def enumerate_features():
        result = []
        for operator_type, stages in QualifiedFeature.pipeline_time_features.items():
            for stage, dims in stages.items():
                result.append(QualifiedFeature(operator_type, stage, Feature.const))
                for dim in dims:
                    for feature in QualifiedFeature.get_dim_features(dim):
                        result.append(QualifiedFeature(operator_type, stage, feature))
        return result

    @staticmethod
    def get_feature_index_lookup():
        return {f: i for i, f in enumerate(QualifiedFeature.enumerate_features())}

    @staticmethod
    def get_feature_lookup():
        result = {}
        for feature in QualifiedFeature.enumerate_features():
            if feature.operator_type not in result:
                result[feature.operator_type] = {}
            if feature.operator_stage not in result[feature.operator_type]:
                result[feature.operator_type][feature.operator_stage] = []
            result[feature.operator_type][feature.operator_stage].append(feature)
        return result

    def get_name(self):
        if self.operator_type is None:
            return f"Global_{self.feature.name}"
        return f"{self.operator_type.name}_{self.operator_stage.name}_{self.feature.name}"

    def __eq__(self, other):
        return (
            other
            and self.operator_type == other.operator_type
            and self.operator_stage == other.operator_stage
            and self.feature == other.feature
        )

    def __hash__(self):
        return hash((self.operator_type, self.operator_stage, self.feature))


class FeatureMapper:
    _lookup = QualifiedFeature.get_feature_lookup()
    _index_lookup = QualifiedFeature.get_feature_index_lookup()
    _features = QualifiedFeature.enumerate_features()
    n_features = len(_features)

    @staticmethod
    def get_features(op: OperatorType, stage: OperatorStage):
        if op not in FeatureMapper._lookup or stage not in FeatureMapper._lookup[op]:
            return []
        return FeatureMapper._lookup[op][stage]

    def get_empty_feature_vector(self) -> np.ndarray:
        return np.zeros(self.n_features, dtype=float)

    def get_estimation_vector(self, phase: ExecutionPhase) -> np.ndarray:
        output_cardinality = phase.get_output_cardinality()
        input_cardinality = phase.get_input_cardinality()
        right_input_cardinality = phase.get_right_input_cardinality()
        output_size = phase.operator.output_tuple_size
        input_size = (
            phase.operator.input_op.output_tuple_size
            if phase.operator.input_op is not None
            else 0
        )
        input_percentage = phase.get_input_percentage()
        output_percentage = phase.get_output_percentage()
        right_percentage = phase.get_right_percentage()

        if phase.operator.type == OperatorType.HashJoin and phase.stage == OperatorStage.Build:
            output_cardinality = input_cardinality
            output_size = input_size
            output_percentage = input_percentage

        expressions = phase.operator.expressions
        features = {
            Feature.out_card: output_cardinality,
            Feature.in_card: input_cardinality,
            Feature.out_size: output_size,
            Feature.in_size: input_size,
            Feature.const: 1,
            Feature.in_percentage: input_percentage,
            Feature.out_percentage: output_percentage,
            Feature.right_percentage: right_percentage,
            Feature.right_card: right_input_cardinality,
            Feature.like_count: expressions.like_count,
            Feature.like_percentage: expressions.like_selectivity,
            Feature.compare_count: expressions.compare_count,
            Feature.compare_percentage: expressions.compare_selectivity,
            Feature.in_expression_count: expressions.in_expression_count,
            Feature.in_expression_percentage: expressions.in_expression_selectivity,
            Feature.between_count: expressions.between_count,
            Feature.between_percentage: expressions.between_selectivity,
            Feature.or_exp_count: expressions.or_expression_count,
            Feature.or_exp_percentage: expressions.or_selectivity,
            Feature.starts_with_count: expressions.starts_with_count,
            Feature.starts_with_percentage: expressions.starts_with_selectivity,
            Feature.join_filter_count: expressions.join_filter_count,
            Feature.false_count: expressions.false_count,
            Feature.empty_output: 1 if output_cardinality == 0 else 0,
        }

        result = self.get_empty_feature_vector()
        for f in self.get_features(phase.operator.type, phase.stage):
            value = features.get(f.feature, 0)
            index = self._index_lookup.get(f)
            if index is not None:
                result[index] = value
        return result

    def get_estimation_matrix(self, query_plan: QueryPlan) -> np.ndarray:
        row_vectors = []
        for pipeline in query_plan.pipelines:
            for op in pipeline.operators:
                row_vectors.append(self.get_estimation_vector(op))
        return np.vstack(row_vectors) if row_vectors else self.get_empty_feature_vector().reshape(1, -1)

    def get_pipeline_estimation_matrix(self, query_plan: QueryPlan) -> np.ndarray:
        result = []
        for pipeline in query_plan.pipelines:
            row_vectors = [self.get_empty_feature_vector()]
            for op in pipeline.operators:
                row_vectors.append(self.get_estimation_vector(op))
            pipeline_vector = np.sum(np.vstack(row_vectors), axis=0)
            result.append(pipeline_vector)
        return np.vstack(result) if result else self.get_empty_feature_vector().reshape(1, -1)

    @staticmethod
    def get_names():
        return [f.get_name() for f in QualifiedFeature.enumerate_features()]

    @staticmethod
    def get_pipeline_scan_sizes(query_plan: QueryPlan) -> np.ndarray:
        return np.array([p.get_pipeline_scan_cardinality() for p in query_plan.pipelines])
