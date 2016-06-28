from acis_thermal_check import dea_check, \
    dpa_check, psmc_check
from acis_thermal_check.tests.utils import \
    TestOpts, test_data_dir, requires_file
import pickle
import os
from numpy.testing import assert_array_equal
import tempfile
import shutil

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

@requires_file("dea_results.pkl")
def test_dea_check(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    short_msid = "dea" 
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    dea_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

@requires_file("dpa_results.pkl")
def test_dpa_check(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    short_msid = "dpa"
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    dpa_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

@requires_file("psmc_results.pkl")
def test_psmc_check(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    short_msid = "psmc"
    out_dir = short_msid+"_test"
    opt = TestOpts(short_msid, "2016:100:12:00:00.000", out_dir)
    psmc_check.driver(opt)
    if not generate_answers:
        compare_results(short_msid, out_dir)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

