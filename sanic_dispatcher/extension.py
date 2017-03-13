# -*- coding: utf-8 -*-
"""
    sanic_dispatcher
    ~~~~

    :copyright: (c) 2017 by Ashley Sommer (based on DispatcherMiddleware in the Werkzeug Project).
    :license: MIT, see LICENSE for more details.
"""

from inspect import isawaitable
from io import BytesIO
from sanic import Sanic
from sanic.response import HTTPResponse


class WsgiApplication(object):
    __slots__ = ['app', 'apply_middleware']

    def __init__(self, app, apply_middleware=False):
        self.app = app
        self.apply_middleware = apply_middleware


class SanicApplication(object):
    __slots__ = ['app', 'apply_middleware']

    def __init__(self, app, apply_middleware=False):
        self.app = app
        self.apply_middleware = apply_middleware


class SanicDispatcherMiddleware(object):
    """Is a multi-application dispatcher, and also acts as a sanic-to-wsgiApp adapter.
    Is based on the DispatcherMiddleware class in werkzeug"""

    __slots__ = ['parent_app', 'parent_handle_request', 'mounts']

    def __init__(self, parent_app, parent_handle_request, mounts=None):
        self.parent_app = parent_app
        self.parent_handle_request = parent_handle_request
        self.mounts = mounts or {}

    # noinspection PyMethodMayBeStatic
    def _call_wsgi_app(self, script_name, path_info, request, wsgi_app, response_callback):
        """Even though the lint says that this method can be static, it really can't. The internal functions need to be
        unique for every call to `_call_wsgi_app`, so a static method would not work here."""
        http_response = None
        body_bytes = bytearray()

        def _start_response(status, headers, *args, **kwargs):
            """The start_response callback as required by the wsgi spec. This sets up a response including the
            status code and the headers, but doesn't write a body."""
            nonlocal http_response
            nonlocal body_bytes
            if isinstance(status, int):
                code = status
            elif isinstance(status, str):
                code = int(status.split(" ")[0])
            else:
                raise RuntimeError("status cannot be turned into a code.")
            sanic_headers = dict(headers)
            response_constructor_args = {'status': code,  'headers': sanic_headers}
            if 'content_type' in kwargs:
                response_constructor_args['content_type'] = kwargs['content_type']
            elif 'Content-Type' in sanic_headers:
                response_constructor_args['content_type'] = str(sanic_headers['Content-Type']).split(";")[0].strip()
            http_response = HTTPResponse(**response_constructor_args)

            def _write_body(body_data):
                """This doesn't seem to be used, but it is part of the wsgi spec, so need to have it."""
                nonlocal body_bytes
                nonlocal http_response
                if isinstance(body_data, bytes):
                    pass
                else:
                    try:
                        # Try to encode it regularly
                        body_data = body_data.encode()
                    except AttributeError:
                        # Convert it to a str if you can't
                        body_data = str(body_data).encode()
                body_bytes.extend(body_data)
            return _write_body

        environ = {}
        original_script_name = environ.get('SCRIPT_NAME', '')
        environ['SCRIPT_NAME'] = original_script_name + script_name
        environ['PATH_INFO'] = path_info
        if 'host' in request.headers:
            host = request.headers['host']
        else:
            host = 'localhost:80'
        if 'content-type' in request.headers:
            content_type = request.headers['content-type']
        else:
            content_type = 'text/plain'
        environ['CONTENT_TYPE'] = content_type
        if 'content-length' in request.headers:
            content_length = request.headers['content-length']
            environ['CONTENT_LENGTH'] = content_length

        split_host = host.split(':', 1)
        server_name = split_host[0]
        if len(split_host) > 0:
            server_port = split_host[1]
        else:
            raise RuntimeError("Did not get a Port number in the url string!")
        environ['SERVER_PORT'] = server_port
        environ['SERVER_NAME'] = server_name
        environ['SERVER_PROTOCOL'] = 'HTTP/1.1' if request.version == "1.1" else 'HTTP/1.0'
        environ['HTTP_HOST'] = host
        environ['QUERY_STRING'] = request.query_string or ''
        environ['REQUEST_METHOD'] = request.method
        environ['wsgi.url_scheme'] = 'http'  # todo: detect http vs https
        environ['wsgi.input'] = BytesIO(request.body) if request.body is not None and len(request.body) > 0\
            else BytesIO(b'')
        try:
            wsgi_return = wsgi_app(environ, _start_response)
        except Exception as e:
            print(e)
            raise e
        if http_response is None:
            http_response = HTTPResponse("WSGI call error.", 500)
        else:
            for body_part in wsgi_return:
                if body_part is not None:
                    if isinstance(body_part, bytes):
                        pass
                    else:
                        try:
                            # Try to encode it regularly
                            body_part = body_part.encode()
                        except AttributeError:
                            # Convert it to a str if you can't
                            body_part = str(body_part).encode()
                    body_bytes.extend(body_part)
            http_response.body = bytes(body_bytes)
        return response_callback(http_response)

    async def __call__(self, request, response_callback):
        script = str(request.url).split('?', 1)[0]
        path_info = ''
        while '/' in script:
            if script in self.mounts:
                application = self.mounts[script]
                break
            script, last_item = script.rsplit('/', 1)
            path_info = '/%s%s' % (last_item, path_info)
        else:
            application = self.mounts.get(script, None)
        request.url = path_info if len(path_info) > 0 else '/'

        if application is None:  # no child matches, call the parent
            return await self.parent_handle_request(request, response_callback)

        parent_app = self.parent_app
        real_response_callback = response_callback

        response = False

        def _response_callback(child_response):
            nonlocal response
            response = child_response

        replace_response_callback = _response_callback
        if application.apply_middleware and parent_app.request_middleware:
            request.app = parent_app
            for middleware in parent_app.request_middleware:
                response = middleware(request)
                if isawaitable(response):
                    response = await response
                if response:
                    break
        if not response:
            if isinstance(application, WsgiApplication):  # child is wsgi_app
                self._call_wsgi_app(script, path_info, request, application.app, replace_response_callback)
            else:  # must be a sanic application
                await application.app.handle_request(request, replace_response_callback)

        if application.apply_middleware and parent_app.response_middleware:
            request.app = parent_app
            for _middleware in parent_app.response_middleware:
                _response = _middleware(request, response)
                if isawaitable(_response):
                    _response = await _response
                if _response:
                    response = _response
                    break

        while isawaitable(response):
            response = await response

        return real_response_callback(response)


class SanicDispatcherMiddlewareController(object):
    __slots__ = ['parent_app', 'parent_handle_request', 'applications', 'url_prefix']

    def __init__(self, app, url_prefix=None):
        """
        :param Sanic app:
        :param url_prefix:
        """
        self.parent_app = app
        self.applications = {}
        self.url_prefix = None if url_prefix is None else str(url_prefix).rstrip('/')
        # Woo, monkey-patch!
        self.parent_handle_request = app.handle_request
        self.parent_app.handle_request = self.handle_request

    def register_sanic_application(self, application, url_prefix, apply_middleware=False):
        """
        :param Sanic application:
        :param url_prefix:
        :param apply_middleware:
        :return:
        """
        assert isinstance(application, Sanic), "Pass only instances of Sanic to register_sanic_application."
        registered_service_url = ''
        if self.url_prefix is not None:
            registered_service_url += self.url_prefix
        registered_service_url += url_prefix
        self.applications[registered_service_url] = SanicApplication(application, apply_middleware)
        self._update_request_handler()

    def register_wsgi_application(self, application, url_prefix, apply_middleware=False):
        """
        :param application:
        :param url_prefix:
        :param apply_middleware:
        :return:
        """
        registered_service_url = ''
        if self.url_prefix is not None:
            registered_service_url += self.url_prefix
        registered_service_url += url_prefix
        self.applications[registered_service_url] = WsgiApplication(application, apply_middleware)
        self._update_request_handler()

    def _update_request_handler(self):
        """
        Rebuilds the SanicDispatcherMiddleware every time a new application is registered
        :return:
        """
        dispatcher = SanicDispatcherMiddleware(self.parent_app, self.parent_handle_request, self.applications)
        self.parent_app.handle_request = dispatcher

    async def handle_request(self, request, response_callback):
        """
        This is only called as a backup handler if _update_request_handler was not yet called.
        :param request:
        :param response_callback:
        :return:
        """
        dispatcher = SanicDispatcherMiddleware(self.parent_app, self.parent_handle_request, self.applications)
        self.parent_app.handle_request = dispatcher  # save it for next time
        retval = dispatcher(request, response_callback)
        if isawaitable(retval):
            retval = await retval
        return retval
