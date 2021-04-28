#! python
# -*- coding: utf-8 -*-
from setuptools import setup 
from Lib.mwx import __version__, __author__

setup(
    name = "mwxlib",
    version = __version__,
    author = __author__,
    author_email = "komoto@jeol.co.jp",
    description = "An wrapper of matplotlib and wxPython (phoenix)",
    
    ## Description of the package in the distribution
    package_dir = {
        '' : 'Lib' # root packages is `Lib`, i.e., mwx package is in ./Lib
    },
    
    ## Packing all modules in mwx package
    packages = [
        'mwx',
    ],
    
    ## install_requires = [
    ##     'numpy',
    ##     'pillow',
    ##     'matplotlib',
    ##     'wxpython==4.0.7',
    ## ],
    
    include_package_data = True,
)
