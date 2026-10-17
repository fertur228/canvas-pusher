# Neural model and product interpretation

The unchanged source is adult female Drosophila FlyWire FAFB v783, 1,500 genuine
root IDs, 25,206 edge rows and 276,399 measured synaptic contacts. Dataset and
annotation citations/hashes/license are in data/neural/flywire_v783/manifest.json.
Detailed investigation: [escape validation](neural-escape-validation.md).

The fixed generic LIF model uses dv/dt=(Vrest−v+g+drive)/20ms and dg/dt=−g/5ms,
rest/reset −52 mV, threshold −45 mV, refractory 2.2 ms, synaptic delay 1.8 ms,
contact increment 0.275 mV into g, dt 0.1 ms. The increment is a free model parameter,
not measured instantaneous EPSP. Presynaptic Shiu transmitter interpretation and
cell-type annotations are model assumptions, not measured receptor signs.

LC4/LPLC2 receive the existing looming feature proxy; GF never receives direct
stimulation. Encoder canvas-looming/v1 chooses weak (contrast .35, r/v80ms) or
strong (contrast1,r/v20ms). Unsubmitted deadlines <=24h and failing grade updates
select strong. Academic semantics begin in this engineered encoder, not in the
fly. Neural computation begins at sensory current drive through the actual graph.
Readout experimental-urgency/v1 is engineering-defined: elevated requires GF total
>=6 and >=400 active cells; moderate requires GF>=1 or >=100 active cells.
Readout does not suppress or delay mandatory notifications.

Normal references: baseline 0 spikes; weak 344 spikes/282 active/GF2,2; strong
834/418/GF3,4. All original source bytes and model files are preserved. Anatomical
soma coordinates are available for 1497/1500 cells; graph layout is explicitly
non-anatomical. No bundled neurite morphology, no VNC/muscles/behavior.

`python -m src.flymind.evaluate --output /tmp/new-evaluation.json` executes fresh
process repeats, zero-transmission controls, three directed edge-swap null models
and stimulus sensitivity controls. Shuffling preserves each neuron's incoming and
outgoing row degree/contact sums, edge weight distribution, neuropil/NT strata;
it intentionally destroys biological partner identity. The original graph is
never overwritten. These are synthetic controls, not invented biological data.

Product evaluation uses 22 explicitly synthetic deadline/completion scenarios and
an engineered <=3h critical rule. Two false elevated signals and no missed critical
signals appeared versus that rule; it is not independent human ground truth.
Strong real GF3/4 versus shuffled2/3,3/2,2/3 changes the neural classification;
zero transmission GF0/0 demonstrates synaptic causality. Weak-fast gives no spikes;
strong-slow GF9/13 shows stimulus duration matters. Deterministic repeats match.
No measurable prioritization advantage over the deterministic baseline is established.
Keep operational urgency rule-based and neural output as experimental enrichment.

Generic physiology, uncalibrated recruitment/gain and partial GF input coverage
(80.49%/82.82%) remain limitations. LC4-only stimulation still activates GF, so the
published LPLC2-dependence is not reproduced under a matched protocol.
`biological_response_validated=false` remains mandatory everywhere.

## Native-platform reproducibility

The first Ubuntu x86 CI correctly exposed an invalid test assumption: the full
float64 result SHA does not necessarily match the historical ARM SHA. A dedicated
probe measured maximum differences2.50e-12 (weak) and3.64e-12 (strong), exact spike
trains and no discrete mismatches; two fresh native runs had identical hashes.
See neural-platform-comparison-linux-x86_64.json. Regression now requires exact
parameters/spikes/discrete structure, all numerical fields within absolute1e-10,
and exact full-result hashes across fresh runs on the same platform. No model
parameters, original exports or stored hashes were changed to pass this check.
