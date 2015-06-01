#!/usr/bin/env python

from setuptools import setup
from codecs import open
from os import path

from dota2 import __version__

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='dota2',
    version=__version__,
    description='Provies wrapper objects for working with Dota2',
    long_description=long_description,
    url='https://github.com/ValvePython/dota2',
    author='Rossen Georgiev',
    author_email='hello@rgp.io',
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing ',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='valve dota dota2 stats statistics',
    packages=['dota2'],
    install_requires=[
        "vpk",
        "vdf",
    ],
    zip_safe=True,
)
