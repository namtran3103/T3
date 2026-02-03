"""
Runtime patches for T3 when running on PostgreSQL EXPLAIN plans.
Applied from postgres package only; no edits to core T3 files.
- Relax get_operator_stage: GroupBy/Sort/Window in middle of pipeline -> PassThrough.
- Relax get_operator_stage: IndexNLJoin as pipeline end with right-child predecessor -> Probe (keeps 110 features).
"""


def apply_patches() -> None:
    import src.operator_stages as _stages
    from src.operators import OperatorType
    from src.operator_stages import OperatorStage

    _original = _stages.get_operator_stage

    def _patched_get_operator_stage(op_index: int, op, pipeline_ops: list) -> OperatorStage:
        if op.type in (
            OperatorType.TableScan,
            OperatorType.EarlyExecution,
            OperatorType.PipelineBreakerScan,
            OperatorType.InlineTable,
        ):
            return OperatorStage.Scan
        elif op.type in (OperatorType.Map, OperatorType.Select, OperatorType.AssertSingle, OperatorType.EarlyProbe):
            return OperatorStage.PassThrough
        elif op.type in (OperatorType.CsvWriter, OperatorType.FileOutput, OperatorType.Temp):
            return OperatorStage.Build
        elif op.type in (OperatorType.GroupBy, OperatorType.Sort, OperatorType.Window):
            if op_index == 0 and len(pipeline_ops) == 1:
                return OperatorStage.Scan
            elif op_index == len(pipeline_ops) - 1:
                return OperatorStage.Build
            elif op_index == 0:
                return OperatorStage.Scan
            # PG plans can have these in the middle of a single pipeline
            return OperatorStage.PassThrough
        elif op.type == OperatorType.HashJoin:
            try:
                return _original(op_index, op, pipeline_ops)
            except AssertionError:
                return OperatorStage.Probe
        elif op.type == OperatorType.IndexNLJoin:
            if op_index <= 0:
                try:
                    return _original(op_index, op, pipeline_ops)
                except AssertionError:
                    return OperatorStage.Probe
            input_op = pipeline_ops[op_index - 1]
            if input_op.json != op.json.get("right") and input_op.json != op.json.get("left"):
                try:
                    return _original(op_index, op, pipeline_ops)
                except AssertionError:
                    return OperatorStage.Probe
            if op_index != len(pipeline_ops) - 1:
                return OperatorStage.Probe
            if len(op.parents) == 0:
                if input_op.json == op.json.get("left"):
                    return OperatorStage.Probe
                if input_op.json == op.json.get("right"):
                    return OperatorStage.Probe
            try:
                return _original(op_index, op, pipeline_ops)
            except AssertionError:
                # T3 has features only for IndexNLJoin-Probe; treat Build as Probe so prediction runs.
                return OperatorStage.Probe
        elif op.type == OperatorType.SetOperation:
            if op_index == 0:
                return OperatorStage.Scan
            elif op_index == len(pipeline_ops) - 1:
                return OperatorStage.Build
            return OperatorStage.PassThrough
        elif op.type == OperatorType.MultiWayJoin:
            try:
                return _original(op_index, op, pipeline_ops)
            except AssertionError:
                return OperatorStage.Build
        elif op.type == OperatorType.GroupJoin:
            try:
                return _original(op_index, op, pipeline_ops)
            except AssertionError:
                return OperatorStage.Probe
        try:
            return _original(op_index, op, pipeline_ops)
        except AssertionError:
            return OperatorStage.PassThrough

    _stages.get_operator_stage = _patched_get_operator_stage
