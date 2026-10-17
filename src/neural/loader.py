"""Integrity-checked, offline loading of a compact connectome extraction."""
from dataclasses import dataclass
from pathlib import Path
import csv
import hashlib
import json

from .models import Neuron, Synapse


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class Connectome:
    neurons: tuple[Neuron, ...]
    synapses: tuple[Synapse, ...]
    manifest: dict

    def validate(self):
        ids = {n.root_id for n in self.neurons}
        if not ids or len(ids) != len(self.neurons):
            raise ValueError("Empty or duplicate neurons")
        seen = set()
        for edge in self.synapses:
            if edge.pre_root_id not in ids or edge.post_root_id not in ids:
                raise ValueError("Connection references a missing neuron")
            key = (edge.pre_root_id, edge.post_root_id, edge.neuropil, edge.nt_type)
            if key in seen:
                raise ValueError("Duplicate connection row")
            seen.add(key)
        return self

    def components(self) -> list[set[str]]:
        adjacency = {n.root_id: set() for n in self.neurons}
        for edge in self.synapses:
            adjacency[edge.pre_root_id].add(edge.post_root_id)
            adjacency[edge.post_root_id].add(edge.pre_root_id)
        unseen = set(adjacency)
        result = []
        while unseen:
            todo = [min(unseen, key=int)]
            component = set()
            while todo:
                node = todo.pop()
                if node not in unseen:
                    continue
                unseen.remove(node)
                component.add(node)
                todo.extend(adjacency[node] & unseen)
            result.append(component)
        return result

    @property
    def stats(self) -> dict:
        return {
            "neurons": len(self.neurons),
            "connection_rows": len(self.synapses),
            "directed_pairs": len({(s.pre_root_id, s.post_root_id) for s in self.synapses}),
            "synapses": sum(s.syn_count for s in self.synapses),
            "weak_components": len(self.components()),
        }


def load_connectome(directory: str | Path) -> Connectome:
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("Unsupported connectome schema")
    if manifest.get("kind") not in {"biological", "synthetic_test_fixture"}:
        raise ValueError("Dataset must declare biological or synthetic provenance")
    if manifest["kind"] == "biological":
        if manifest.get("dataset") != "FlyWire FAFB" or manifest.get("version") != "783":
            raise ValueError("This importer supports only FlyWire FAFB v783")
        if not manifest.get("sources") or not manifest.get("license"):
            raise ValueError("Missing biological provenance")
    for filename in ("neurons.csv", "connections.csv"):
        if sha256(directory / filename) != manifest["files"][filename]["sha256"]:
            raise ValueError(f"Integrity check failed: {filename}")
    with (directory / "neurons.csv").open(newline="") as stream:
        neurons = tuple(Neuron(**row) for row in csv.DictReader(stream))
    with (directory / "connections.csv").open(newline="") as stream:
        synapses = tuple(Synapse(**{**row, "syn_count": int(row["syn_count"])}) for row in csv.DictReader(stream))
    graph = Connectome(neurons, synapses, manifest).validate()
    if graph.stats != manifest["counts"]:
        raise ValueError("Manifest counts do not match data")
    if manifest.get("selection", {}).get("require_weakly_connected") and len(graph.components()) != 1:
        raise ValueError("Subset is disconnected")
    return graph
