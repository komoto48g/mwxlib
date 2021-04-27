#! python
# -*- coding: utf-8 -*-
from setuptools import setup 
from Lib.mwx import __version__

setup(
    name = "mwxlib",
    version = __version__,
    author = "Kazuya O'moto",
    author_email = "komoto@jeol.co.jp",
    description = "An wrapper of wxPython (phoenix)",
    
    ## Description of the package in the distribution
    package_dir = {
        '' : 'Lib' # root packages is `Lib`, i.e., mwx package is in ./Lib
    },
    
    ## Packing all modules in mwx package
    packages = [
        'mwx',
    ],
    
    ## install_requires = [
    ##     'wxPython',
    ##     'scipy',
    ##     'Pillow',
    ##     'matplotlib',
    ##     'opencv-python',
    ## ],
    
    include_package_data = True,
)
