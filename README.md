# mwxlib

Python package based on matplotlib/wx
and wxPython shell extension library

See [Demo Script and Gallery](./demo/readme.md).


## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

- ~~Python 2.7~~ (PY2 support has ended since 0.50)
- Python 3.5 or later
    - numpy
    - pillow
    - matplotlib
    - wxpython >= 4.0.7

### Installing

If you want to check how mwxlib works before installation,
enter the directory ~/Lib/mwx/ and type:
```
py -3 -m framework
```
To install, type:
```
py -3 -m pip install mwxlib
```
To install latest version from GitHub, type:
```
py -3 -m pip install git+https://github.com/komoto48g/mwxlib.git
```

### How to use

```
>>> import mwx; mwx.deb()
```

:memo: mwxlib creates "~/.mwxlib/" in your *HOME* directory.
This includes history, logs, dump files used to check when an error occurs.

:memo: At the first startup, it takes some time to collect module information and create a dictionary file.
The collected module name is used for completion at the time of input in the shell.
(If you start the shell while pressing [C-S-], the dictionary file will be recreated)

### Uninstalling
```
pip uninstall mwxlib
```


# Features

![intro](doc/image/intro.gif)
The animation shows how the Nautilus works, which is embedded in a simple PyEditor app.

As you are diving into the python process,
you can watch, inspect, and change everything in the target.


## Nautilus in the Shell

The framework has an extended class based on wx.py.shell.Shell named Nautilus,
which has the following features:

1. Auto-completion and apropos functions are reinfoced.
    - [1] history-comp-mode
    - [2] word-comp-mode
    - [3] apropos-comp-mode
    - [4] text-comp-mode
    - [5] module-comp-mode
2. Objective magic syntax is implemented.
    - [ ` ] quoteback
    - [@] pullback
3. Powerful inspectoin utillities are compiled.
    - Filling
    - InspectionTool
    - Ghost in the shell

**All objects in the process can be accessed using,**
```
    self : the target of the shell,
    this : the module which includes target.
```

**It is very easy to include the shell in your wxPython application.**
```
>>> self.inspector = mwx.ShellFrame(self, target=self)
```


## Autocomp key bindings:
        C-up : [0] retrieve previous history
      C-down : [0] retrieve next history
    M-j, C-j : [0] call tooltip of eval (for the word selected or focused)
    M-h, C-h : [0] call tooltip of help (for the func selected or focused)
         TAB : [1] history-comp-mode
         M-p : [1] retrieve previous history in comp-mode
         M-n : [1] retrieve next history in comp-mode
         M-. : [2] word-comp-mode
         M-/ : [3] apropos-comp-mode
         M-, : [4] text-comp-mode
         M-m : [5] module-comp-mode
  * All completions [1--5] are incremental when pressed any alnums, and decremental when backspace.  
See [key bindings](key-bindings.md) for more information.

<!--
![autocomp](doc/image/autocomp.gif)
-->


## Magic syntax:

  - quoteback : ```x`y --> y=x  | x`y`z --> z=y=x```

  - pullback : ```x@y --> y(x) | x@y@z --> z(y(x))```

  - apropos : ```x.y? [not] p => shows apropos &optional (not-)matched by p:predicates```
                equiv. apropos(y, x [,ignorecase ?:True,??:False] [,pred=p])
                y can contain regular expressions.
                    (RE) \\a:[a-z], \\A:[A-Z] can be used in addition.
                p can be ?atom, ?callable, ?instance(*types), and
                    predicates imported from inspect
                    e.g., isclass, ismodule, ismethod, isfunction, etc.
  
  * info :  ?x (x@?) --> info(x) shows short information
  * help : ??x (x@??) --> help(x) shows full description
  * sx   :  !x (x@!) --> sx(x) executes command in external shell
    
    Note: The last three (*) are original syntax defined in wx.py.shell,
    at present version, enabled with USE_MAGIC switch being on

<!--
![apropos](doc/image/apropos.gif)
-->


## built-in utility:

    @p          synonym of print
    @pp         synonym of pprint
    @info   @?  short info
    @help   @?? full description
    @dive       clone the shell with new target
    @timeit     measure the duration cpu time
    @profile    profile the func(*args, **kwargs)
    @filling    inspection using wx.lib.filling.Filling
    @watch      inspection using wx.lib.inspection.InspectionTool
    @edit       open file with your editor (undefined)
    @where      filename and lineno or module
    @debug      open pdb or show event-watcher and widget-tree

<!--
![utils-mod](doc/image/utils-mod.gif)
-->


## Ghost in the shell

The Ghost in the shell (g.i.t.s) is the help system for divers,
which is a notebook-style window consists of four editors:
- scratch buffer
    + a temporary buffer used as big-tooltip
- Help buffer
    + for piping text from help() and info()
- Logging buffer
    + for logging Clipboard communication across the shell
    + free memo space
- History buffer
    + read-only buffer of the input-history

<!--
![utils-ghost](doc/image/utils-ghost.gif)
The animation shows how to inspect *blurring*-functions of OpenCV.
-->


## Authors

* Kazuya O'moto - *Initial work* -

See also the list of who participated in this project.


## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details
