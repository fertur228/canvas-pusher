import gzip
import json
import pytest
from src.neural.experiment import export_run
from src.neural.models import Parameters
from .test_loader import DATA


def test_offline_export_schema_and_string_ids(tmp_path, monkeypatch):
    import urllib.request
    def forbidden(*_, **__):
        raise AssertionError("The simulation must be offline")
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    output = tmp_path / "control.json.gz"
    summary = export_run(DATA, output, Parameters(), control=True)
    with gzip.open(output, "rt") as stream:
        telemetry = json.load(stream)
    assert telemetry["biological_response_validated"] is False
    assert telemetry["schema_version"] == 1
    assert all(isinstance(rid, str) for rid in telemetry["neuron_ids"])
    assert telemetry["simulation"]["spikes"] == []
    assert summary["active_neurons"] == 0
    assert summary["measurements"]["cpu_seconds_load_import_simulation_export"] > 0
    assert json.loads((tmp_path / "control.json.gz.summary.json").read_text()) == summary
    with pytest.raises(FileExistsError):
        export_run(DATA, output, Parameters(), control=True)
