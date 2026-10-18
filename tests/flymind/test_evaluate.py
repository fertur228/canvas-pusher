from collections import Counter
from src.flymind.evaluate import shuffled_control
from src.neural.loader import load_connectome


def test_shuffle_is_reproducible_preserves_degrees_and_never_changes_source():
    graph=load_connectome('data/neural/flywire_v783')
    control,info=shuffled_control(graph)
    again,_=shuffled_control(graph)
    assert control==again and control.neurons==graph.neurons
    assert info['changed_rows']>1000 and control.manifest['biological_topology'] is False
    assert graph.manifest['kind']=='biological'
    assert Counter(e.syn_count for e in graph.synapses)==Counter(e.syn_count for e in control.synapses)
