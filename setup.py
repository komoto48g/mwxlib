#! python3
from setuptools import setup
import os


def get_version(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    fn = os.path.join(here, rel_path)
    with open(fn, encoding='utf-8', newline='') as fp:
        for line in fp:
            if line.startswith('__version__'):
                delim = '"' if '"' in line else "'"
                return line.split(delim)[1]
        else:
            raise RuntimeError("Unable to find version string.")

## __version__ = "1.0rc"  # TestPyPI
__version__ = get_version("Lib/mwx/framework.py")


setup(
    name = "mwxlib",
    version = __version__,
    author = "Kazuya O'moto",
    author_email = "komoto@jeol.co.jp",
    description = "A wrapper of matplotlib and wxPython (phoenix)",
    
    url = "https://github.com/komoto48g/mwxlib",
    
    long_description = open("README.md").read(),
    long_description_content_type = "text/markdown",
    
    ## Description of the package in the distribution
    package_dir = {
        "" : "Lib" # root packages is `Lib`, i.e., mwx package is in ./Lib
    },
    
    ## Packing all modules in mwx package
    packages = [
        "mwx",
        "mwx.py",
        "mwx.plugins",
    ],
    
    install_requires = open("requirements.txt").read().splitlines(),
    
    ## This is necessary for egg distribution to include *.txt files
    package_data = {
        "mwx": [
            # no *.txt files to be included
        ],
    },
    include_package_data = True,
    
    ## License and classifiers for PyPi distribution
    license = "MIT",
    
    classifiers = [
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Image Processing",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
