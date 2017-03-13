#Sanic-Dispatcher
###A Dispatcher extension for Sanic that also acts as a Sanic-to-WSGI adapter 
#
Allows you to do this: *(seriously)*
```python
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

if __name__ == "__main__":
    app.run(port=8001, debug=True)
```
#
##How To Use
First make a Sanic application the way you normally do:
```python
from sanic import Sanic

app = Sanic(__name__) # This creates a sanic app
```
`app` becomes your 'base' or 'parent' sanic app which will accommodate the Dispatcher extension

Create a Dispatcher
```python
from sanic_dispatcher import SanicDispatcherMiddlewareController

dispatcher = SanicDispatcherMiddlewareController(app)
```
`dispatcher` is your new dispatcher controller.
*Note: This takes a reference to `app` as its first parameter, but it does not consume `app`, nor does it return `app`.*

**I want to dispatch another Sanic App**
```python
app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)

otherapp = Sanic("MyChildApp")

dispatcher.register_sanic_application(otherapp, "/childprefix")

@otherapp.route('/')
async def index(request):
    return response.text("Hello World from Child App")
```
Browsing to url `/childprefix/` will invoke the `otherapp` App, and call the `/` route which displays "Hello World from Child App"

**What if the other App is a Flask App?**
```python
from flask import Flask, make_response

app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)
flaskapp = Flask("MyFlaskApp")

# register the wsgi_app method from the flask app into the dispatcher
dispatcher.register_wsgi_application(flaskapp.wsgi_app, "/flaskprefix")

@flaskapp.route('/')
def index():
    return make_response("Hello World from Flask App")
```
Browsing to url `/flaskprefix/` will invoke the Flask App, and call the `/` route which displays "Hello World from Flask App"

**What if the other App is a Django App?**
```python
import my_django_app

app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)
# register the django wsgi application into the dispatcher
dispatcher.register_wsgi_application(my_django_app.wsgi.application,
                                     "/djangoprefix")
```
Browsing to url `/djangoprefix/` will invoke the Django App.

**Can I run a default application?**

The Sanic App `app` you create at the start is also the default app.

When you navigate to a URL that does not match a registered dispatch prefix, this Sanic app will handle the request itself as per normal.
```python
app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)

otherapp = Sanic("MyChildApp")

dispatcher.register_sanic_application(otherapp, "/childprefix")

@app.route('/')
async def index(request):
    return response.text("Hello World from Default App")

@otherapp.route('/')
async def index(request):
    return response.text("Hello World from Child App")
```
Browsing to url `/` will *not* invoke any Dispatcher applications, so `app` will handle the request itself, resolving the `/` route which displays "Hello World from Default App"

**I want to apply common middleware to the registered applications!**

Easy!
```python
import my_django_app
from flask import Flask, make_response, current_app

app = Sanic(__name__)

dispatcher = SanicDispatcherMiddlewareController(app)

child_sanic_app = Sanic("MyChildSanicApp")

child_flask_app = Flask("MyChildFlaskApp")

@app.middleware("request")
async def modify_request(request):
    request.headers['Content-Type'] = "text/plain"

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
    app = current_app
    return make_response("Hello World from {}".format(app.import_name))

dispatcher.register_sanic_application(child_sanic_app,
                                      '/childprefix', apply_middleware=True)
dispatcher.register_wsgi_application(my_django_app.wsgi.application,
                                     '/djangoprefix', apply_middleware=True)
dispatcher.register_wsgi_application(child_flask_app.wsgi_app,
                                     '/flaskprefix', apply_middleware=True)
```
The key here is passing `apply_middleware=True` to the relevant register application function. By default `apply_middleware` is set to `False` for all registered dispatcher applications.

In this example the Sanic Request Middleware `modify_request` will be applied to ALL requests, including those handled by applications registered on the dispatcher. The request middleware will be applied to the `request` *before* it is passed to any registered applications.

In this example the Sanic Response Middleware `modify_response` will be applied to ALL responses, including those which were generated by applications registered on the dispatcher. The response middleware will be applied to the `response` *after* it is processed by the registered application.
