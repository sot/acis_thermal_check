import pytest

def pytest_addoption(parser):
    parser.addoption("--generate_answers", action="store_true",
        help="Generate new answers; don't test")

@pytest.fixture()
def generate_answers(request):
    return request.config.getoption('--generate_answers')
