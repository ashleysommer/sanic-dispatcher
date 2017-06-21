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


class SanicCompatURL(object):
    """
    This class exists because the sanic native URL type is private (a non-exposed C module)
    and all of its components are read-only. We need to modify the URL path in the dispatcher
    so we build a feature-compatible writable class of our own to use instead.
    """
    __slots__ = ('schema', 'host', 'port', 'path', 'query', 'fragment', 'userinfo')

    def __init__(self, schema, host, port, path, query, fragment, userinfo):
        self.schema = schema
        self.host = host
        self.port = port
        self.path = path
        self.query = query
        self.fragment = fragment
        self.userinfo = userinfo


class SanicDispatcherMiddleware(object):
    """
    A multi-application dispatcher, and also acts as a sanic-to-wsgiApp adapter.
    Based on the DispatcherMiddleware class in werkzeug.
    """

    __slots__ = ['parent_app', 'parent_handle_request', 'mounts', 'hosts']

    def __init__(self, parent_app, parent_handle_request, mounts=None, hosts=None):
        self.parent_app = parent_app
        self.parent_handle_request = parent_handle_request
        self.mounts = mounts or {}
        self.hosts = frozenset(hosts) if hosts else frozenset()

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
        if request._parsed_url and request._parsed_url.host is not None:
            host = request._parsed_url.host.decode('utf-8')
        elif 'host' in request.headers:
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
        if request._parsed_url and request._parsed_url.port is not None:
            server_port = request._parsed_url.port.decode('ascii')
        elif len(split_host) > 1:
            server_port = split_host[1]
        else:
            server_port = '80'  # TODO: Find a better way of determining the port number when not provided
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

    @staticmethod
    def get_request_scheme(request):
        try:
            if request.headers.get('upgrade') == 'websocket':
                scheme = b'ws'
            elif request.transport.get_extra_info('sslcontext'):
                scheme = b'https'
            else:
                scheme = b'http'
        except (AttributeError, KeyError):
            scheme = b'http'
        return scheme

    def _get_application_by_route(self, request, use_host=False):
        host = request.headers.get('Host', '')
        scheme = self.get_request_scheme(request)
        path = request._parsed_url.path
        port = request._parsed_url.port
        query_string = request._parsed_url.query
        fragment = request._parsed_url.fragment
        userinfo = request._parsed_url.userinfo
        script = path
        if ':' in host and port is None:
            (host, port) = host.split(':', 1)[0:2]
            port = port.encode('ascii')
        host_bytes = host.encode('utf-8')

        if use_host:
            script = b'%s%s' % (host_bytes, script)
        path_info = b''
        while b'/' in script:
            script_str = script.decode('utf-8')
            try:
                application = self.mounts[script_str]
                break
            except KeyError:
                pass
            script, last_item = script.rsplit(b'/', 1)
            path_info = b'/%s%s' % (last_item, path_info)
        else:
            script_str = script.decode('utf-8')
            application = self.mounts.get(script_str, None)
        if application is not None:
            request._parsed_url = SanicCompatURL(scheme, host_bytes, port,
                                                 path_info, query_string, fragment, userinfo)
            request.parsed_args = None  # To trigger re-parse args
            path = request.path
        return application, script_str, path

    async def __call__(self, request, write_callback, stream_callback):
        # Assume at this point that we have no app. So we cannot know if we are on Websocket or not.
        if self.hosts and len(self.hosts) > 0:
            application, script, path = self._get_application_by_route(request, use_host=True)
            if application is None:
                application, script, path = self._get_application_by_route(request, use_host=False)
        else:
            application, script, path = self._get_application_by_route(request)
        if application is None:  # no child matches, call the parent
            return await self.parent_handle_request(request, write_callback, stream_callback)

        real_write_callback = write_callback
        real_stream_callback = stream_callback
        response = False
        streaming_response = False
        def _write_callback(child_response):
            nonlocal response
            response = child_response

        def _stream_callback(child_stream):
            nonlocal streaming_response
            streaming_response = child_stream

        replaced_write_callback = _write_callback
        replaced_stream_callback = _stream_callback
        parent_app = self.parent_app
        if application.apply_middleware and parent_app.request_middleware:
            request.app = parent_app
            for middleware in parent_app.request_middleware:
                response = middleware(request)
                if isawaitable(response):
                    response = await response
                if response:
                    break
        if not response and not streaming_response:
            if isinstance(application, WsgiApplication):  # child is wsgi_app
                self._call_wsgi_app(script, path, request, application.app, replaced_write_callback)
            else:  # must be a sanic application
                request.app = None  # Remove parent app from request to child app
                await application.app.handle_request(request, replaced_write_callback, replaced_stream_callback)

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
        if streaming_response:
            return real_stream_callback(streaming_response)
        return real_write_callback(response)


class SanicDispatcherMiddlewareController(object):
    __slots__ = ['parent_app', 'parent_handle_request', 'applications', 'url_prefix', 'filter_host', 'hosts']

    def __init__(self, app, url_prefix=None, host=None):
        """
        :param Sanic app:
        :param url_prefix:
        """
        self.parent_app = app
        self.applications = {}
        self.url_prefix = None if url_prefix is None else str(url_prefix).rstrip('/')
        self.hosts = set()
        if host:
            self.filter_host = host
            self.hosts.add(host)
        else:
            self.filter_host = None
        # Woo, monkey-patch!
        self.parent_handle_request = app.handle_request
        self.parent_app.handle_request = self.handle_request

    def _determine_uri(self, url_prefix, host=None):

        uri = ''
        if self.url_prefix is not None:
            uri = self.url_prefix
        if host is not None:
            uri = str(host) + uri
            self.hosts.add(host)
        elif self.filter_host is not None:
            uri = str(self.filter_host) + uri
        uri += url_prefix
        return uri

    def register_sanic_application(self, application, url_prefix, host=None, apply_middleware=False):
        """
        :param Sanic application:
        :param url_prefix:
        :param host:
        :param apply_middleware:
        :return:
        """
        assert isinstance(application, Sanic), "Pass only instances of Sanic to register_sanic_application."
        if str(url_prefix).endswith('/'):
            url_prefix = url_prefix[:-1]
        if host is not None and isinstance(host, (list, set)):
            for _host in host:
                self.register_sanic_application(application, url_prefix, host=_host,
                                                apply_middleware=apply_middleware)
                return

        registered_service_url = self._determine_uri(url_prefix, host)
        self.applications[registered_service_url] = SanicApplication(application, apply_middleware)
        self._update_request_handler()

    def register_wsgi_application(self, application, url_prefix, host=None, apply_middleware=False):
        """
        :param application:
        :param url_prefix:
        :param apply_middleware:
        :return:
        """
        if host is not None and isinstance(host, (list, set)):
            for _host in host:
                self.register_wsgi_application(application, url_prefix, host=_host,
                                               apply_middleware=apply_middleware)
                return

        registered_service_url = self._determine_uri(url_prefix, host)
        self.applications[registered_service_url] = WsgiApplication(application, apply_middleware)
        self._update_request_handler()

    def unregister_application(self, application, all_matches=False):
        if isinstance(application, (SanicApplication, WsgiApplication)):
            application = application.app
        urls_to_unregister = []
        for url, reg_application in self.applications.items():
            if reg_application.app == application:
                urls_to_unregister.append(url)
                if not all_matches:
                    break
        for url in urls_to_unregister:
            del self.applications[url]
        self._update_request_handler()

    def unregister_prefix(self, url_prefix):
        registered_service_url = ''
        if self.url_prefix is not None:
            registered_service_url += self.url_prefix
        registered_service_url += url_prefix
        try:
            del self.applications[registered_service_url]
        except KeyError:
            pass
        self._update_request_handler()

    def _update_request_handler(self):
        """
        Rebuilds the SanicDispatcherMiddleware every time a new application is registered
        :return:
        """
        dispatcher = SanicDispatcherMiddleware(self.parent_app, self.parent_handle_request, self.applications,
                                               self.hosts)
        self.parent_app.handle_request = dispatcher

    async def handle_request(self, request, write_callback, stream_callback):
        """
        This is only called as a backup handler if _update_request_handler was not yet called.
        :param request:
        :param write_callback:
        :param stream_callback:
        :return:
        """
        dispatcher = SanicDispatcherMiddleware(self.parent_app, self.parent_handle_request, self.applications,
                                               self.hosts)
        self.parent_app.handle_request = dispatcher  # save it for next time
        retval = dispatcher(request, write_callback, stream_callback)
        if isawaitable(retval):
            retval = await retval
        return retval
