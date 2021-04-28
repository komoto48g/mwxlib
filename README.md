# mwxlib

My python package based on matplotlib/wx


## Overview


## Features


## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

- Python 2.7
- Python 3.x
    - numpy
    - pillow
    - matplotlib
    - wxpython==4.0.7

### Installing

Beofre installing, you can check how mwxlib works.
Enter the src directory (mwxlib/Lib/mwx), and type
```
$ py -3 -m framework (cf. framework is the mastar source of mwxlib)
```

To install, enter the root directory (./mwxlib), then type
```
$ py -3 setup.py install
```

To install from GitHub, type
```
$ py -3 -m pip install git+https://github.com/komoto48g/mwxlib.git
```

### How to use

```python
>>> from mwx import deb
>>> deb()
```

The more pragmatic sample is 'debut.py'.
Enjoy diving!

### Uninstalling
<!--
```sh
$ py -3 setup.py install --record files.txt
$ cat files.txt | xargs rm -rf
```
次のやつでＯＫぽい
-->
```sh
$ pip uninstall mwxlib
```



## Authors

* Kazuya O'moto - *Initial work* -

See also the list of who participated in this project.


## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details
