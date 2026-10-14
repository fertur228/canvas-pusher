"""Boundary and directed-path integration checks use genuine cached FlyWire data."""
from pathlib import Path
import pytest
from src.neural.connectivity import analyze
from src.neural.loader import load_connectome
from src.neural.audit import audit_sources
from .test_loader import DATA


def test_source_boundary_and_directed_paths():
    cache = DATA.parent / "cache"
    if not (cache / "connections.csv.gz").exists():
        pytest.skip("Optional pinned source cache not present")
    graph = load_connectome(DATA)
    report = analyze(graph, cache)
    for gf, expected, omitted in zip(report["giant_fibers"], ((329, 305), (428, 539)), (733, 814)):
        assert tuple(gf["direct_type_inputs"][t]["synapses"] for t in ("LC4", "LPLC2")) == expected
        assert all(v["all_direct_edges_retained"] for v in gf["direct_type_inputs"].values())
        assert gf["incoming_boundary"]["omitted_synapses"] == omitted
        assert all(e["post_root_id"] == gf["root_id"] for paths in gf["direct_paths"].values() for p in paths for e in p["edges"])
        for paths in gf["top_two_hop_paths"].values():
            for path in paths:
                first, last = path["edges"]
                assert first["post_root_id"] == last["pre_root_id"]
                assert last["post_root_id"] == gf["root_id"]
                assert first["synapses"] > 0 and last["synapses"] > 0


def test_boundary_expansion_preserves_original_and_is_exact_source_induced_graph():
    cache = DATA.parent / "cache"
    expanded_path = cache / "gf-boundary-complete"
    if not expanded_path.exists():
        pytest.skip("Generate the optional GF-boundary expansion first")
    original, expanded = load_connectome(DATA), load_connectome(expanded_path)
    assert expanded.stats == {"neurons": 1660, "connection_rows": 32009, "directed_pairs": 19773,
                              "synapses": 321594, "weak_components": 1}
    assert set(original.neurons) <= set(expanded.neurons)
    assert set(original.synapses) <= set(expanded.synapses)
    report = audit_sources(expanded_path, cache)
    assert report["induced_topology_exactly_preserved"]
