import pytest
import pytest_asyncio
pytestmark = pytest.mark.asyncio
from sanic import Sanic
from sanic import __version__ as sanic_version
from sanic_dispatcher import SanicDispatcherMiddlewareController, SanicDispatcherMiddleware

try:
    from setuptools.extern import packaging
except ImportError:
    from pkg_resources.extern import packaging

SANIC_VERSION = packaging.version.parse(sanic_version)
SANIC_0_7_0 = packaging.version.parse('0.7.0')
if SANIC_VERSION < SANIC_0_7_0:
    raise RuntimeError("Please use Sanic v0.7.0 or greater with this extension.")
SANIC_19_03_0 = packaging.version.parse('19.3.0')
SANIC_18_12_0 = packaging.version.parse('18.12.0')
SANIC_21_03_0 = packaging.version.parse('21.03.0')
IS_19_03 = SANIC_VERSION >= SANIC_19_03_0
IS_18_12 = SANIC_VERSION >= SANIC_18_12_0
IS_21_03 = SANIC_VERSION >= SANIC_21_03_0

if IS_21_03:
    from sanic_testing import TestManager

def app_with_name(name):
    s = Sanic(name)
    if IS_21_03:
        manager = TestManager(s)
    return s

@pytest.fixture
def app(request):
    a = app_with_name(request.node.name)
    return a

@pytest.fixture
def dispatcher(request):
    a = app_with_name(request.node.name)
    return SanicDispatcherMiddlewareController(a)
