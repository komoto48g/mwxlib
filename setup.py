#! python3
from setuptools import setup 
from Lib.mwx import __version__, __author__

## __version__ = "0.69.0rc4" #  TestPyPI

setup(
    name = "mwxlib",
    version = __version__,
    author = __author__,
    author_email = "komoto@jeol.co.jp",
    description = "A wrapper of matplotlib and wxPython (phoenix)",
    
    url = "https://github.com/komoto48g/mwxlib",
    
    ## long_description_content_type = "text/markdown",
    ## long_description = open('README.md').read(),
    
    long_description = open('README.rst').read(),
    
    ## Description of the package in the distribution
    package_dir = {
        '' : 'Lib' # root packages is `Lib`, i.e., mwx package is in ./Lib
    },
    
    ## Packing all modules in mwx package
    packages = [
        'mwx',
        'mwx.py',
    ],
    
    ## install_requires = open("requirements.txt").read().splitlines(),
    install_requires = [
        'wxpython',
        'numpy',
        'scipy',
        'pillow',
        'matplotlib',
        'opencv-python',
    ],
    
    ## This is necessary for egg distribution to include *.txt files
    package_data = {
        "mwx": [
            # no *.txt files to be included
        ],
    },
    include_package_data = True,
    
    ## License and classifiers for PyPi distribution
    license = 'MIT',
    
    classifiers = [
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering :: Image Processing',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
