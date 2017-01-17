import pickle
import os
from numpy.testing import assert_array_equal, \
    assert_allclose
import shutil
import numpy as np
from scipy import misc

test_data_dir = "/data/acis/thermal_model_tests"

class TestOpts(object):
    def __init__(self, short_msid, run_start, outdir, model_spec=None,
                 oflsdir=None, days=21.0, ccd_count=6, fep_count=6,
                 vid_board=1, clocking=1, simpos=75616.0, pitch=150.0,
                 T_init=None, dh_heater=0, cmd_states_db='sybase'):
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
        self.cmd_states_db = cmd_states_db
        setattr(self, "T_%s" % short_msid, T_init)
        self.dh_heater = dh_heater
        self.traceback = True
        self.verbose = 1
        self.model_spec = model_spec
        self.version = None

def run_model(short_msid, msid_check, model_spec, run_start, oflsdir, cmd_states_db):
    out_dir = short_msid+"_test"
    msid_opts = TestOpts(short_msid, run_start, out_dir, model_spec=model_spec,
                         oflsdir=oflsdir, cmd_states_db=cmd_states_db)
    msid_check.driver(msid_opts)
    return out_dir

data_dtype = {'temperatures': {'names': ('time', 'date', 'temperature'),
                               'formats': ('f8', 'S21', 'f8')
                              },
              'states': {'names': ('ccd_count', 'clocking', 'datestart',
                                   'datestop', 'dec', 'dither', 'fep_count', 
                                   'hetg', 'letg', 'obsid', 'pcad_mode', 
                                   'pitch', 'power_cmd', 'q1', 'q2', 'q3', 
                                   'q4', 'ra', 'roll', 'si_mode', 'simfa_pos',
                                   'simpos', 'trans_keys'),
                         'formats': ('i4', 'i4', 'S21', 'S21', 'f8', 'S4',
                                     'i4', 'S4', 'S4', 'i4', 'S4', 'f8',
                                     'S9', 'f8', 'f8', 'f8', 'f8', 'f8',
                                     'f8', 'S8', 'i4', 'i4', 'S80')
                        }
             }

def compare_data_files(prefix, short_msid, oflsdir, out_dir):
    fn = prefix+".dat"
    new_fn = os.path.join(out_dir, fn)
    old_fn = os.path.join(test_data_dir, short_msid, oflsdir, fn)
    new_data = np.loadtxt(new_fn, skiprows=1, dtype=data_dtype[prefix])
    old_data = np.loadtxt(old_fn, skiprows=1, dtype=data_dtype[prefix])
    for k, dt in new_data.dtype.descr:
        if 'f' in dt:
            assert_allclose(new_data[k], old_data[k])
        else:
            assert_array_equal(new_data[k], old_data[k])

def compare_results(short_msid, oflsdir, out_dir):
    new_answer_file = os.path.join(out_dir, "validation_data.pkl")
    new_results = pickle.load(open(new_answer_file, "rb"))
    old_answer_file = os.path.join(test_data_dir, short_msid,
                                   "validation_data.pkl")
    old_results = pickle.load(open(old_answer_file, "rb"))
    new_pred = new_results["pred"]
    old_pred = old_results["pred"]
    for k in new_pred:
        assert_array_equal(new_pred[k], old_pred[k])
    new_tlm = new_results['tlm']
    old_tlm = old_results['tlm']
    for k in new_tlm.dtype.names:
        assert_array_equal(new_tlm[k], old_tlm[k])
    for prefix in ("temperatures", "states"):
        compare_data_files(prefix, short_msid, oflsdir, out_dir)

def copy_new_results(short_msid, out_dir, answer_dir):
    for fn in ('validation_data.pkl', 'states.dat', 'temperatures.dat'):
        fromfile = os.path.join(out_dir, fn)
        adir = os.path.join(answer_dir, short_msid)
        if not os.path.exists(adir):
            os.mkdir(adir)
        tofile = os.path.join(adir, fn)
        shutil.copyfile(fromfile, tofile)

def run_answer_test(short_msid, oflsdir, out_dir, answer_dir):
    out_dir = os.path.abspath(out_dir)
    if not answer_dir:
        compare_results(short_msid, oflsdir, out_dir)
    else:
        copy_new_results(short_msid, out_dir, answer_dir)

def build_image_list(msid):
    images = ["%s.png" % msid, "pow_sim.png"]
    for prefix in (msid, "pitch", "roll", "tscpos"):
        images += ["%s_valid.png" % prefix, 
                   "%s_valid_hist_lin.png" % prefix,
                   "%s_valid_hist_log.png" % prefix]
    return images

def compare_images(msid, short_msid, oflsdir, out_dir):
    images = build_image_list(msid)
    for image in images:
        new_image = misc.imread(os.path.join(out_dir, image))
        old_image = misc.imread(os.path.join(test_data_dir, short_msid, oflsdir, image))
        assert_array_equal(new_image, old_image)

def copy_new_images(msid, short_msid, out_dir, answer_dir):
    images = build_image_list(msid)
    for image in images:
        fromfile = os.path.join(out_dir, image)
        adir = os.path.join(answer_dir, short_msid)
        if not os.path.exists(adir):
            os.mkdir(adir)
        tofile = os.path.join(adir, image)
        shutil.copyfile(fromfile, tofile)

def run_image_test(msid, short_msid, oflsdir, out_dir, answer_dir):
    out_dir = os.path.abspath(out_dir)
    if not answer_dir:
        compare_images(msid, short_msid, oflsdir, out_dir)
    else:
        copy_new_images(msid, short_msid, out_dir, answer_dir)
