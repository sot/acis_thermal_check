import os
import shutil
import tempfile
from acis_thermal_check import dpa_check
from acis_thermal_check.tests.utils import \
    run_answer_test, run_image_test, run_model

def test_dpa(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    out_dir = run_model("dpa", dpa_check)
    run_answer_test("dpa", out_dir, generate_answers)
    run_image_test("1dpamzt", "dpa", out_dir, generate_answers)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

