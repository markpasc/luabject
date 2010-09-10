#!/usr/bin/env python

from distutils.core import setup, Extension


luabject = Extension('village._luabject',
                     libraries=['lua'],
                     sources=['src/luabject.c'])

setup(
    name='village',
    version='1.0',
    packages=['village'],
    scripts=['bin/villaged'],
    ext_modules=[luabject],
)
