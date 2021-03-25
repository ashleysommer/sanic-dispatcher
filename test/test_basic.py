from sanic import Sanic
from sanic import response
import pytest

from sanic_dispatcher import SanicDispatcherMiddlewareController, SanicDispatcherMiddleware
#
# app = Sanic(__name__)
# dispatcher = SanicDispatcherMiddlewareController(app)
# child_sanic_app = Sanic("MyChildSanicApp")
# _ = CORS(child_sanic_app)
# child_sanic_app_hosted = Sanic("MyChildHostedSanicApp")
# child_flask_app = Flask("MyChildFlaskApp")


# @app.middleware("response")
# async def modify_response(request, response):
#     response.body = response.body + b"\nModified by Sanic Response middleware!"
#     response.headers['Content-Length'] = len(response.body)
#     return response
#
#
# @app.listener('before_server_start')
# async def b0(app, loop):
#     print("Parent app {} starting".format(app.name))
#     return
#
#
# @app.route("/")
# async def index1(request):
#     return response.text("Hello World from {}".format(request.app.name))
#
#
# @child_sanic_app.route("/", methods=['GET', 'OPTIONS'])
# async def index2(request):
#     return response.text("Hello World from {}.".format(request.app.name))
#
#
# @child_sanic_app.listener('before_server_start')
# async def b1(app, loop):
#     print("Child app {} Starting".format(app.name))
#     return
#
#
# @child_sanic_app_hosted.route("/")
# async def index3(request):
#     return response.text("Hello World from {}".format(request.app.name))
#
#
# @child_flask_app.route("/")
# def index4():
#     app = flask_app
#     return make_response("Hello World from {}".format(app.import_name))


# dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
# dispatcher.register_sanic_application(child_sanic_app_hosted, '/sanicchild', host='example.com', apply_middleware=True)
# dispatcher.register_wsgi_application(child_flask_app.wsgi_app, '/flaskchild', apply_middleware=True)
# #dispatcher.unregister_application(child_sanic_app)
#
# test_url = dispatcher.url_for("index1")

def test_basic_parent(dispatcher):
    @dispatcher.parent_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index1(request):
        return response.text("Hello World from {}.".format(request.app.name))
    tester = dispatcher.parent_app.test_client
    request, resp = tester.get("/test", gather_request=True)
    assert resp.status == 200

def test_basic_child(dispatcher):
    child_sanic_app = Sanic("child1")
    @dispatcher.parent_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index1(request):
        return response.text("Hello World from {}.".format(request.app.name))
    @child_sanic_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index2(request):
        return response.text("Hello World from {}.".format(request.app.name))
    dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
    tester = dispatcher.parent_app.test_client
    request, resp = tester.get("/sanicchild/test", gather_request=True)
    assert resp.status == 200
    assert "child1" in resp.text

def test_child_with_mw(dispatcher):
    child_sanic_app = Sanic("child2")
    @dispatcher.parent_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index1(request):
        return response.text("Hello World from {}.".format(request.app.name))
    @dispatcher.parent_app.middleware("response")
    async def mw(request, resp):
        return response.text("Hello from response middleware.")
    @child_sanic_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index2(request):
        return response.text("Hello World from {}.".format(request.app.name))
    dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
    tester = dispatcher.parent_app.test_client
    request, resp = tester.get("/sanicchild/test", gather_request=True)
    assert resp.status == 200
    assert "response middleware" in resp.text

def test_child_with_child_mw(dispatcher):
    child_sanic_app = Sanic("child3")
    @dispatcher.parent_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index1(request):
        return response.text("Hello World from {}.".format(request.app.name))
    @child_sanic_app.middleware("response")
    async def mw(request, resp):
        return response.text("Hello from child response middleware.")
    @child_sanic_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index2(request):
        return response.text("Hello World from {}.".format(request.app.name))
    dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
    tester = dispatcher.parent_app.test_client
    request, resp = tester.get("/sanicchild/test", gather_request=True)
    assert resp.status == 200
    assert "child response middleware" in resp.text

def test_flask_child(dispatcher):
    from flask import Flask
    child_flask_app = Flask("child4")
    @dispatcher.parent_app.route("/test", methods=['GET', 'OPTIONS'])
    async def index1(request):
        return response.text("Hello World from {}.".format(request.app.name))
    @child_flask_app.route("/test", methods=['GET', 'OPTIONS'])
    def index2():
        return "Hello World from flask!."
    dispatcher.register_wsgi_application(child_flask_app, '/flaskchild', apply_middleware=True)
    tester = dispatcher.parent_app.test_client
    request, resp = tester.get("/flaskchild/test", gather_request=True)
    assert resp.status == 200
    assert "flask!" in resp.text
