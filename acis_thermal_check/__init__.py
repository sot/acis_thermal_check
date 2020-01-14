import ska_helpers

__version__ = ska_helpers.get_version(__package__)

from acis_thermal_check.main import \
    ACISThermalCheck, \
    DPABoardTempCheck
from acis_thermal_check.utils import \
    calc_off_nom_rolls, get_options, \
    get_acis_limits, mylog


def test(*args, **kwargs):
    '''
    Run py.test unit tests.
    '''
    import testr
    return testr.test(*args, **kwargs)
