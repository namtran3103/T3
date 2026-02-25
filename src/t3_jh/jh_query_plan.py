"""
Johannes-style QueryPlan: plan_parameters (est_card, act_card), left/right/input, card_type, db_statistics.
"""
import math
from enum import Enum
from functools import cmp_to_key
from typing import Dict, Optional, Tuple

from .jh_operator_stages import ExecutionPhase, OperatorStage, Pipeline, build_pipeline
from .jh_operators import Expressions, Operator, OperatorType, parse_operator_type


class CardType(Enum):
    pg = 1
    act = 2
    deepdb = 3


class QueryPlan:
    def __init__(self, plan: dict, card_type: CardType, db_statistics: Dict):
        self.db_statistics = db_statistics
        self.json_plan = plan
        self.operators = {}
        self.ius = None
        self._parse_operator(self.json_plan, [], card_type=card_type)

    @staticmethod
    def _get_output_cardinality(op: dict, card_type: CardType) -> float:
        pp = op.get("plan_parameters", {})
        if card_type == CardType.pg:
            return float(pp.get("est_card", 1))
        elif card_type == CardType.act:
            return float(pp.get("act_card", pp.get("est_card", 1)))
        elif card_type == CardType.deepdb:
            return float(pp.get("deepdb_card", 1))
        raise ValueError(f"Unknown cardinality type {card_type}")

    @staticmethod
    def _get_left_cardinality(op: dict, operator_type: OperatorType, card_type: CardType) -> float:
        assert operator_type.is_join_type()
        return QueryPlan._get_output_cardinality(op["left"], card_type=card_type)

    def _get_table_name(self, op: dict) -> str:
        return op["plan_parameters"].get("table_name", "unknown")

    def _get_input_cardinality(
        self, op: dict, operator_type: OperatorType, card_type: CardType
    ) -> float:
        if operator_type.is_join_type():
            return self._get_left_cardinality(op, operator_type, card_type=card_type)
        elif operator_type == OperatorType.TableScan:
            tname = self._get_table_name(op)
            if tname not in self.db_statistics.get("table_stats_dict", {}):
                return float(op["plan_parameters"].get("act_card", op["plan_parameters"].get("est_card", 1)))
            return self.db_statistics["table_stats_dict"][tname]["reltuples"]
        elif operator_type == OperatorType.IdxScan:
            return self._get_output_cardinality(op, card_type=card_type)
        elif operator_type in (OperatorType.PipelineBreakerScan, OperatorType.InlineTable):
            return self._get_output_cardinality(op, card_type=card_type)
        elif operator_type == OperatorType.MultiWayJoin:
            return 0
        elif operator_type == OperatorType.SetOperation:
            if op.get("operation", "unionall") == "unionall":
                return 0
            return self._get_output_cardinality(op, card_type=card_type)
        else:
            assert "input" in op
            return self._get_output_cardinality(op["input"], card_type=card_type)

    def _get_right_cardinality(
        self, op: dict, operator_type: OperatorType, card_type: CardType
    ) -> Optional[float]:
        if operator_type.is_join_type():
            return QueryPlan._get_output_cardinality(op["right"], card_type=card_type)
        return None

    def _get_tuple_size(self, op: dict) -> float:
        return op["plan_parameters"].get("est_width", 8.0)

    @staticmethod
    def _annotate_child(parent: Operator, child: Operator):
        if parent.type.is_join_type():
            if parent.json["left"] == child.json:
                parent.input_op = child
            elif parent.json["right"] == child.json:
                parent.right_input_op = child
            else:
                assert False, "unhandled join child"
        elif parent.type == OperatorType.SetOperation:
            parent.input_op = child
        elif parent.type == OperatorType.PipelineBreakerScan:
            if "pipelineBreaker" in parent.json:
                parent.input_op = child
        elif parent.type == OperatorType.MultiWayJoin:
            parent.input_op = child
        elif "input" in parent.json and parent.json["input"] == child.json:
            parent.input_op = child
        else:
            assert False, "unknown child"

    @staticmethod
    def _featurize_expression(
        expression: dict,
        result: Expressions,
        incoming_selectivity: float,
        expression_selectivity: float,
    ):
        if "table_name2" in expression:
            result.join_filter_count += 1
        elif expression.get("operator") in (
            "<", "<=", ">", ">=", "=", "!=",
            "isnotnull", "is", "IS NOT NULL", "IS NULL",
        ):
            result.compare_count += 1
            result.compare_selectivity += incoming_selectivity
        elif expression.get("operator") in ("not", "NOT"):
            if expression.get("children"):
                QueryPlan._featurize_expression(
                    expression["children"][0], result, incoming_selectivity, expression_selectivity
                )
        elif expression.get("operator") in ("or", "OR"):
            result.or_expression_count += 1
            result.or_selectivity += incoming_selectivity
            for i, input_expr in enumerate(expression.get("children", [])):
                QueryPlan._featurize_expression(
                    input_expr, result, incoming_selectivity, expression_selectivity
                )
        elif expression.get("operator") in ("and", "AND"):
            for input_expr in expression.get("children", []):
                QueryPlan._featurize_expression(
                    input_expr, result, incoming_selectivity, expression_selectivity
                )
        elif expression.get("operator") in ("in", "IN"):
            result.in_expression_count += 1
            result.in_expression_selectivity += incoming_selectivity
        elif ("mode" in expression and expression["mode"] in ("[]", "[)", "(]", "()")) or (
            expression.get("expression") == "between"
        ):
            result.between_count += 1
            result.between_selectivity += incoming_selectivity
        elif expression.get("operator") in ("like", "LIKE", "NOT LIKE"):
            result.like_count += 1
            result.like_selectivity += incoming_selectivity
        elif expression.get("operator") in ("startswith", "STARTSWITH"):
            result.starts_with_count += 1
            result.starts_with_selectivity += incoming_selectivity
        elif expression.get("operator") in ("<", "<=", ">", ">=", "="):
            result.compare_count += 1
            result.compare_selectivity += incoming_selectivity

    @staticmethod
    def _get_expression_selectivity(expression: dict) -> float:
        if "estimatedSelectivity" in expression:
            return expression["estimatedSelectivity"]
        op = expression.get("operator", "")
        if op in ("<", "<=", ">", ">="):
            return 0.5
        if op == "=":
            return 0.01
        if op in ("<>", "!="):
            return 0.99
        if op in ("between", "isnotnull", "BETWEEN", "IS NOT NULL", "IS NULL"):
            return 0.5
        if op in ("in", "like", "startswith", "IN", "LIKE", "STARTSWITH"):
            return 0.01
        if op == "NOT LIKE":
            return 0.99
        if op in ("not", "NOT"):
            return 1.0 - QueryPlan._get_expression_selectivity(expression.get("children", [{}])[0])
        if op in ("and", "AND"):
            return math.prod(
                QueryPlan._get_expression_selectivity(e) for e in expression.get("children", [])
            )
        if op in ("or", "OR"):
            sels = [QueryPlan._get_expression_selectivity(e) for e in expression.get("children", [])]
            return min(sum(sels), 1.0)
        return 0.5

    def _list_expressions(self, op: dict) -> Tuple[list, list]:
        filters = [op["plan_parameters"]["filter"]] if op["plan_parameters"].get("filter") else []
        joins = [op["plan_parameters"]["join"]] if op["plan_parameters"].get("join") else []
        expressions = filters + joins
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

    def _parse_operator(self, op: dict, parent: list, card_type: CardType):
        assert len(parent) <= 1
        operator_type = parse_operator_type(op)
        output_cardinality = self._get_output_cardinality(op, card_type=card_type)
        input_cardinality = self._get_input_cardinality(op, operator_type, card_type=card_type)
        right_cardinality = self._get_right_cardinality(op, operator_type, card_type=card_type)
        output_tuple_size = self._get_tuple_size(op)
        expressions = self._parse_expressions(op, operator_type)
        assert "op_id" in op["plan_parameters"]

        current_op = Operator(
            type=operator_type,
            operator_name=op["plan_parameters"]["op_name"],
            op_id=op["plan_parameters"]["op_id"],
            output_cardinality=output_cardinality,
            input_cardinality=input_cardinality,
            right_input_cardinality=right_cardinality,
            output_tuple_size=output_tuple_size,
            expressions=expressions,
            parents=parent,
            input_op=None,
            right_input_op=None,
            json=op,
        )

        if current_op.op_id in self.operators:
            self.operators[current_op.op_id].parents.extend(parent)
            # Recurse anyway so every node gets an operator (avoids missing op_ids when
            # the same node is reachable from multiple paths and we took the other path first).

        def recurse_and_annotate(child_op: dict) -> None:
            self._parse_operator(child_op, [current_op], card_type=card_type)
            child_obj = self.operators.get(child_op["plan_parameters"]["op_id"])
            if child_obj is not None:
                self._annotate_child(current_op, child_obj)

        if operator_type == OperatorType.MultiWayJoin:
            for inp in op.get("inputs", []):
                recurse_and_annotate(inp.get("op", inp))
        elif operator_type == OperatorType.PipelineBreakerScan:
            if "pipelineBreaker" in op:
                recurse_and_annotate(op["pipelineBreaker"])
        elif operator_type == OperatorType.SetOperation:
            for a in op.get("arguments", []):
                recurse_and_annotate(a.get("input", a))
        elif operator_type in (
            OperatorType.TableScan,
            OperatorType.InlineTable,
            OperatorType.IdxScan,
        ):
            # Some scans have "input" (e.g. Bitmap Heap Scan -> Bitmap Index Scan); recurse so
            # every node gets an operator and pipeline op_ids resolve.
            if "input" in op and op["input"] is not None:
                recurse_and_annotate(op["input"])
        else:
            if "input" in op:
                recurse_and_annotate(op["input"])
            if "left" in op:
                recurse_and_annotate(op["left"])
            if "right" in op and op["right"] is not None:
                recurse_and_annotate(op["right"])

        for p in parent:
            self._annotate_child(p, current_op)
        if current_op.op_id not in self.operators:
            self.operators[current_op.op_id] = current_op

    def _get_operator_pipelines(self) -> dict:
        result = {}
        for pipeline in self.pipelines:
            ops = set(o.operator.op_id for o in pipeline.operators)
            result[frozenset(ops)] = pipeline
        return result

    @staticmethod
    def _resolve_dangling_pipelines(
        dangling_pipelines: dict,
        unused_pipelines: dict,
        op_id_to_benchmark_id: dict,
        result: dict,
    ):
        for p, ops in dangling_pipelines.items():
            current_pipelines = {}
            for op in ops:
                for u_ops in unused_pipelines:
                    if op in u_ops:
                        current_pipelines[op] = u_ops
                        break
            total_set = {c_op for pl in current_pipelines.values() for c_op in pl}
            if total_set == ops:
                for op in ops:
                    containing_pipeline = unused_pipelines[current_pipelines[op]]
                    result[op_id_to_benchmark_id[op], p] = containing_pipeline.get_execution_phase(op)
                for pl in set(current_pipelines.values()):
                    unused_pipelines.pop(pl, None)

    def fix_union_all(self):
        for op in self.operators.values():
            if op.type != OperatorType.SetOperation or op.json.get("operation") != "unionall":
                continue
            tail_pipeline = None
            for pipeline in self.pipelines:
                if not pipeline.operators:
                    continue
                if pipeline.operators[0].operator == op:
                    tail_pipeline = pipeline
                    break
            if tail_pipeline is None:
                continue
            tail_pipeline.start = 0
            tail_pipeline.stop = 0
            tail_pipeline.operators[0].stage = OperatorStage.PassThrough
            union_cardinality = max(1, tail_pipeline.operators[0].operator.output_cardinality)
            for pipeline in self.pipelines:
                if not pipeline.operators or pipeline.operators[-1].operator != op:
                    continue
                fraction = pipeline.operators[-2].operator.output_cardinality / union_cardinality
                pipeline.operators[-1].stage = OperatorStage.PassThrough
                append_ops = [o.copy() for o in tail_pipeline.operators[1:]]
                for append_op in append_ops:
                    append_op.fraction *= fraction
                    append_op.pipeline = pipeline
                pipeline.operators += append_ops
            tail_pipeline.operators = []

    def build_pipelines(self, pipelines: list):
        operator_dict = {
            op.json["plan_parameters"]["analyze_plan_id"]: op
            for op in self.operators.values()
        }
        result = []
        for pipeline in pipelines:
            op_ids = pipeline["operators"]
            if not op_ids:
                continue
            if op_ids == [0] and 0 not in operator_dict and pipeline["duration"] == 0:
                continue
            ops = [operator_dict.get(op_id) for op_id in op_ids]
            missing_ids = [op_id for op_id in op_ids if operator_dict.get(op_id) is None]
            if missing_ids:
                print(
                    f"build_pipelines: pipeline with op_ids {op_ids} has missing op_ids "
                    f"{missing_ids} (keeping {len(op_ids) - len(missing_ids)} ops)"
                )
            ops = [o for o in ops if o is not None]
            if not ops:
                continue
            ops.sort(key=cmp_to_key(lambda b, a: a.precedes(b)))
            start = float(pipeline["start"])
            stop = float(pipeline["stop"])
            result.append(build_pipeline(ops, start, stop))
        self.pipelines = result
        self.fix_union_all()
