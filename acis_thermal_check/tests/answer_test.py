from acis_thermal_check import dea_check, \
    dpa_check, psmc_check
import pickle
import os
from numpy.testing import assert_array_equal
from acis_thermal_check.utils import TASK_DATA

test_data_dir = "/data/acis/thermal_model_tests"

def compare_results(short_msid, out_dir):
    new_answer_file = os.path.join(out_dir, "validation_data.pkl")
    new_results = pickle.load(open(new_answer_file, "rb"))
    old_answer_file = os.path.join(test_data_dir, 
                               short_msid+"_results.pkl")
    old_results = pickle.load(open(old_answer_file, "rb"))
    new_pred = new_results["pred"]
    old_pred = old_results["pred"]
    for k in new_pred:
        assert_array_equal(new_pred[k], old_pred[k])
    assert_array_equal(new_results["tlm"], old_results["tlm"])
 
class TestOpts(object):
    def __init__(self, short_msid, run_start, outdir, days=21.0, 
                 ccd_count=6, fep_count=6, vid_board=1, clocking=1,
                 simpos=75616.0, pitch=150.0, T_init=None):
        self.run_start = run_start
        self.outdir = outdir
        self.days = days
        self.ccd_count = ccd_count
        self.fep_count = fep_count
        self.vid_board = vid_board
        self.clocking = clocking
        self.simpos = simpos
        self.pitch = pitch
        setattr(self, "T_%s" % short_msid, T_init)
        self.oflsdir = None
        self.traceback = True
        self.verbose = 1
        self.model_spec = os.path.join(TASK_DATA, 'model_spec',
                                       '%s_model_spec.json' % short_msid)
        self.version = None

def test_dea_check(generate_answers):
    short_msid = "dea" 
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    dea_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)

def test_dpa_check(generate_answers):
    short_msid = "dpa"
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    dpa_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)

def test_psmc_check(generate_answers):
    short_msid = "psmc"
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    psmc_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)
