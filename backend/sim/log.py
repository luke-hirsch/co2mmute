"""The detailed per-round report the host can download. Moved verbatim."""

import io

class SimulationLog:
    """Collects detailed simulation logs into a downloadable text report."""

    def __init__(self):
        self._buf = io.StringIO()
        self._edge_names: dict[int, str] = {}  # edge_id -> name
        self._route_labels: dict[int, str] = {}  # route_pk -> "Player/Agent#N (mode)"
        # Per-edge per-route sample tracking: (route_pk, edge_id) -> {enter_tick, exit_tick, ...}
        self._sample_edge_events: dict[tuple[int, int], dict] = {}

    def set_edge_names(self, edge_names: dict[int, str]):
        self._edge_names = edge_names

    def set_route_labels(self, route_labels: dict[int, str]):
        self._route_labels = route_labels

    def _edge_label(self, edge_id: int) -> str:
        name = self._edge_names.get(edge_id, "")
        return f"Edge {edge_id} ({name})" if name else f"Edge {edge_id}"

    def _route_label(self, route_pk: int) -> str:
        return self._route_labels.get(route_pk, f"Route {route_pk}")

    def write(self, line: str):
        self._buf.write(line + "\n")

    def header(self, text: str):
        sep = "=" * 70
        self._buf.write(f"\n{sep}\n{text}\n{sep}\n")

    def subheader(self, text: str):
        self._buf.write(f"\n--- {text} ---\n")

    def get_text(self) -> str:
        return self._buf.getvalue()

