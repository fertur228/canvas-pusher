"""Directed escape-circuit paths and omitted boundary inputs, from pinned real data."""
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
import argparse
import csv
import gzip
import json

from .ingest import SOURCES, connection_rows, fetch_sources, EDGE_FIELDS
from .loader import Connectome, load_connectome, sha256
from .models import Neuron, Synapse, effective_sign, effective_transmitter


def cell_kind(neuron: Neuron) -> str:
    return neuron.cell_type or neuron.hemibrain_type or "untyped"


def incoming_summary(edges, retained_ids):
    return {"synapses": sum(e.syn_count for e in edges), "connection_rows": len(edges),
            "presynaptic_neurons": len({e.pre_root_id for e in edges}),
            "retained_synapses": sum(e.syn_count for e in edges if e.pre_root_id in retained_ids),
            "omitted_synapses": sum(e.syn_count for e in edges if e.pre_root_id not in retained_ids),
            "omitted_presynaptic_neurons": len({e.pre_root_id for e in edges if e.pre_root_id not in retained_ids}),
            "raw_nt_synapses": dict(sorted(Counter({nt: sum(e.syn_count for e in edges if e.nt_type == nt)
                                                    for nt in {e.nt_type for e in edges}}).items()))}


def analyze(graph: Connectome, cache: Path) -> dict:
    fetch_sources(cache, offline=True)
    ids = {n.root_id for n in graph.neurons}
    sensory = {n.root_id for n in graph.neurons if cell_kind(n) in {"LC4", "LPLC2"}}
    gf_ids = sorted((n.root_id for n in graph.neurons if n.role == "readout"), key=int)
    incoming_gf = defaultdict(list)
    outgoing_sensory = defaultdict(list)
    incoming_sensory = []
    for row in connection_rows(cache / "connections.csv.gz"):
        pre, post = row["pre_root_id"], row["post_root_id"]
        if pre in sensory or post in sensory or post in gf_ids:
            edge = Synapse(**{**row, "syn_count": int(row["syn_count"])})
            if post in gf_ids:
                incoming_gf[post].append(edge)
            if pre in sensory:
                outgoing_sensory[post].append(edge)
            if post in sensory:
                incoming_sensory.append(edge)
    relevant = ids | {e.pre_root_id for es in incoming_gf.values() for e in es}
    with gzip.open(cache / "neurons.csv.gz", "rt", newline="") as stream:
        catalog = {r["root_id"]: r for r in csv.DictReader(stream) if r["root_id"] in relevant}
    with (cache / "annotations.tsv").open(newline="") as stream:
        annotations = {r["root_id"]: r for r in csv.DictReader(stream, delimiter="\t") if r["root_id"] in relevant}
    cells = {n.root_id: n for n in graph.neurons}
    for rid in relevant - ids:
        a, c = annotations.get(rid, {}), catalog[rid]
        cells[rid] = Neuron(rid, cell_type=a.get("cell_type", ""), hemibrain_type=a.get("hemibrain_type", ""),
                            side=a.get("side", ""), predicted_nt=c["nt_type"], predicted_nt_confidence=c["nt_type_score"],
                            known_nt=a.get("known_nt", ""), known_nt_source=a.get("known_nt_source", ""))

    def aggregate(edges):
        pairs = defaultdict(list)
        for edge in edges:
            pairs[(edge.pre_root_id, edge.post_root_id)].append(edge)
        return pairs

    def descriptor(rid):
        return {"root_id": rid, "type": cell_kind(cells[rid]), "side": cells[rid].side,
                "in_original_subset": rid in ids}

    def edge_descriptor(edges):
        pre, post = edges[0].pre_root_id, edges[0].post_root_id
        return {"pre_root_id": pre, "post_root_id": post, "synapses": sum(e.syn_count for e in edges),
                "raw_nt_counts": {nt: sum(e.syn_count for e in edges if e.nt_type == nt) for nt in sorted({e.nt_type for e in edges})},
                "effective_signs": {p: sorted({effective_sign(cells[pre], e, p) for e in edges})
                                    for p in ("edge_prediction", "presynaptic_conservative", "presynaptic_shiu")}}

    targets = []
    for gf in gf_ids:
        pairs = aggregate(incoming_gf[gf])
        direct = defaultdict(list)
        two_hop = defaultdict(list)
        for (pre, _), edges in pairs.items():
            if pre in sensory:
                direct[cell_kind(cells[pre])].append({"nodes": [descriptor(pre), descriptor(gf)],
                                                     "edges": [edge_descriptor(edges)]})
            if pre in gf_ids:
                continue
            for (start, _), first in aggregate(outgoing_sensory[pre]).items():
                if start == pre:
                    continue
                two_hop[cell_kind(cells[start])].append({"nodes": [descriptor(start), descriptor(pre), descriptor(gf)],
                                                        "edges": [edge_descriptor(first), edge_descriptor(edges)],
                                                        "count_product_for_ranking_only": sum(e.syn_count for e in first) * sum(e.syn_count for e in edges)})
        type_stats = {}
        for typ in ("LC4", "LPLC2"):
            raw = [e for e in incoming_gf[gf] if e.pre_root_id in sensory and cell_kind(cells[e.pre_root_id]) == typ]
            type_stats[typ] = {"synapses": sum(e.syn_count for e in raw),
                               "raw_ach_synapses": sum(e.syn_count for e in raw if e.nt_type == "ACH"),
                               "presynaptic_neurons": len({e.pre_root_id for e in raw}),
                               "all_direct_edges_retained": all(e.pre_root_id in ids for e in raw),
                               "legacy_single_coincident_burst_mv": sum(e.syn_count * 0.02 * effective_sign(cells[e.pre_root_id], e, "edge_prediction") for e in raw),
                               "cell_annotation_single_coincident_burst_mv": sum(e.syn_count * 0.02 * effective_sign(cells[e.pre_root_id], e, "presynaptic_conservative") for e in raw)}
        excluded = []
        for (pre, _), edges in pairs.items():
            if pre not in ids:
                excluded.append({**descriptor(pre), "synapses_to_gf": sum(e.syn_count for e in edges),
                                 "known_nt": cells[pre].known_nt, "known_nt_source": cells[pre].known_nt_source,
                                 "predicted_nt": cells[pre].predicted_nt})
        summary = incoming_summary(incoming_gf[gf], ids)
        summary["retained_fraction"] = summary["retained_synapses"] / summary["synapses"]
        targets.append({**descriptor(gf), "incoming_boundary": summary, "direct_type_inputs": type_stats,
                        "direct_paths": {typ: sorted(paths, key=lambda p: (-p["edges"][0]["synapses"], int(p["nodes"][0]["root_id"]))) for typ, paths in direct.items()},
                        "two_hop_path_counts": {typ: {"full_source": len(paths),
                            "within_subset": sum(all(n["in_original_subset"] for n in p["nodes"]) for p in paths)} for typ, paths in two_hop.items()},
                        "top_two_hop_paths": {typ: sorted(paths, key=lambda p: (-p["count_product_for_ranking_only"], tuple(int(n["root_id"]) for n in p["nodes"])))[:8] for typ, paths in two_hop.items()},
                        "omitted_gf_predecessors": sorted(excluded, key=lambda n: (-n["synapses_to_gf"], int(n["root_id"])))})
    seed_coverage = {}
    for typ in ("LC4", "LPLC2"):
        edges = [e for e in incoming_sensory if cell_kind(cells[e.post_root_id]) == typ]
        summary = incoming_summary(edges, ids)
        summary["retained_fraction"] = summary["retained_synapses"] / summary["synapses"]
        seed_coverage[typ] = summary
    return {"schema_version": 1, "dataset_files": graph.manifest["files"],
            "dataset_counts": graph.stats, "sources": SOURCES, "giant_fibers": targets,
            "sensory_input_boundary": seed_coverage,
            "interpretation": "Directed structural paths, not validated functional pathways. Path count products are ranking scores, not probabilities or synaptic efficacy."}


def expand_gf_boundary(graph: Connectome, cache: Path, output: Path) -> Connectome:
    """Diagnostic graph adds EVERY direct GF predecessor; leaves original graph intact."""
    if output.exists():
        raise FileExistsError("Choose a new expansion directory")
    report = analyze(graph, cache)
    ids = {n.root_id for n in graph.neurons}
    ids.update(n["root_id"] for gf in report["giant_fibers"] for n in gf["omitted_gf_predecessors"])
    with gzip.open(cache / "neurons.csv.gz", "rt", newline="") as stream:
        catalog = {r["root_id"]: r for r in csv.DictReader(stream) if r["root_id"] in ids}
    with (cache / "annotations.tsv").open(newline="") as stream:
        annotations = {r["root_id"]: r for r in csv.DictReader(stream, delimiter="\t") if r["root_id"] in ids}
    cells = {n.root_id: n for n in graph.neurons}
    for rid in ids - cells.keys():
        a, c = annotations.get(rid, {}), catalog[rid]
        cells[rid] = Neuron(rid, cell_type=a.get("cell_type", ""), hemibrain_type=a.get("hemibrain_type", ""),
                            side=a.get("side", ""), predicted_nt=c["nt_type"], predicted_nt_confidence=c["nt_type_score"],
                            known_nt=a.get("known_nt", ""), known_nt_source=a.get("known_nt_source", ""))
    edges = [Synapse(**{**r, "syn_count": int(r["syn_count"])}) for r in connection_rows(cache / "connections.csv.gz")
             if r["pre_root_id"] in ids and r["post_root_id"] in ids]
    edges.sort(key=lambda s: (int(s.pre_root_id), int(s.post_root_id), s.neuropil, s.nt_type))
    expanded = Connectome(tuple(cells[rid] for rid in sorted(ids, key=int)), tuple(edges), {}).validate()
    if len(expanded.components()) != 1:
        raise ValueError("Expanded graph unexpectedly disconnected")
    output.mkdir(parents=True)
    for name, records in (("neurons.csv", expanded.neurons), ("connections.csv", expanded.synapses)):
        with (output / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(asdict(records[0])))
            writer.writeheader()
            writer.writerows(asdict(r) for r in records)
    manifest = {**graph.manifest, "counts": expanded.stats,
                "selection": {"algorithm": "original 1500-neuron graph union all source direct GF predecessors; all induced source rows unchanged",
                              "require_weakly_connected": True, "target_neurons": len(ids),
                              "parent_files": graph.manifest["files"], "added_synapse_threshold": None},
                "files": {name: {"sha256": sha256(output / name)} for name in ("neurons.csv", "connections.csv")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return load_connectome(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connectome", type=Path, default=Path("data/neural/flywire_v783"))
    parser.add_argument("--cache", type=Path, default=Path("data/neural/cache"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expand-output", type=Path)
    args = parser.parse_args()
    graph = load_connectome(args.connectome)
    report = analyze(graph, args.cache)
    if args.expand_output:
        report["expanded_graph"] = expand_gf_boundary(graph, args.cache, args.expand_output).stats
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"counts": graph.stats, "output": str(args.output), "expanded_graph": report.get("expanded_graph")}, sort_keys=True))


if __name__ == "__main__":
    main()
