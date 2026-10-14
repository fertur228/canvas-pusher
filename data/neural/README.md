# Scientific data provenance

The `flywire_v783` CSVs are the original adult female Drosophila FlyWire FAFB v783
extraction: 1,500 genuine string root IDs, 25,206 neuron/neuropil edge rows and
276,399 synaptic contacts. Source URLs, SHA-256 checksums, release/annotation
versions and citations are in `flywire_v783/manifest.json`.

FlyWire/FlyBase-derived source material is distributed under **CC BY-NC 4.0** as
recorded in that manifest: https://creativecommons.org/licenses/by-nc/4.0/ .
Retain attribution and the non-commercial restriction. This repository makes no
claim to sublicense biological datasets for commercial use.

`runs/escape-resumed-20261014/{baseline,weak,strong}-1.json.gz` are unchanged
scientific model recordings included as compact, reproducible test/replay
references. They contain neuron activity, no Canvas/student information.
`escape-suite.json` is the historical summary, including references to additional
locally generated files that are intentionally not bundled. Full upstream caches
and other generated runs remain ignored.

Dashboard derivatives preserve every measured edge, neuron ID and recorded
sample. Recorded activity is from an experimental fixed LIF model; it is not
physiological measurement or validated behavior. Shuffled experimental controls
are separately labeled in evaluation reports and never overwrite these files.
