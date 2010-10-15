#!/usr/bin/env python

from distutils.core import setup, Extension


luabject = Extension('luabject._luabject',
                     libraries=['lua'],
                     sources=['src/luabject.cpp'])

setup(
    name='luabject',
    version='1.0',
    packages=['luabject'],
    ext_modules=[luabject],
    requires=['greenlet', 'eventlet'],
)
