"""
    sanic_dispatcher
    ~~~~

    :copyright: (c) 2017 by Ashley Sommer (based on DispatcherMiddleware in the Werkzeug Project).
    :license: MIT, see LICENSE for more details.
"""
from sanic import Sanic, response
from sanic_dispatcher import SanicDispatcherMiddlewareController
from flask import Flask, make_response, current_app as flask_app

app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)

child_sanic_app = Sanic("MyChildSanicApp")

child_flask_app = Flask("MyChildFlaskApp")

@app.middleware("response")
async def modify_response(request, response):
    response.body = response.body + b"\nModified by Sanic Response middleware!"
    response.headers['Content-Length'] = len(response.body)
    return response

@app.route("/")
async def index(request):
    return response.text("Hello World from {}".format(request.app.name))

@child_sanic_app.route("/")
async def index(request):
    return response.text("Hello World from {}".format(request.app.name))

@child_flask_app.route("/")
def index():
    app = flask_app
    return make_response("Hello World from {}".format(app.import_name))

dispatcher.register_sanic_application(child_sanic_app, '/sanicchild', apply_middleware=True)
dispatcher.register_wsgi_application(child_flask_app.wsgi_app, '/flaskchild', apply_middleware=True)
dispatcher.unregister_application(child_sanic_app)

if __name__ == "__main__":
    app.run(port=8001, debug=True)
