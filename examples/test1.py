"""
    sanic_dispatcher
    ~~~~

    :copyright: (c) 2017 by Ashley Sommer (based on DispatcherMiddleware in the Werkzeug Project).
    :license: MIT, see LICENSE for more details.
"""
from sanic import Sanic, response
from sanic_dispatcher import SanicDispatcherMiddlewareController
from flask import Flask, make_response, current_app as flask_app
from sanic_cors import CORS

app = Sanic(__name__)
dispatcher = SanicDispatcherMiddlewareController(app)
child_sanic_app = Sanic("MyChildSanicApp")
_ = CORS(child_sanic_app)
child_sanic_app_hosted = Sanic("MyChildHostedSanicApp")
child_flask_app = Flask("MyChildFlaskApp")


@app.middleware("response")
async def modify_response(request, response):
    response.body = response.body + b"\nModified by Sanic Response middleware!"
    response.headers['Content-Length'] = len(response.body)
    return response


@app.listener('before_server_start')
async def b0(app, loop):
    print("Parent app {} starting".format(app.name))
    return


@app.route("/")
async def index1(request):
    return response.text("Hello World from {}".format(request.app.name))


@child_sanic_app.route("/", methods=['GET', 'OPTIONS'])
async def index2(request):
    return response.text("Hello World from {}.".format(request.app.name))


@child_sanic_app.listener('before_server_start')
async def b1(app, loop):
    print("Child app {} Starting".format(app.name))
    return


@child_sanic_app_hosted.route("/")
async def index3(request):
    return response.text("Hello World from {}".format(request.app.name))


@child_flask_app.route("/")
def index4():
    app = flask_app
    return make_response("Hello World from {}".format(app.import_name))


dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
dispatcher.register_sanic_application(child_sanic_app_hosted, '/sanicchild', host='example.com', apply_middleware=True)
dispatcher.register_wsgi_application(child_flask_app.wsgi_app, '/flaskchild', apply_middleware=True)
#dispatcher.unregister_application(child_sanic_app)

test_url = dispatcher.url_for("index1")

if __name__ == "__main__":
    app.run(port=8001, debug=True, auto_reload=False)
