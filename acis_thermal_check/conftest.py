import pytest


def pytest_addoption(parser):
    parser.addoption("--answer_store", action='store_true',
                     help="If true, generate new answers, but don't test. "
                          "Default: False, which performs only the test.")

@pytest.fixture()
def answer_store(request):
    return request.config.getoption('--answer_store')
