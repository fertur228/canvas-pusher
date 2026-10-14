"""ALL in-memory fixtures are synthetic, not biological data."""
import pytest
from src.neural.loader import Connectome
from src.neural.models import Neuron, Synapse


@pytest.fixture
def synthetic_graph():
    return Connectome(
        (Neuron("1", role="stimulus"), Neuron("2", role="readout"), Neuron("3")),
        (Synapse("1", "2", "SYNTHETIC", 100, "ACH"),
         Synapse("1", "3", "SYNTHETIC", 100, "GABA")),
        {"schema_version": 1, "kind": "synthetic_test_fixture"},
    ).validate()
