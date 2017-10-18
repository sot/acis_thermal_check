__version__ = "2.0-dev"

from acis_thermal_check.main import \
    ACISThermalCheck
from acis_thermal_check.state_builder import \
    LegacyStateBuilder, ACISStateBuilder, \
    HDF5StateBuilder, state_builders
from acis_thermal_check.utils import \
    calc_off_nom_rolls, get_options, \
    get_acis_limits

def test(*args, **kwargs):
    '''
    Run py.test unit tests.
    '''
    import testr
    return testr.test(*args, **kwargs)
