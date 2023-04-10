import pytest


def pytest_addoption(parser):
    parser.addoption('--dbhost', action="store", default="localhost")
    parser.addoption('--aphost', action="store", default="localhost")
    parser.addoption('--mqhost', action="store", default="localhost")


@pytest.fixture(scope='session')
def dbhost(request):
    dbhost_value = request.config.option.dbhost
    if dbhost_value is None:
        pytest.skip()
    return dbhost_value


@pytest.fixture(scope='session')
def aphost(request):
    aphost_value = request.config.option.aphost
    if aphost_value is None:
        pytest.skip()
    return aphost_value


@pytest.fixture(scope='session')
def mqhost(request):
    mqhost_value = request.config.option.mqhost
    if mqhost_value is None:
        pytest.skip()
    return mqhost_value
