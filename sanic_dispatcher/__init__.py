# -*- coding: utf-8 -*-
"""
    sanic_dispatcher
    ~~~~

    :copyright: (c) 2017 by Ashley Sommer (based on DispatcherMiddleware in the Werkzeug Project).
    :license: MIT, see LICENSE for more details.
"""
from .extension import SanicDispatcherMiddleware, SanicDispatcherMiddlewareController
from .version import __version__

__all__ = ['SanicDispatcherMiddleware', 'SanicDispatcherMiddlewareController']

