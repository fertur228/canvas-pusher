"""Optional offline integration with genuine upstream files, never synthetic ones."""
from pathlib import Path
import pytest
from src.neural.audit import audit_sources
from .test_loader import DATA


def test_entire_induced_graph_matches_pinned_upstream():
    cache = DATA.parent / "cache"
    if not all((cache / name).exists() for name in ("neurons.csv.gz", "connections.csv.gz", "annotations.tsv")):
        pytest.skip("Upstream audit requires the optional source cache; bundled graph tests still run offline")
    report = audit_sources(DATA, cache)
    assert report["source_hashes_verified"]
    assert report["all_neuron_ids_verified"]
    assert report["all_annotations_verified"]
    assert report["induced_topology_exactly_preserved"]
