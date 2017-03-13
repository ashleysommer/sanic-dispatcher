# -*- coding: utf-8 -*-
"""
    setup
    ~~~~
    A Dispatcher extension for Sanic which also acts as a Sanic-to-WSGI adapter

    :copyright: (c) 2017 by Ashley Sommer (based on DispatcherMiddleware in Workzeug).
    :license: MIT, see LICENSE for more details.
"""

from setuptools import setup
from os.path import join, dirname

with open(join(dirname(__file__), 'sanic_dispatcher/version.py'), 'r') as f:
    exec(f.read())

with open(join(dirname(__file__), 'requirements.txt'), 'r') as f:
    install_requires = f.read().split("\n")

setup(
    name='Sanic-Dispatcher',
    version=__version__,
    url='https://github.com/ashleysommer/sanic-dispatcher',
    license='MIT',
    author='Ashley Sommer',
    author_email='ashleysommer@gmail.com',
    description="Multi-application dispatcher based on DispatcherMiddleware from the Werkzeug Project.",
    long_description=open('README.md').read(),
    packages=['sanic_dispatcher'],
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    install_requires=install_requires,
    tests_require=[
        'nose'
    ],
    test_suite='nose.collector',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
