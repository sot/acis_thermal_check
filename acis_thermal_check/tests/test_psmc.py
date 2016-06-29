import os
import shutil
import tempfile
from acis_thermal_check import psmc_check
from acis_thermal_check.tests.utils import \
    run_answer_test, run_image_test, run_model, \
    oflsdir

def test_psmc(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    shutil.copy(os.path.join(oflsdir, 'dahtbon_history.rdb'), tmpdir)
    out_dir = run_model("psmc", psmc_check)
    run_answer_test("psmc", out_dir, generate_answers)
    run_image_test("1pdeaat", "psmc", out_dir, generate_answers)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

