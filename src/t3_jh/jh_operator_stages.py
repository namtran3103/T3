from dataclasses import dataclass
from typing import Optional

from .jh_operators import Operator, OperatorType
from .jh_util import AutoNumber


class OperatorStage(AutoNumber):
    Scan = ()
    Build = ()
    Probe = ()
    PassThrough = ()


@dataclass
class ExecutionPhase:
    operator: Operator
    stage: OperatorStage
    pipeline: "Pipeline"
    fraction: float = 1.0

    def __str__(self):
        return f"{self.operator.type.name}:{self.stage.name}"

    def copy(self) -> "ExecutionPhase":
        return ExecutionPhase(self.operator, self.stage, self.pipeline, self.fraction)

    def _get_pipeline_scan_cardinality(self) -> float:
        return self.pipeline.get_pipeline_scan_cardinality()

    def get_input_percentage(self) -> float:
        if self._get_pipeline_scan_cardinality() == 0:
            return 0
        return (
            self.operator.input_cardinality
            * self.fraction
            / self._get_pipeline_scan_cardinality()
        )

    def get_output_percentage(self) -> float:
        if self._get_pipeline_scan_cardinality() == 0:
            return 0
        return (
            self.operator.output_cardinality
            * self.fraction
            / self._get_pipeline_scan_cardinality()
        )

    def get_right_percentage(self) -> Optional[float]:
        if self.operator.right_input_cardinality is None:
            return None
        if self._get_pipeline_scan_cardinality() == 0:
            return 0
        return (
            self.operator.right_input_cardinality
            * self.fraction
            / self._get_pipeline_scan_cardinality()
        )

    def get_input_cardinality(self) -> float:
        if self.stage == OperatorStage.Probe:
            return self.operator.input_cardinality
        return self.operator.input_cardinality * self.fraction

    def get_output_cardinality(self) -> float:
        if self.pipeline.operators[-1] == self:
            return self.operator.output_cardinality
        return self.operator.output_cardinality * self.fraction

    def get_right_input_cardinality(self) -> float:
        r = self.operator.right_input_cardinality
        if r is None:
            return 0
        if self.stage == OperatorStage.Probe:
            return r * self.fraction
        return r


@dataclass
class Pipeline:
    operators: list
    operator_mapping: dict
    start: float
    stop: float

    def __init__(self, execution_phases: list, start: float, stop: float):
        self.operators = execution_phases
        self.operator_mapping = {e.operator.op_id: e for e in self.operators}
        self.start = start
        self.stop = stop

    def get_execution_phase(self, op_id: int) -> ExecutionPhase:
        for op in self.operators:
            if op.operator.op_id == op_id:
                return op
        return None

    def get_pipeline_scan_cardinality(self) -> float:
        if len(self.operators) == 0:
            return 0
        first = self.operators[0].operator
        if first.type in (
            OperatorType.GroupBy,
            OperatorType.Sort,
            OperatorType.Temp,
        ):
            return first.output_cardinality
        return first.input_cardinality

    def get_pipeline_sink_cardinality(self) -> float:
        if self.operators[-1].operator.type == OperatorType.GroupBy:
            return self.operators[-1].operator.input_cardinality
        return self.operators[-1].operator.output_cardinality


def get_operator_stage(op_index: int, op: Operator, pipeline_ops: list) -> OperatorStage:
    if op.type in (
        OperatorType.TableScan,
        OperatorType.EarlyExecution,
        OperatorType.PipelineBreakerScan,
        OperatorType.InlineTable,
    ):
        return OperatorStage.Scan
    elif op.type in (
        OperatorType.Map,
        OperatorType.Select,
        OperatorType.AssertSingle,
        OperatorType.EarlyProbe,
    ):
        return OperatorStage.PassThrough
    elif op.type in (OperatorType.CsvWriter, OperatorType.FileOutput, OperatorType.Temp):
        return OperatorStage.Build
    elif op.type in (
        OperatorType.GroupBy,
        OperatorType.Sort,
        OperatorType.Window,
        OperatorType.Aggregate,
    ):
        if op_index == 0 and len(pipeline_ops) == 1:
            return OperatorStage.Scan
        elif op_index == len(pipeline_ops) - 1:
            return OperatorStage.Build
        elif op_index == 0:
            return OperatorStage.Scan
        raise AssertionError(f"{op.type.name} should be at begin or end of pipeline")
    elif op.type == OperatorType.HashJoin:
        assert op_index > 0
        input_op = pipeline_ops[op_index - 1]
        if input_op.json == op.json["right"] or input_op.json == op.json["left"]:
            if op_index != len(pipeline_ops) - 1 or input_op.json == op.json["right"]:
                return OperatorStage.Probe
            return OperatorStage.Build
        return OperatorStage.Probe
    elif op.type == OperatorType.IndexNLJoin:
        assert op_index > 0
        input_op = pipeline_ops[op_index - 1]
        if input_op.json == op.json["left"]:
            return OperatorStage.Probe
        return OperatorStage.Build
    elif op.type == OperatorType.SetOperation:
        if op_index == 0:
            return OperatorStage.Scan
        return OperatorStage.Build
    elif op.type == OperatorType.MultiWayJoin:
        if op_index == 0:
            return OperatorStage.Scan
        return OperatorStage.Build
    elif op.type == OperatorType.GroupJoin:
        if op_index == 0:
            return OperatorStage.Scan
        input_op = pipeline_ops[op_index - 1]
        return OperatorStage.Probe if input_op.json == op.json["right"] else OperatorStage.Build
    elif op.type == OperatorType.NLJoin:
        input_op = pipeline_ops[op_index - 1]
        return OperatorStage.Probe if input_op.json == op.json["right"] else OperatorStage.Build
    elif op.type == OperatorType.MergeJoin:
        return OperatorStage.Probe if op_index == 0 else OperatorStage.Build
    elif op.type == OperatorType.IdxScan:
        return OperatorStage.Probe
    raise AssertionError(f"unhandled operator: {op.type.name}")


def build_execution_phase(
    op_index: int, op: Operator, pipeline_ops: list, pipeline: Pipeline
) -> ExecutionPhase:
    stage = get_operator_stage(op_index, op, pipeline_ops)
    return ExecutionPhase(op, stage, pipeline)


def build_pipeline(pipeline_ops: list, start: float, stop: float) -> Pipeline:
    pipeline = Pipeline([], start, stop)
    execution_phases = [
        build_execution_phase(i, op, pipeline_ops, pipeline)
        for i, op in enumerate(pipeline_ops)
    ]
    pipeline.operators = execution_phases
    pipeline.operator_mapping = {e.operator.op_id: e for e in pipeline.operators}
    return pipeline
