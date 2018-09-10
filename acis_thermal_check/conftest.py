import pytest

def pytest_addoption(parser):
    parser.addoption("--answer_store",
                     help="Generate new answers, but don't test. "
                          "Argument is the directory to store the answers to. "
                          "Default: None, which performs the test.")
    parser.addoption("--model_spec",
                     help="The path to the model specification used by "
                          "the model test run.")

@pytest.fixture()
def answer_store(request):
    return request.config.getoption('--answer_store')

@pytest.fixture()
def model_spec(request):
    return request.config.getoption('--model_spec')
