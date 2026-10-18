"""Reproducible two-pass extraction; never downloads the full synapse table.

Run: python -m src.neural.ingest --help. Uses only public, pinned data, no tokens.
"""
from collections import defaultdict, deque
from dataclasses import asdict
from pathlib import Path
import argparse
import csv
import gzip
import json
import os
import urllib.request

from .loader import Connectome, sha256
from .models import Neuron, Synapse


ANNOTATION_COMMIT = "ebd66db2596fcc39c6950fb54ea3efa00f7fe8a0"
CODEX_COMMIT = "3477b6cfccaf3bf976e6af0d40513ad221311a36"
BASE_URL = "https://storage.googleapis.com/flywire-data/codex/data/fafb/783"
SOURCES = {
    "neurons.csv.gz": {
        "url": f"{BASE_URL}/neurons.csv.gz",
        "sha256": "6a6b3759e635f0f35a677d169052362131ec61d95f55919298b55c43fce4e719",
        "max_bytes": 10_000_000,
    },
    "connections.csv.gz": {
        "url": f"{BASE_URL}/connections.csv.gz",
        "sha256": "d49dd692e59e153aa3c83f5257bfc0eff51247b86d7bb183386c6d1622c70fc9",
        "max_bytes": 60_000_000,
    },
    "annotations.tsv": {
        "url": f"https://raw.githubusercontent.com/flyconnectome/flywire_annotations/{ANNOTATION_COMMIT}/supplemental_files/Supplemental_file1_neuron_annotations.tsv",
        "sha256": "30be6c73975a70c56d930e27911f36455d3886e15abf383b78edd2a5d679e0b6",
        "max_bytes": 60_000_000,
    },
}
SEED_TYPES = {"LC4", "LPLC2", "DNp01"}
EDGE_FIELDS = ["pre_root_id", "post_root_id", "neuropil", "syn_count", "nt_type"]


def fetch_sources(cache: Path, offline: bool = False):
    cache.mkdir(parents=True, exist_ok=True)
    for filename, source in SOURCES.items():
        path = cache / filename
        if path.exists():
            if sha256(path) != source["sha256"]:
                raise ValueError(f"Source checksum mismatch: {filename}; remove the corrupt cache explicitly")
            continue
        if offline:
            raise FileNotFoundError(f"Missing pinned source: {filename}")
        temporary = path.with_suffix(path.suffix + ".partial")
        try:
            request = urllib.request.Request(source["url"], headers={"User-Agent": "FlyMind-neural-poc/1"})
            with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
                count = 0
                while block := response.read(1024 * 1024):
                    count += len(block)
                    if count > source["max_bytes"]:
                        raise ValueError("Source exceeds bounded download size")
                    stream.write(block)
            if sha256(temporary) != source["sha256"]:
                raise ValueError(f"Upstream source changed: {filename}; inspect before updating pins")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()


def connection_rows(path: Path):
    with gzip.open(path, "rt", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != EDGE_FIELDS:
            raise ValueError("Unexpected source connection schema")
        yield from reader


def choose_nodes(core: set[str], gf: list[str], scores: dict, adjacency: dict, target: int):
    """Include real paths connecting all seeds, then strongest one-hop partners.

    Ties use numeric root IDs. This is weak connectivity, not bidirectional reachability.
    """
    parent = {gf[0]: None}
    todo = deque([gf[0]])
    while todo:
        node = todo.popleft()
        for neighbor in sorted(adjacency[node], key=int):
            if neighbor not in parent:
                parent[neighbor] = node
                todo.append(neighbor)
    if not core <= parent.keys():
        raise ValueError("Seed circuit is disconnected in the source neighborhood")
    selected = set()
    for seed in sorted(core, key=int):
        node = seed
        while node is not None and node not in selected:
            selected.add(node)
            node = parent[node]
    if len(selected) > target:
        raise ValueError("Target is smaller than the connected seed circuit")
    for node in sorted(scores, key=lambda n: (-scores[n], int(n))):
        if len(selected) == target:
            break
        # Each scored candidate has a measured edge to an included seed.
        if node not in selected and adjacency[node] & core:
            selected.add(node)
    if len(selected) != target:
        raise ValueError(f"Only {len(selected)} connected candidates; requested {target}")
    return selected


def extract(cache: Path, output: Path, target: int = 1500) -> Connectome:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Output must be absent or empty; existing data will not be overwritten")
    fetch_sources(cache, offline=True)
    with gzip.open(cache / "neurons.csv.gz", "rt", newline="") as stream:
        catalog = {row["root_id"]: row for row in csv.DictReader(stream)}
    with (cache / "annotations.tsv").open(newline="") as stream:
        annotations = {row["root_id"]: row for row in csv.DictReader(stream, delimiter="\t")}
    core = {rid for rid, row in annotations.items()
            if rid in catalog and {row["cell_type"], row["hemibrain_type"]} & SEED_TYPES}
    gf = sorted((rid for rid in core if "DNp01" in
                 (annotations[rid]["cell_type"], annotations[rid]["hemibrain_type"])), key=int)
    if len(gf) != 2:
        raise ValueError("Expected the two annotated Giant Fibers")
    scores = defaultdict(int)
    adjacency = defaultdict(set)
    source_row_count = 0
    for row in connection_rows(cache / "connections.csv.gz"):
        source_row_count += 1
        pre, post = row["pre_root_id"], row["post_root_id"]
        if pre in core or post in core:
            if pre not in catalog or post not in catalog:
                raise ValueError("Source connection references an unlisted neuron")
            weight = int(row["syn_count"])
            scores[pre] += weight
            scores[post] += weight
            adjacency[pre].add(post)
            adjacency[post].add(pre)
    selected = choose_nodes(core, gf, scores, adjacency, target)
    neurons = []
    for rid in sorted(selected, key=int):
        ann = annotations.get(rid, {})
        row = catalog[rid]
        kind = {ann.get("cell_type", ""), ann.get("hemibrain_type", "")}
        neurons.append(Neuron(
            root_id=rid, cell_type=ann.get("cell_type", ""),
            hemibrain_type=ann.get("hemibrain_type", ""), side=ann.get("side", ""),
            predicted_nt=row["nt_type"], predicted_nt_confidence=row["nt_type_score"],
            known_nt=ann.get("known_nt", ""), known_nt_source=ann.get("known_nt_source", ""),
            role="readout" if "DNp01" in kind else "stimulus" if kind & {"LC4", "LPLC2"} else "partner",
        ))
    edges = []
    for row in connection_rows(cache / "connections.csv.gz"):
        if row["pre_root_id"] in selected and row["post_root_id"] in selected:
            edges.append(Synapse(**{**row, "syn_count": int(row["syn_count"])}))
    edges.sort(key=lambda e: (int(e.pre_root_id), int(e.post_root_id), e.neuropil, e.nt_type))
    graph = Connectome(tuple(neurons), tuple(edges), {}).validate()
    if len(graph.components()) != 1:
        raise ValueError("Extracted network is disconnected")
    output.mkdir(parents=True, exist_ok=True)
    for name, records in (("neurons.csv", neurons), ("connections.csv", edges)):
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(asdict(records[0])))
            writer.writeheader()
            writer.writerows(asdict(record) for record in records)
    manifest = {
        "schema_version": 1, "kind": "biological", "dataset": "FlyWire FAFB", "version": "783",
        "organism": "adult female Drosophila melanogaster",
        "license": "CC-BY-NC-4.0", "license_url": "https://join.flywire.ai/guidelines",
        "sources": SOURCES, "annotation_version": "2.1.0", "annotation_commit": ANNOTATION_COMMIT,
        "source_discovery": f"https://github.com/murthylab/codex/blob/{CODEX_COMMIT}/codex/data/local_data_loader.py",
        "connectivity_reference": "https://doi.org/10.5281/zenodo.10676866",
        "citations": ["https://doi.org/10.1038/s41586-024-07558-y", "https://doi.org/10.1038/s41586-024-07686-5", "https://doi.org/10.1016/j.cub.2019.01.079"],
        "source_connection_rows": source_row_count,
        "selection": {
            "algorithm": "all LC4/LPLC2/DNp01 seeds; BFS paths in seed-incident graph; remaining partners ranked by incident synapse sum; numeric ID ties",
            "seed_types": sorted(SEED_TYPES), "seed_count": len(core), "target_neurons": target,
            "require_weakly_connected": True, "edge_policy": "all source rows induced by selected IDs, unchanged",
            "added_synapse_threshold": None,
        },
        "counts": graph.stats,
        "files": {name: {"sha256": sha256(output / name)} for name in ("neurons.csv", "connections.csv")},
        "limitations": [
            "Codex source is already thresholded; this is not the full synapse-level connectome.",
            "No missing edges reconstructed; all source rows within selected neurons retained.",
            "Neurotransmitter labels/confidence are predictions unless known_nt_source is given.",
            "FAFB contains brain, not the downstream ventral nerve cord/muscles; no escape behavior readout.",
            "Electrical synapses and receptor identities are not provided.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return Connectome(graph.neurons, graph.synapses, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/neural/cache"))
    parser.add_argument("--output", type=Path, default=Path("data/neural/flywire_v783"))
    parser.add_argument("--neurons", type=int, default=1500)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    fetch_sources(args.cache, args.offline)
    graph = extract(args.cache, args.output, args.neurons)
    print(json.dumps(graph.stats, sort_keys=True))


if __name__ == "__main__":
    main()
