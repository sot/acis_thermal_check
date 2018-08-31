from six.moves import cPickle as pickle
import os
from numpy.testing import assert_array_equal, \
    assert_allclose
import shutil
import numpy as np
import tempfile
from .main import ACISThermalCheck
import pytest
import six

def pytest_addoption(parser):
    parser.addoption("--answer_store",
                     help="Generate new answers, but don't test. "
                          "Argument is the directory to store the answers to.")

@pytest.fixture()
def answer_store(request):
    return request.config.getoption('--answer_store')

months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# This directory is currently where the thermal model
# "gold standard" answers live.
test_data_dir = "/data/acis/thermal_model_tests"

# Loads for regression testing
normal_loads = ["MAR0617A", "MAR2017E", "JUL3117B", "SEP0417A"]
too_loads = ["MAR1517B", "JUL2717A", "AUG2517C", "AUG3017A"]
stop_loads = ["MAR0817B", "MAR1117A", "APR0217B", "SEP0917C"]

class TestArgs(object):
    """
    A mock-up of a command-line parser object to be used with
    ACISThermalCheck testing.

    Parameters
    ----------
    name : string
        The "short name" of the temperature to be modeled.
    outdir : string
        The path to the output directory.
    model_path : string
        The path to the model code itself.
    run_start : string, optional
        The run start time in YYYY:DOY:HH:MM:SS.SSS format. If not
        specified, one will be created 3 days prior to the model run.
    load_week : string, optional
        The load week to be tested, in a format like "MAY2016". If not
        provided, it is assumed that a full set of initial states will
        be supplied.
    days : float, optional
        The number of days to run the model for. Default: 21.0
    T_init : float, optional
        The starting temperature for the run. If not set, it will be
        determined from telemetry.
    interrupt : boolean, optional
        Whether or not this is an interrupt load. Default: False
    state_builder string, optional
        The mode used to create the list of commanded states. "sql" or
        "acis", default "acis".
    cmd_states_db : string, optional
        The mode of database access for the commanded states database.
        "sqlite" or "sybase". Default: "sqlite"
    verbose : integer, optional
        The verbosity of the output. Default: 0
    """
    def __init__(self, name, outdir, model_path, run_start=None,
                 load_week=None, days=21.0, T_init=None, interrupt=False,
                 state_builder='acis', cmd_states_db="sqlite", verbose=0):
        from datetime import datetime
        if cmd_states_db is None:
            if six.PY2:
                cmd_states_db = "sybase"
            else:
                cmd_states_db = "sqlite"
        self.load_week = load_week
        if run_start is None:
            year = 2000 + int(load_week[5:7])
            month = months.index(load_week[:3])+1
            day = int(load_week[3:5])
            run_start = datetime(year, month, day).strftime("%Y:%j:%H:%M:%S")
        self.run_start = run_start
        self.outdir = outdir
        # load_week sets the bsdir
        if load_week is None:
            self.backstop_file = None
        else:
            load_year = "20%s" % load_week[-3:-1]
            load_letter = load_week[-1].lower()
            self.backstop_file = "/data/acis/LoadReviews/%s/%s/ofls%s" % (load_year, load_week[:-1], load_letter)
        self.days = days
        self.nlet_file = '/data/acis/LoadReviews/NonLoadTrackedEvents.txt'
        self.interrupt = interrupt
        self.state_builder = state_builder
        self.cmd_states_db = cmd_states_db
        self.T_init = T_init
        self.traceback = True
        self.verbose = verbose
        self.model_spec = os.path.join(model_path, "%s_model_spec.json" % name)
        self.version = None
        if name == "acisfp":
            self.fps_nopref = os.path.join(model_path, "FPS_NoPref.txt")

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

def exception_catcher(test, old, new, data_type, **kwargs):
    if new.dtype.kind == "S":
        new = new.astype("U")
    if old.dtype.kind == "S":
        old = old.astype("U")
    try:
        test(old, new, **kwargs)
    except AssertionError:
        raise AssertionError("%s are not the same!" % data_type)

class RegressionTester(object):
    def __init__(self, msid, name, model_path, valid_limits,
                 hist_limit, calc_model, atc_class=None,
                 atc_kwargs=None):
        self.msid = msid
        self.name = name
        self.model_path = model_path
        self.valid_limits = valid_limits
        self.hist_limit = hist_limit
        self.calc_model = calc_model
        if atc_kwargs is None:
            atc_kwargs = {}
        self.atc_kwargs = atc_kwargs
        if atc_class is None:
            atc_class = ACISThermalCheck
        self.atc_class = atc_class

    def run_test_arrays(self, generate_answers, exclude_images=None, 
                        state_builder='acis', run_start=None):
        for load_week in normal_loads:
            self.load_test_template(load_week, generate_answers, interrupt=False, 
                                    exclude_images=exclude_images, 
                                    state_builder=state_builder, run_start=run_start)
        for load_week in too_loads:
            self.load_test_template(load_week, generate_answers, interrupt=True, 
                                    exclude_images=exclude_images, 
                                    state_builder=state_builder, run_start=run_start)
        for load_week in stop_loads:
            self.load_test_template(load_week, generate_answers, interrupt=True, 
                                    exclude_images=exclude_images, 
                                    state_builder=state_builder, run_start=run_start)

    def load_test_template(self, load_week, generate_answers, run_start=None,
                           state_builder='acis', interrupt=False, 
                           exclude_images=None):
        if generate_answers is not None:
            generate_answers = os.path.join(os.path.abspath(generate_answers),
                                            self.name, load_week)
            if not os.path.exists(generate_answers):
                os.makedirs(generate_answers)
        tmpdir = tempfile.mkdtemp()
        curdir = os.getcwd()
        os.chdir(tmpdir)
        out_dir = self.name+"_test"
        args = TestArgs(self.name, out_dir, self.model_path, run_start=run_start,
                        load_week=load_week, interrupt=interrupt,
                        state_builder=state_builder)
        msid_check = self.atc_class(self.msid, self.name, self.valid_limits,
                                    self.hist_limit, self.calc_model, args,
                                    **self.atc_kwargs)
        msid_check.run()
        self.run_answer_test(load_week, out_dir, generate_answers)
        os.chdir(curdir)
        shutil.rmtree(tmpdir)

    def run_answer_test(self, load_week, out_dir, answer_dir):
        """
        This function runs the answer test in one of two modes:
        either comparing the answers from this test to the "gold
        standard" answers or to simply run the model to generate
        answers.

        Parameters
        ----------
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
            self.compare_results(load_week, out_dir)
        else:
            self.copy_new_results(out_dir, answer_dir)

    def compare_results(self, load_week, out_dir):
        """
        This function compares the "gold standard" data with the current
        test run's data.

        Parameters
        ----------
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
        old_answer_file = os.path.join(test_data_dir, self.name, load_week,
                                       "validation_data.pkl")
        kwargs = {} if six.PY2 else {'encoding': 'latin1'}
        old_results = pickle.load(open(old_answer_file, "rb"), **kwargs)
        # Compare predictions
        new_pred = new_results["pred"]
        old_pred = old_results["pred"]
        pred_keys = set(new_pred.keys()) | set(old_pred.keys())
        for k in pred_keys:
            if k not in new_pred:
                print("WARNING in pred: '%s' in old answer but not new. Answers should be updated." % k)
                continue
            if k not in old_pred:
                print("WARNING in pred: '%s' in new answer but not old. Answers should be updated." % k)
                continue
            exception_catcher(assert_allclose, new_pred[k], old_pred[k],
                              "Validation model arrays for %s" % k)
        # Compare telemetry
        new_tlm = new_results['tlm']
        old_tlm = old_results['tlm']
        tlm_keys = set(new_tlm.dtype.names) | set(old_tlm.dtype.names)
        for k in tlm_keys:
            if k not in new_tlm.dtype.names:
                print("WARNING in tlm: '%s' in old answer but not new. Answers should be updated." % k)
                continue
            if k not in old_tlm.dtype.names:
                print("WARNING in tlm: '%s' in new answer but not old. Answers should be updated." % k)
                continue
            exception_catcher(assert_array_equal, new_tlm[k], old_tlm[k],
                              "Validation telemetry arrays for %s" % k)
        # Compare
        for prefix in ("temperatures", "states"):
            self.compare_data_files(prefix, load_week, out_dir)

    def compare_data_files(self, prefix, load_week, out_dir):
        """
        This function compares the "gold standard" data with the current
        test run's data for the .dat files produced in the thermal model
        run. Called by ``compare_results``.

        Parameters
        ----------
        prefix : string
            The prefix of the file, "temperatures" or "states".
        load_week : string, optional
            The load week to be tested, in a format like "MAY2016". If not
            provided, it is assumed that a full set of initial states will
            be supplied.
        out_dir : string
            The path to the output directory.
        """
        fn = prefix+".dat"
        new_fn = os.path.join(out_dir, fn)
        old_fn = os.path.join(test_data_dir, self.name, load_week, fn)
        new_data = np.loadtxt(new_fn, skiprows=1, dtype=data_dtype[prefix])
        old_data = np.loadtxt(old_fn, skiprows=1, dtype=data_dtype[prefix])
        # Compare test run data to gold standard. Since we're loading from
        # ASCII text files here, floating-point comparisons will be different
        # at machine precision, others will be exact.
        for k, dt in new_data.dtype.descr:
            if 'f' in dt:
                exception_catcher(assert_allclose, new_data[k], old_data[k],
                                  "Prediction arrays for %s" % k, rtol=1.0e-5)
            else:
                exception_catcher(assert_array_equal, new_data[k], old_data[k],
                                  "Prediction arrays for %s" % k)

    def copy_new_results(self, out_dir, answer_dir):
        """
        This function copies the pickle files and the .dat files
        generated in this test run to a directory specified by the
        user, typically for inspection and for possible updating of
        the "gold standard" answers.

        Parameters
        ----------
        out_dir : string
            The path to the output directory.
        answer_dir : string
            The path to the directory to which to copy the files.
        """
        for fn in ('validation_data.pkl', 'states.dat', 'temperatures.dat'):
            fromfile = os.path.join(out_dir, fn)
            tofile = os.path.join(answer_dir, fn)
            shutil.copyfile(fromfile, tofile)

