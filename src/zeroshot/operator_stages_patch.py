"""
Zeroshot-only patch for operator_stages: relax IndexNLJoin so pipelines that have
left-subtree nodes (Select, Temp, etc.) before the join do not assert. Keeps
operator_stages.py untouched; applied when zeroshot conversion/training/eval runs.
"""


def _json_in_subtree(node_json: dict, root_json: dict) -> bool:
    """Return True if node_json is root_json or is in the tree under root_json (left/right/input)."""
    if node_json is root_json:
        return True
    for key in ("left", "right", "input"):
        if key in root_json and isinstance(root_json.get(key), dict):
            if _json_in_subtree(node_json, root_json[key]):
                return True
    return False


def apply_zeroshot_operator_stages_patch() -> None:
    """Patch get_operator_stage so IndexNLJoin accepts previous op in left/right subtree (not only direct child)."""
    import src.operator_stages as _stages
    from src.operators import OperatorType
    from src.operator_stages import OperatorStage

    _original = _stages.get_operator_stage

    def _patched_get_operator_stage(op_index: int, op, pipeline_ops: list) -> OperatorStage:
        if op.type != OperatorType.IndexNLJoin:
            return _original(op_index, op, pipeline_ops)
        # Zeroshot: allow previous op to be in left/right subtree (not only direct left/right child)
        assert op_index > 0
        input_op = pipeline_ops[op_index - 1]
        in_left = op.json.get("left") and _json_in_subtree(input_op.json, op.json["left"])
        in_right = op.json.get("right") and _json_in_subtree(input_op.json, op.json["right"])
        if not in_left and not in_right:
            return OperatorStage.Probe
        if op_index != len(pipeline_ops) - 1:
            return OperatorStage.Probe
        elif len(op.parents) == 0:
            return OperatorStage.Probe if in_left else OperatorStage.Build
        else:
            return OperatorStage.Build if in_right else OperatorStage.Probe

    _stages.get_operator_stage = _patched_get_operator_stage
