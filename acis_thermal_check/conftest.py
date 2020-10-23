import pytest


def pytest_addoption(parser):
    parser.addoption("--answer_store", action='store_true',
                     help="If true, generate new answers, but don't test. "
                          "Default: False, which performs only the test.")
    parser.addoption("--test_root", type=str,
                     help="If specified, this will be the location which "
                          "the test artifacts will be stored. If not, a "
                          "temporary directory is created.")


@pytest.fixture()
def answer_store(request):
    return request.config.getoption('--answer_store')


@pytest.fixture(autouse=True, scope='module')
def test_root(request):
    return request.config.getoption('--test_root')
