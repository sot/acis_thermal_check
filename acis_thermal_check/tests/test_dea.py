import os
import shutil
import tempfile

from .. import dea_check
from .utils import run_answer_test, \
    run_image_test, run_model

def test_dea(generate_answers):
    tmpdir = tempfile.mkdtemp()
    curdir = os.getcwd()
    os.chdir(tmpdir)
    out_dir = run_model("dea", dea_check)
    run_answer_test("dea", out_dir, generate_answers)
    run_image_test("1deamzt", "dea", out_dir, generate_answers)
    os.chdir(curdir)
    shutil.rmtree(tmpdir)

