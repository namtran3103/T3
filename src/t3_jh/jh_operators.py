from dataclasses import dataclass
from typing import Optional

from .jh_util import AutoNumber


class OperatorType(AutoNumber):
    TableScan = ()
    InlineTable = ()
    PipelineBreakerScan = ()
    Temp = ()
    EarlyExecution = ()
    Select = ()
    Map = ()
    MultiWayJoin = ()
    HashJoin = ()
    IndexNLJoin = ()
    GroupJoin = ()
    GroupBy = ()
    Sort = ()
    SetOperation = ()
    Window = ()
    FileOutput = ()
    CsvWriter = ()
    AssertSingle = ()
    EarlyProbe = ()
    AnalyzePlan = ()
    IdxScan = ()
    NLJoin = ()
    MergeJoin = ()
    Aggregate = ()

    def is_join_type(self):
        return self in {
            OperatorType.HashJoin,
            OperatorType.IndexNLJoin,
            OperatorType.GroupJoin,
            OperatorType.MergeJoin,
            OperatorType.NLJoin,
        }


@dataclass
class Expressions:
    join_filter_count: int = 0
    false_count: int = 0
    like_count: int = 0
    like_selectivity: float = 0.0
    compare_count: int = 0
    compare_selectivity: float = 0.0
    in_expression_count: int = 0
    in_expression_selectivity: float = 0.0
    between_count: int = 0
    between_selectivity: float = 0.0
    or_expression_count: int = 0
    or_selectivity: float = 0.0
    starts_with_count: int = 0
    starts_with_selectivity: float = 0.0


@dataclass
class Operator:
    type: OperatorType
    operator_name: str
    op_id: int
    output_cardinality: float
    input_cardinality: float
    right_input_cardinality: Optional[float]
    output_tuple_size: float
    expressions: Expressions
    parents: list["Operator"]
    input_op: Optional["Operator"]
    right_input_op: Optional["Operator"]
    json: dict

    def precedes(self, other_op: "Operator") -> int:
        if self == other_op:
            return 0
        current_ancestors = other_op.parents.copy()
        while len(current_ancestors) > 0:
            current_ancestor = current_ancestors.pop()
            if current_ancestor == self:
                return -1
            current_ancestors.extend(current_ancestor.parents)
        return 1


def parse_operator_type(op: dict, dbms: str = "pg") -> OperatorType:
    name = op["plan_parameters"]["op_name"]

    if dbms == "umbra":
        if name in ("hashjoin", "singletonjoin", "bnljoin"):
            return OperatorType.HashJoin
        elif name == "indexnljoin":
            return OperatorType.IndexNLJoin

    pg_name_map = {
        "Seq Scan": OperatorType.TableScan,
        "Parallel Seq Scan": OperatorType.TableScan,
        "Index Scan": OperatorType.IdxScan,
        "Index Only Scan": OperatorType.IdxScan,
        "Parallel Index Scan": OperatorType.IdxScan,
        "Hash Join": OperatorType.HashJoin,
        "Hash": OperatorType.Temp,
        "Index Nested Loop": OperatorType.IndexNLJoin,
        "Nested Loop": OperatorType.NLJoin,
        "Merge Join": OperatorType.MergeJoin,
        "Sort": OperatorType.Sort,
        "Aggregate": OperatorType.Aggregate,
        "Partial Aggregate": OperatorType.Aggregate,
        "Finalize Aggregate": OperatorType.Aggregate,
        "Simple Aggregate": OperatorType.Aggregate,
        "Gather": OperatorType.Select,
        "Gather Merge": OperatorType.Select,
        "Materialize": OperatorType.Temp,
        "Memoize": OperatorType.Select,
        "Limit": OperatorType.Select,
        "Append": OperatorType.Select,
        "Subquery Scan": OperatorType.Select,
        "Bitmap Heap Scan": OperatorType.TableScan,
        "Bitmap Index Scan": OperatorType.IdxScan,
        "Parallel Bitmap Heap Scan": OperatorType.TableScan,
        "Parallel Index Only Scan": OperatorType.IdxScan,
    }

    umbra_name_map = {
        "fileoutput": OperatorType.FileOutput,
        "csvwriter": OperatorType.CsvWriter,
        "sort": OperatorType.Sort,
        "window": OperatorType.Window,
        "select": OperatorType.Select,
        "groupby": OperatorType.GroupBy,
        "groupjoin": OperatorType.GroupJoin,
        "multiwayjoin": OperatorType.MultiWayJoin,
        "tablescan": OperatorType.TableScan,
        "inlinetable": OperatorType.InlineTable,
        "map": OperatorType.Map,
        "earlyexecution": OperatorType.EarlyExecution,
        "pipelinebreakerscan": OperatorType.PipelineBreakerScan,
        "temp": OperatorType.Temp,
        "setoperation": OperatorType.SetOperation,
        "assertsingle": OperatorType.AssertSingle,
        "earlyprobe": OperatorType.EarlyProbe,
        "analyzeplan": OperatorType.AnalyzePlan,
    }

    if dbms == "pg":
        name_map = pg_name_map
    elif dbms == "umbra":
        name_map = umbra_name_map
    else:
        raise ValueError(f"Unknown dbms {dbms}")

    if name not in name_map:
        raise ValueError(f"{name} missing in operator name map {name_map}")
    return name_map[name]
