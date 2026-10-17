from dataclasses import replace
from pathlib import Path
import shutil
import pytest

from src.neural.loader import load_connectome
from src.neural.models import Neuron, Synapse, root_id, synaptic_sign
from src.neural.ingest import choose_nodes, fetch_sources

DATA = Path(__file__).resolve().parents[2] / "data/neural/flywire_v783"


@pytest.mark.parametrize("value", ["0", "-1", "1.0", "01", "abc", str(2**64), 720575940622838154])
def test_rejects_lossy_or_invalid_ids(value):
    with pytest.raises(ValueError):
        root_id(value)


def test_ids_preserve_full_precision():
    assert root_id("720575940622838154") == "720575940622838154"


def test_missing_endpoint_and_duplicate_neuron(synthetic_graph):
    with pytest.raises(ValueError, match="missing"):
        replace(synthetic_graph, synapses=(Synapse("1", "4", "SYNTHETIC", 2, "ACH"),)).validate()
    with pytest.raises(ValueError, match="duplicate"):
        replace(synthetic_graph, neurons=(Neuron("1"), Neuron("1"))).validate()


def test_duplicate_edges_rejected(synthetic_graph):
    with pytest.raises(ValueError, match="Duplicate"):
        replace(synthetic_graph, synapses=synthetic_graph.synapses * 2).validate()


@pytest.mark.parametrize("count", [0, -1, 1.5, True])
def test_invalid_strength(count):
    with pytest.raises(ValueError):
        Synapse("1", "2", "SYNTHETIC", count, "ACH")


def test_unknown_transmitter_is_not_fabricated():
    assert [synaptic_sign(nt) for nt in ("ACH", "GABA", "GLUT", "DA", "UNKNOWN")] == [1, -1, 0, 0, 0]
    with pytest.raises(ValueError):
        Synapse("1", "2", "SYNTHETIC", 1, "invented")


def test_real_subset_integrity_and_giant_fiber_inputs():
    graph = load_connectome(DATA)
    assert graph.stats == {"neurons": 1500, "connection_rows": 25206, "directed_pairs": 17186,
                           "synapses": 276399, "weak_components": 1}
    gf = {n.root_id for n in graph.neurons if n.role == "readout"}
    assert gf == {"720575940632499757", "720575940622838154"}
    assert graph.manifest["annotation_commit"] == "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0"
    assert graph.manifest["license"] == "CC-BY-NC-4.0"
    for neuron_type, expected in (("LC4", 104), ("LPLC2", 210)):
        sensory = {n.root_id for n in graph.neurons if neuron_type in (n.cell_type, n.hemibrain_type)}
        assert len(sensory) == expected
        assert all(any(s.pre_root_id in sensory and s.post_root_id == target for s in graph.synapses)
                   for target in gf)


def test_tampered_subset_is_rejected(tmp_path):
    shutil.copytree(DATA, tmp_path / "graph")
    with (tmp_path / "graph/connections.csv").open("a") as stream:
        stream.write("fabricated\n")
    with pytest.raises(ValueError, match="Integrity"):
        load_connectome(tmp_path / "graph")


def test_source_integrity_fails_closed(tmp_path):
    (tmp_path / "neurons.csv.gz").write_bytes(b"synthetic corrupt cache")
    with pytest.raises(ValueError, match="checksum"):
        fetch_sources(tmp_path, offline=True)


def test_missing_source_offline_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError, match="Missing pinned"):
        fetch_sources(tmp_path, offline=True)


def test_selection_retains_paths_and_deterministic_ties():
    # Explicitly SYNTHETIC topology; never exported as biological data.
    adjacency = {"1": {"3", "4", "5"}, "2": {"3"}, "3": {"1", "2"}, "4": {"1"}, "5": {"1"}}
    selected = choose_nodes({"1", "2"}, ["1", "2"], {"4": 100, "5": 100, "3": 1}, adjacency, 4)
    assert selected == {"1", "2", "3", "4"}
    with pytest.raises(ValueError, match="smaller"):
        choose_nodes({"1", "2"}, ["1", "2"], {}, adjacency, 2)
