#! python
# -*- coding: utf-8 -*-
from setuptools import setup 
from Lib.mwx import __version__, __author__

try:
    with open('README.md', encoding='utf-8') as f:
        readme = f.read()
except IOError:
    readme = ''

setup(
    name = "mwxlib",
    version = __version__,
    author = __author__,
    author_email = "komoto@jeol.co.jp",
    description = "An wrapper of matplotlib and wxPython (phoenix)",
    
    long_description = readme,
    long_description_content_type = "text/markdown",
    
    ## Description of the package in the distribution
    package_dir = {
        '' : 'Lib' # root packages is `Lib`, i.e., mwx package is in ./Lib
    },
    
    ## Packing all modules in mwx package
    packages = [
        'mwx',
    ],
    
    install_requires = [
        'numpy',
        'scipy',
        'pillow',
        'matplotlib',
        'wxpython',
        'opencv-python',
    ],
    
    ## This is necessary for egg distribution to include *.txt files
    package_data={
        "mwx": [
        ],
    },
    
    include_package_data = True,
    
    license = 'MIT',
    
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Scientific/Engineering :: Image Processing',
        'Topic :: System :: Shells',
    ],
    ## entry_points = {
    ##     'console_scripts': ['mwxlib = mwx.framework:deb']
    ## },
)
