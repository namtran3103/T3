import math
from functools import cmp_to_key
from typing import Tuple, Optional

from src.database import Database
from src.operator_stages import ExecutionPhase, build_pipeline, OperatorStage
from src.operator_stages import Pipeline
from src.operators import Operator, Expressions
from src.operators import OperatorType
from src.operators import parse_operator_type


class QueryPlan:
    operators: dict[int, Operator]
    execution_phases: list[ExecutionPhase]
    pipelines: list[Pipeline]
    db: Database
    ius: dict[str, float]  # maps from iu name to estimated size
    predicted_cardinalities: bool

    def __init__(self, plan: dict, db: Database, predicted_cardinalities: bool):
        self.json_plan = plan["plan"]
        self.operators = {}
        self.db = db
        self.predicted_cardinalities = predicted_cardinalities
        self.ius = self._parse_ius(plan["ius"])
        self._parse_operator(self.json_plan, [])

    @staticmethod
    def _parse_ius(ius: list[dict]) -> dict[str, float]:
        return {iu["iu"]: iu["estimatedSize"] for iu in ius}

    @staticmethod
    def _get_output_cardinality(op: dict, predicted_cardinalities: bool) -> float:
        output_cardinality = 0
        found = False
        if "cardinality" in op and op["operator"] == "tablescan":
            # tablescan ops in below nested loop join operators have no analyzePlanCardinality
            output_cardinality = op["cardinality"]
            found = True
        if "analyzePlanCardinality" in op and not predicted_cardinalities:
            # we overwrite the cardinality if correct cardinalities are present
            output_cardinality = op["analyzePlanCardinality"]
            found = True
        if not found:
            assert True, "could not find output cardinality"
        return output_cardinality

    @staticmethod
    def _get_left_cardinality(op: dict, operator_type: OperatorType, predicted_cardinalities: bool) -> float:
        assert operator_type.is_join_type()
        if (predicted_cardinalities or "analyzePlanCardinality" not in op["left"]) and "cardinality" in op["left"]:
            return op["left"]["cardinality"]
        else:
            return op["left"]["analyzePlanCardinality"]

    def _get_table_name(self, op: dict) -> str:
        """
        our database does not give us quotes on table names, so we add them if needed
        """
        return self.db.schema.quote_table_name(op["tablename"])

    def _get_input_cardinality(self, op: dict, operator_type: OperatorType, predicted_cardinalities: bool) -> float:
        if operator_type.is_join_type():
            return self._get_left_cardinality(op, operator_type, predicted_cardinalities)
        elif operator_type == OperatorType.TableScan:
            if "inputCardinality" in op:
                return float(op["inputCardinality"])
            return self.db.schema.get_table_scan_size(self._get_table_name(op))
        elif operator_type in (OperatorType.PipelineBreakerScan, OperatorType.InlineTable):
            return self._get_output_cardinality(op, predicted_cardinalities)
            # return op["cardinality"]
        elif operator_type == OperatorType.MultiWayJoin:
            return 0
        elif operator_type == OperatorType.SetOperation:
            if op["operation"] == "unionall":
                return 0
            else:
                return self._get_output_cardinality(op, predicted_cardinalities)
        else:
            while not (
                ("analyzePlanCardinality" in op["input"] and not predicted_cardinalities)
                or "cardinality" in op["input"]
            ):
                op = op["input"]
            if "analyzePlanCardinality" in op["input"] and not predicted_cardinalities:
                return op["input"]["analyzePlanCardinality"]
            else:
                return op["input"]["cardinality"]

    def _get_right_cardinality(
        self, op: dict, operator_type: OperatorType, predicted_cardinalities: bool
    ) -> Optional[float]:
        if operator_type == OperatorType.IndexNLJoin:
            return self._get_input_cardinality(op["right"], parse_operator_type(op["right"]), predicted_cardinalities)
        if operator_type.is_join_type():
            return QueryPlan._get_output_cardinality(op["right"], predicted_cardinalities)
            # return op["right"]["cardinality"]
        else:
            return None

    def _get_tuple_size(self, op: dict) -> float:
        iu_sizes = []
        for iu in op["producedIUs"]:
            if type(iu) == str:
                iu_sizes.append(self.ius[iu])
            else:
                iu_sizes.append(iu["estimatedSize"])
        return sum(iu_sizes)

    @staticmethod
    def _annotate_child(parent: Operator, child: Operator):
        if parent.type.is_join_type():
            if parent.json["left"] == child.json:
                parent.input_op = child
            elif parent.json["right"] == child.json:
                parent.right_input_op = child
            else:
                assert False, "unhandeld join child"
        elif parent.type == OperatorType.SetOperation:
            parent.input_op = child
        elif parent.type == OperatorType.PipelineBreakerScan:
            if "pipelineBreaker" in parent.json:
                assert parent.json["pipelineBreaker"] == child.json
            parent.input_op = child
        elif parent.type == OperatorType.MultiWayJoin:
            parent.input_op = child
        elif "input" in parent.json and parent.json["input"] == child.json:
            parent.input_op = child
        else:
            assert False, "unknown child"

    @staticmethod
    def _featurize_expression(
        expression: dict, result: Expressions, incoming_selectivity: float, expression_selectivity: float
    ):
        if "mode" in expression and expression["mode"] == "filter":
            QueryPlan._featurize_expression(expression["value"], result, incoming_selectivity, expression_selectivity)
        elif "mode" in expression and expression["mode"] == "joinfilter":
            result.join_filter_count += 1
        elif ("mode" in expression and expression["mode"] in ("<", "<=", ">", ">=", "=", "!=", "isnotnull", "is")) or (
            "expression" in expression and expression["expression"] in ("compare", "isnotnull", "is")
        ):
            # null checks should be similarly cheap as comparisons
            result.compare_count += 1
            result.compare_selectivity += incoming_selectivity
        elif "expression" in expression and expression["expression"] == "not":
            QueryPlan._featurize_expression(expression["input"], result, incoming_selectivity, expression_selectivity)
        elif "expression" in expression and expression["expression"] == "or":
            result.or_expression_count += 1
            result.or_selectivity += incoming_selectivity
            n_expressions = len(expression["input"])
            outgoing_sel = incoming_selectivity * expression_selectivity
            # we assume that number of expressions reached is uniformly distributed
            single_expression_sel = (incoming_selectivity - outgoing_sel) / n_expressions
            for i, input in enumerate(expression["input"]):
                current_incoming_sel = incoming_selectivity - i * single_expression_sel
                QueryPlan._featurize_expression(input, result, current_incoming_sel, single_expression_sel)
        elif "expression" in expression and expression["expression"] == "and":
            n_expressions = len(expression["input"])
            outgoing_sel = incoming_selectivity * expression_selectivity
            # we assume that number of expressions reached is uniformly distributed
            single_expression_sel = (incoming_selectivity - outgoing_sel) / n_expressions
            for i, input in enumerate(expression["input"]):
                current_incoming_sel = incoming_selectivity - i * single_expression_sel
                QueryPlan._featurize_expression(input, result, current_incoming_sel, single_expression_sel)
        elif "expression" in expression and expression["expression"] == "in":
            result.in_expression_count += 1
            result.in_expression_selectivity += incoming_selectivity
        elif ("mode" in expression and expression["mode"] in ("[]", "[)", "(]", "()")) or (
            "expression" in expression and expression["expression"] == "between"
        ):
            result.between_count += 1
            result.between_selectivity += incoming_selectivity
        elif "expression" in expression and expression["expression"] == "like":
            result.like_count += 1
            result.like_selectivity += incoming_selectivity
        elif "expression" in expression and expression["expression"] == "startswith":
            result.starts_with_count += 1
            result.starts_with_selectivity += incoming_selectivity
        elif ("mode" in expression and expression["mode"] == "false") or (
            "expression" in expression and expression["mode"] == "false"
        ):
            result.false_count = 0
        else:
            assert False, f"unhandled expression {expression}"

    @staticmethod
    def _get_expression_selectivity(expression: dict) -> float:
        if "estimatedSelectivity" in expression:
            return expression["estimatedSelectivity"]
        elif expression["expression"] == "compare":
            if expression["direction"] in ("<", "<=", ">", ">="):
                return 0.5
            elif expression["direction"] == "=":
                return 0.01
            elif expression["direction"] == "<>":
                return 0.99
        elif expression["expression"] in ("between", "isnotnull"):
            return 0.5
        elif expression["expression"] in ("in", "like", "startswith"):
            return 0.01
        elif expression["expression"] == "not":
            return 1.0 - QueryPlan._get_expression_selectivity(expression["input"])
        elif expression["expression"] == "and":
            selectivities = [QueryPlan._get_expression_selectivity(e) for e in expression["input"]]
            return math.prod(selectivities)
        elif expression["expression"] == "or":
            selectivities = [QueryPlan._get_expression_selectivity(e) for e in expression["input"]]
            return min([sum(selectivities), 1.0])
        assert False, "could not find selectivity for expression"

    def _list_expressions(self, op: dict) -> tuple[list[dict], list[float]]:
        restrictions = op["restrictions"]
        residuals = op["residuals"]
        expressions = restrictions + residuals
        selectivities = [self._get_expression_selectivity(e) for e in expressions]
        return expressions, selectivities

    def _parse_expressions(self, op: dict, operator_type: OperatorType) -> Expressions:
        result = Expressions()
        if operator_type == OperatorType.TableScan:
            expressions, selectivities = self._list_expressions(op)
            current_selectivity = 1.0
            for expression, selectivity in zip(expressions, selectivities):
                self._featurize_expression(expression, result, current_selectivity, selectivity)
                current_selectivity *= selectivity

        return result

    def _parse_operator(self, op: dict, parent: list[Operator]):
        assert len(parent) <= 1
        operator_type = parse_operator_type(op)
        output_cardinality = self._get_output_cardinality(op, self.predicted_cardinalities)
        input_cardinality = self._get_input_cardinality(op, operator_type, self.predicted_cardinalities)
        right_cardinality = self._get_right_cardinality(op, operator_type, self.predicted_cardinalities)
        output_tuple_size = self._get_tuple_size(op)

        expressions = self._parse_expressions(op, operator_type)

        current_op = Operator(
            operator_type,
            op["operator"],
            op["operatorId"],
            output_cardinality,
            input_cardinality,
            right_cardinality,
            output_tuple_size,
            expressions,
            parent,
            None,
            None,
            op,
        )

        if current_op.op_id in self.operators:
            self.operators[current_op.op_id].parents.extend(parent)
            return

        if operator_type.is_join_type():
            self._parse_operator(op["left"], [current_op])
            self._parse_operator(op["right"], [current_op])
        elif operator_type == OperatorType.MultiWayJoin:
            for input in op["inputs"]:
                self._parse_operator(input["op"], [current_op])
        elif operator_type == OperatorType.PipelineBreakerScan:
            # only one of the scanners will include the input
            if "pipelineBreaker" in op:
                self._parse_operator(op["pipelineBreaker"], [current_op])
        elif operator_type in (OperatorType.TableScan, OperatorType.InlineTable):
            pass
        elif operator_type == OperatorType.SetOperation:
            for a in op["arguments"]:
                self._parse_operator(a["input"], [current_op])
        else:
            self._parse_operator(op["input"], [current_op])

        for p in parent:
            self._annotate_child(p, current_op)

        assert current_op.op_id not in self.operators
        self.operators[current_op.op_id] = current_op

    def _get_operator_pipelines(self) -> dict[frozenset[int], Pipeline]:
        result = {}
        for pipeline in self.pipelines:
            ops = set()
            for op in pipeline.operators:
                ops.add(op.operator.op_id)
            result[frozenset(ops)] = pipeline
        return result

    @staticmethod
    def _resolve_dangling_pipelines(
        dangling_pipelines: dict[int, frozenset[int]],
        unused_pipelines: dict[frozenset, Pipeline],
        op_id_to_benchmark_id: dict[int, int],
        result: dict[Tuple[int, int], ExecutionPhase],
    ):
        for p, ops in dangling_pipelines.items():
            current_pipelines = {}
            for op in ops:
                potential_pipeline = None
                for u_ops in unused_pipelines:
                    if op in u_ops:
                        potential_pipeline = u_ops
                        break
                current_pipelines[op] = potential_pipeline

            total_set = {c_op for current_pipeline in current_pipelines.values() for c_op in current_pipeline}

            if total_set == ops:
                for op in ops:
                    containing_pipeline = unused_pipelines[current_pipelines[op]]
                    result[op_id_to_benchmark_id[op], p] = containing_pipeline.get_execution_phase(op)
                for pipeline in set(current_pipelines.values()):
                    unused_pipelines.pop(pipeline)

    def annotate_samples(
        self,
        operator_pipelines: list[Tuple[int, int]],
        benchmark_operator_names: dict[int, str],  # names of operators by benchmark file id
        pipeline_names: dict[int, str],
    ) -> dict[Tuple[int, int], ExecutionPhase]:
        no_pipeline_names = {"No pipeline", "No pipeline running"}
        op_id_to_benchmark_id: dict[int, int] = {}
        operator_dict: dict[str, Operator] = {op.operator_name: op for op in self.operators.values()}
        result = {}
        pipeline_ops = {}

        for o, p in operator_pipelines:
            name = benchmark_operator_names[o]
            if pipeline_names[p] in no_pipeline_names:
                continue
            elif name in operator_dict:
                if p not in pipeline_ops:
                    pipeline_ops[p] = set()
                pipeline_ops[p].add(operator_dict[name].op_id)
                op_id_to_benchmark_id[operator_dict[name].op_id] = o
            else:
                print(f"unknown operator {name}")

        _operator_pipelines = self._get_operator_pipelines()
        dangling_pipelines: dict[int, frozenset[int]] = {}
        for p, ops in pipeline_ops.items():
            op_set = frozenset(ops)
            if op_set in _operator_pipelines:
                current_pipeline = _operator_pipelines.pop(frozenset(ops))
                for op in op_set:
                    result[op_id_to_benchmark_id[op], p] = current_pipeline.get_execution_phase(op)
            else:
                dangling_pipelines[p] = op_set
        self._resolve_dangling_pipelines(dangling_pipelines, _operator_pipelines, op_id_to_benchmark_id, result)
        return result

    def fix_union_all(self):
        """
        union-all pipelines are completely wrong, we need to identify the target pipeline that runs on the resulting
        data of the union all operator.
        All operators of this pipline will be appended to all pipelines that end with the union_all operator.
        """
        for op in self.operators.values():
            if op.type == OperatorType.SetOperation and op.json["operation"] == "unionall":
                tail_pipeline: Optional[Pipeline] = None
                for pipeline in self.pipelines:
                    if len(pipeline.operators) == 0:
                        continue
                    if pipeline.operators[0].operator == op:
                        tail_pipeline = pipeline
                        break
                tail_pipeline.start = 0
                tail_pipeline.stop = 0
                tail_pipeline.operators[0].stage = OperatorStage.PassThrough
                union_cardinality = tail_pipeline.operators[0].operator.output_cardinality
                if union_cardinality < 1:
                    union_cardinality = 1
                for pipeline in self.pipelines:
                    if len(pipeline.operators) == 0:
                        continue
                    if pipeline.operators[-1].operator == op:
                        fraction = pipeline.operators[-2].operator.output_cardinality / union_cardinality
                        # assert pipeline.operators[-1].stage == OperatorStage.PassThrough
                        pipeline.operators[-1].stage = OperatorStage.PassThrough
                        append_ops = [op.copy() for op in tail_pipeline.operators[1:]]
                        for append_op in append_ops:
                            append_op.fraction *= fraction
                            append_op.pipeline = pipeline
                        pipeline.operators += append_ops
                tail_pipeline.operators = []
                # return

    def build_pipelines(self, pipelines: list[dict]):
        """
        build pipelines using only the json plan
        """
        operator_dict: dict[int, Operator] = {op.json["analyzePlanId"]: op for op in self.operators.values()}
        result = []
        for pipeline in pipelines:
            if pipeline["operators"] == [0] and 0 not in operator_dict and pipeline["duration"] == 0:
                assert False, "could not assign operators to pipelines"
            ops = [operator_dict[op_id] for op_id in pipeline["operators"]]
            ops.sort(key=cmp_to_key(lambda b, a: a.precedes(b)))
            start = float(pipeline["start"])
            stop = float(pipeline["stop"])
            result.append(build_pipeline(ops, start, stop))
        self.pipelines = result
        self.fix_union_all()
