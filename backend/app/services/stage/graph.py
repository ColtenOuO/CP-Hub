import json
from pathlib import Path

STAGES_PATH = Path(__file__).resolve().parents[5] / "static" / "stages.json"


class CyclicDependencyError(ValueError):
    pass


class StageGraph:
    def __init__(self, stages: list[dict]):
        self.stages: dict[int, dict] = {s["id"]: s for s in stages}
        self._validate()

    @classmethod
    def load(cls) -> "StageGraph":
        stages = json.loads(STAGES_PATH.read_text())
        return cls(stages)

    def _validate(self) -> None:
        for stage_id, stage in self.stages.items():
            for req in stage.get("requires", []):
                if req not in self.stages:
                    raise ValueError(f"Stage {stage_id} requires unknown stage {req}")

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[int, int] = {sid: WHITE for sid in self.stages}

        def dfs(node: int) -> None:
            color[node] = GRAY
            for req in self.stages[node].get("requires", []):
                if color[req] == GRAY:
                    raise CyclicDependencyError(f"Cycle detected: stage {req} is a transitive dependency of itself")
                if color[req] == WHITE:
                    dfs(req)
            color[node] = BLACK

        for sid in self.stages:
            if color[sid] == WHITE:
                dfs(sid)

    def get_stage(self, stage_id: int) -> dict:
        return self.stages[stage_id]

    def all_stages(self) -> list[dict]:
        return list(self.stages.values())

    def is_unlocked(self, stage_id: int, completed_ids: set[int]) -> bool:
        return all(req in completed_ids for req in self.stages[stage_id].get("requires", []))

    def available_to_enroll(self, completed_ids: set[int], enrolled_ids: set[int]) -> list[dict]:
        return [s for s in self.stages.values() if self.is_unlocked(s["id"], completed_ids) and s["id"] not in enrolled_ids]
