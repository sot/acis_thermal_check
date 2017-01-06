__version__ = "1.1.0"

from acis_thermal_check.main import \
    ACISThermalCheck
from acis_thermal_check.utils import \
    calc_off_nom_rolls, get_options

from acis_thermal_check.dea_check import dea_check
from acis_thermal_check.dpa_check import dpa_check
from acis_thermal_check.psmc_check import psmc_check


def test(*args, **kwargs):
    '''
    Run py.test unit tests.
    '''
    import testr
    return testr.test(*args, **kwargs)
