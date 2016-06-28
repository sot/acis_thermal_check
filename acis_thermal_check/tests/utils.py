import os
from acis_thermal_check.utils import TASK_DATA

test_data_dir = "/data/acis/thermal_model_tests"

def requires_file(req_file):
    def ffalse(func):
        return lambda: None
    def ftrue(func):
        return func
    if os.path.exists(os.path.join(test_data_dir,req_file)):
        return ftrue
    else:
        return ffalse

class TestOpts(object):
    def __init__(self, short_msid, run_start, outdir, oflsdir=None, 
                 days=21.0, ccd_count=6, fep_count=6, vid_board=1,
                 clocking=1,simpos=75616.0, pitch=150.0, T_init=None):
        self.run_start = run_start
        self.outdir = outdir
        self.oflsdir = oflsdir
        self.days = days
        self.ccd_count = ccd_count
        self.fep_count = fep_count
        self.vid_board = vid_board
        self.clocking = clocking
        self.simpos = simpos
        self.pitch = pitch
        setattr(self, "T_%s" % short_msid, T_init)
        self.traceback = True
        self.verbose = 1
        self.model_spec = os.path.join(TASK_DATA, 'model_spec',
                                       '%s_model_spec.json' % short_msid)
        self.version = None
