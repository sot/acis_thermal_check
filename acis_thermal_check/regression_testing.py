import pickle
import os
from numpy.testing import assert_array_equal, \
    assert_allclose
import shutil
import numpy as np
from scipy import misc

# This directory is currently where the thermal model
# "gold standard" answers live.
test_data_dir = "/data/acis/thermal_model_tests"

# Loads for regression testing
test_loads = [
# normal loads
         "MAR0617A", "MAR2017E", "JUL3117B", "SEP0417A",
# TOOs
         "MAR1517B", "JUL2717A", "AUG2517C", "AUG3017A",
# STOPs
         "MAR0817B", "MAR1117A", "APR0217B", "SEP0917C"
]

class TestOpts(object):
    """
    A mock-up of a command-line parser object to be used with
    ACISThermalCheck testing.

    Parameters
    ----------
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    run_start : string
        The run start time in YYYY:DOY:HH:MM:SS.SSS format.
    outdir : string
        The path to the output directory.
    model_spec : string, optional
        The path to the model specification JSON file. If not provided,
        the default one will be used.
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    days : float, optional
        The number of days to run the model for. Default: 21.0
    T_init : float, optional
        The starting temperature for the run. If not set, it will be
        determined from telemetry.
    cmd_states_db : string
        The mode of database access for the commanded states database.
        "sybase" or "sqlite". Default: "sybase"
    """
    def __init__(self, name, run_start, outdir, model_spec=None,
                 load_week=None, days=21.0, T_init=None, 
                 cmd_states_db='sybase'):
        self.load_week = load_week
        self.run_start = run_start
        self.outdir = outdir
        # load_week sets the bsdir
        if load_week is None:
            self.bsdir = None
        else:
            load_year = "20%s" % load_week[-2:]
            self.bsdir = "/data/acis/LoadReviews/%s/%s/ofls" % (load_year, load_week)
        self.days = days
        self.cmd_states_db = cmd_states_db
        setattr(self, "T_%s" % name, T_init)
        self.traceback = True
        self.verbose = 1
        self.model_spec = model_spec
        self.version = None

def run_model(name, msid_check, model_spec, run_start, load_week, cmd_states_db):
    """
    Function to run a thermal model for a test.

    Parameters
    ----------
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    msid_check : :class:`~acis_thermal_check.main.ACISThermalCheck` instance
        The ACISThermalCheck instance supplied by the specific thermal
        model to be used in the test run.
    model_spec : string, optional
        The path to the model specification JSON file. If not provided,
        the default one will be used.
    run_start : string
        The run start time in YYYY:DOY:HH:MM:SS.SSS format.
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    cmd_states_db : string
        The mode of database access for the commanded states database.
        "sybase" or "sqlite". Default: "sybase"
    """
    out_dir = name+"_test"
    msid_opts = TestOpts(name, run_start, out_dir, model_spec=model_spec,
                         load_week=load_week, cmd_states_db=cmd_states_db)
    msid_check.driver(msid_opts)
    return out_dir

# Large, multi-layer dictionary which encodes the datatypes for the
# different quantities that are being checked against.
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

def compare_data_files(prefix, name, load_week, out_dir):
    """
    This function compares the "gold standard" data with the current
    test run's data for the .dat files produced in the thermal model
    run. Called by ``compare_results``.

    Parameters
    ----------
    prefix : string
        The prefix of the file, "temperatures" or "states".
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    out_dir : string
        The path to the output directory.
    """
    fn = prefix+".dat"
    new_fn = os.path.join(out_dir, fn)
    old_fn = os.path.join(test_data_dir, name, load_week, fn)
    new_data = np.loadtxt(new_fn, skiprows=1, dtype=data_dtype[prefix])
    old_data = np.loadtxt(old_fn, skiprows=1, dtype=data_dtype[prefix])
    # Compare test run data to gold standard. Since we're loading from
    # ASCII text files here, floating-point comparisons will be different
    # at machine precision, others will be exact.
    for k, dt in new_data.dtype.descr:
        if 'f' in dt:
            assert_allclose(new_data[k], old_data[k])
        else:
            assert_array_equal(new_data[k], old_data[k])

def compare_results(name, load_week, out_dir):
    """
    This function compares the "gold standard" data with the current
    test run's data.

    Parameters
    ----------
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    out_dir : string
        The path to the output directory.
    """
    # First load the answers from the pickle files, both gold standard
    # and current
    new_answer_file = os.path.join(out_dir, "validation_data.pkl")
    new_results = pickle.load(open(new_answer_file, "rb"))
    old_answer_file = os.path.join(test_data_dir, name, load_week,
                                   "validation_data.pkl")
    old_results = pickle.load(open(old_answer_file, "rb"))
    # Compare predictions
    new_pred = new_results["pred"]
    old_pred = old_results["pred"]
    pred_keys = set(list(new_pred.keys())+list(old_pred.keys()))
    for k in pred_keys:
        if k not in new_pred:
            print("WARNING : '%s' in old answer but not new. Answers should be updated." % k)
            continue
        if k not in old_pred:
            print("WARNING : '%s' in new answer but not old. Answers should be updated." % k)
            continue
        assert_array_equal(new_pred[k], old_pred[k])
    # Compare telemetry
    new_tlm = new_results['tlm']
    old_tlm = old_results['tlm']
    tlm_keys = set(list(new_tlm.dtype.names)+list(old_tlm.dtype.names))
    for k in tlm_keys:
        if k not in new_pred:
            print("WARNING : '%s' in old answer but not new. Answers should be updated." % k)
            continue
        if k not in old_pred:
            print("WARNING : '%s' in new answer but not old. Answers should be updated." % k)
            continue
        assert_array_equal(new_tlm[k], old_tlm[k])
    # Compare
    for prefix in ("temperatures", "states"):
        compare_data_files(prefix, name, load_week, out_dir)

def copy_new_results(name, out_dir, answer_dir):
    """
    This function copies the pickle files and the .dat files
    generated in this test run to a directory specified by the
    user, typically for inspection and for possible updating of
    the "gold standard" answers.

    Parameters
    ----------
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    out_dir : string
        The path to the output directory.
    answer_dir : string
        The path to the directory to which to copy the files.
    """
    for fn in ('validation_data.pkl', 'states.dat', 'temperatures.dat'):
        fromfile = os.path.join(out_dir, fn)
        adir = os.path.join(answer_dir, name)
        if not os.path.exists(adir):
            os.mkdir(adir)
        tofile = os.path.join(adir, fn)
        shutil.copyfile(fromfile, tofile)

def run_answer_test(name, load_week, out_dir, answer_dir):
    """
    This function runs the answer test in one of two modes:
    either comparing the answers from this test to the "gold
    standard" answers or to simply run the model to generate
    answers.

    Parameters
    ----------
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    out_dir : string
        The path to the output directory.
    answer_dir : string
        The path to the directory to which to copy the files. Is None
        if this is a test run, is an actual directory if we are simply
        generating answers.
    """
    out_dir = os.path.abspath(out_dir)
    if not answer_dir:
        compare_results(name, load_week, out_dir)
    else:
        copy_new_results(name, out_dir, answer_dir)

def build_image_list(msid):
    """
    A simple function to build the list of images that will
    be compared for a particular ``msid``.
    """
    images = ["%s.png" % msid, "pow_sim.png"]
    for prefix in (msid, "pitch", "roll", "tscpos"):
        images += ["%s_valid.png" % prefix, 
                   "%s_valid_hist_lin.png" % prefix,
                   "%s_valid_hist_log.png" % prefix]
    return images

def compare_images(msid, name, load_week, out_dir):
    """
    This function compares two images using SciPy's
    ``imread`` function to convert images to NumPy
    integer arrays and comparing them.

    Parameters
    ----------
    msid : string
        The MSID that is being modeled.
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    out_dir : string
        The path to the output directory.
    """
    images = build_image_list(msid)
    for image in images:
        new_path = os.path.join(out_dir, image)
        old_path = os.path.join(test_data_dir, name, load_week, image)
        if not os.path.exists(old_path):
            print("WARNING: Image %s has new answer but not old. Answers should be updated." % image)
            continue
        if not os.path.exists(new_path):
            print("WARNING: Image %s has old answer but not new. Answers should be updated." % image)
            continue
        new_image = misc.imread(new_path)
        old_image = misc.imread(old_path)
        assert_array_equal(new_image, old_image)

def copy_new_images(msid, name, out_dir, answer_dir):
    """
    This function copies the image files generated in this test
    run to a directory specified by the user, typically for
    inspection and for possible updating of the "gold standard"
    answers.

    Parameters
    ----------
    msid : string
        The MSID that is being modeled.
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    out_dir : string
        The path to the output directory.
    answer_dir : string
        The path to the directory to which to copy the files.
    """
    images = build_image_list(msid)
    for image in images:
        fromfile = os.path.join(out_dir, image)
        adir = os.path.join(answer_dir, name)
        if not os.path.exists(adir):
            os.mkdir(adir)
        tofile = os.path.join(adir, image)
        shutil.copyfile(fromfile, tofile)

def run_image_test(msid, name, load_week, out_dir, answer_dir):
    """
    This function runs the image answer test in one of two modes:
    either comparing the image answers from this test to the "gold
    standard" answers or to simply run the model to generate image
    answers.

    Parameters
    ----------
    msid : string
        The MSID that is being modeled.
    name : string
        The "short" name of the model, referring to the component
        it models the temperature for, e.g. "dea", "dpa", "psmc".
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    out_dir : string
        The path to the output directory.
    answer_dir : string
        The path to the directory to which to copy the files. Is None
        if this is a test run, is an actual directory if we are simply
        generating answers. 
    """
    out_dir = os.path.abspath(out_dir)
    if not answer_dir:
        compare_images(msid, name, load_week, out_dir)
    else:
        copy_new_images(msid, name, out_dir, answer_dir)
