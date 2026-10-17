from scripts.check_platform_reproducibility import compare


def test_platform_comparison_detects_real_changes_and_nonfinite_values():
    assert compare({'spikes':[1,2],'v':-52.0},{'spikes':[1,3],'v':-52.0})['discrete_mismatches']
    assert compare({'v':-52.0},{'v':-51.9})['max_absolute_difference']>1e-10
    assert compare({'v':-52.0},{'v':float('nan')})['discrete_mismatches']
    assert compare({'v':-52.0},{'v':-52.0+1e-12})['max_absolute_difference']<1e-10
