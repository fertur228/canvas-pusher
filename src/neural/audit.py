"""Compare every extracted row/annotation with the pinned upstream cache."""
from collections import Counter
from pathlib import Path
import argparse
import csv
import gzip
import json

from .ingest import connection_rows, fetch_sources
from .loader import load_connectome


def audit_sources(directory: Path, cache: Path) -> dict:
    fetch_sources(cache, offline=True)
    graph = load_connectome(directory)
    ids = {n.root_id for n in graph.neurons}
    source_edges = Counter()
    for row in connection_rows(cache / "connections.csv.gz"):
        if row["pre_root_id"] in ids and row["post_root_id"] in ids:
            source_edges[(row["pre_root_id"], row["post_root_id"], row["neuropil"],
                          int(row["syn_count"]), row["nt_type"])] += 1
    extracted_edges = Counter((s.pre_root_id, s.post_root_id, s.neuropil, s.syn_count, s.nt_type)
                              for s in graph.synapses)
    if source_edges != extracted_edges:
        raise ValueError("Subset changed, omitted, or invented upstream connection rows")
    with gzip.open(cache / "neurons.csv.gz", "rt", newline="") as stream:
        catalog = {r["root_id"]: r for r in csv.DictReader(stream) if r["root_id"] in ids}
    with (cache / "annotations.tsv").open(newline="") as stream:
        annotations = {r["root_id"]: r for r in csv.DictReader(stream, delimiter="\t") if r["root_id"] in ids}
    if catalog.keys() != ids:
        raise ValueError("Subset contains a neuron absent from the source catalog")
    for neuron in graph.neurons:
        original = catalog[neuron.root_id]
        annotation = annotations.get(neuron.root_id, {})
        if (neuron.predicted_nt != original["nt_type"] or
                neuron.predicted_nt_confidence != original["nt_type_score"]):
            raise ValueError("Transmitter prediction changed")
        for field in ("cell_type", "hemibrain_type", "side", "known_nt", "known_nt_source"):
            if getattr(neuron, field) != annotation.get(field, ""):
                raise ValueError(f"Neuron annotation changed: {field}")
    return {"source_hashes_verified": True, "all_neuron_ids_verified": True,
            "all_annotations_verified": True, "induced_topology_exactly_preserved": True,
            "counts": graph.stats}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    parser.add_argument("--cache", type=Path, default=Path("data/neural/cache"))
    args = parser.parse_args()
    print(json.dumps(audit_sources(args.connectome, args.cache), sort_keys=True))


if __name__ == "__main__":
    main()
