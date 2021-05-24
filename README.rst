Project description
===================

Welcome to mwxlib project!
The mwxlib is the Python package based on matplotlib/wx and wxPython shell extension.

For more information please refer to the `Readme file <https://github.com/komoto48g/mwxlib>`_ and demos.


How to use
----------

mwx.deb is wx.py.shell-base inspector used for debugging in the target process.

::

   >>> from mwx import deb
   >>> deb()

It is very easy to include the shell in your wxPython application.

::

    >>> import mwx
    >>> self.inspector = mwx.InspectorFrame(self, target=self)

As you are diving into the python process, you can watch, inspect, and change everything in the target.
The more pragmatic sample is 'debut.py' included in the `repository <https://github.com/komoto48g/mwxlib>`_.

Enjoy diving!

:memo:
    mwxlib creates ~/.deb/ in your home directory. 
    This includes history, logs, dump files used to report when an error occurs.

:memo:
    At the first startup, it takes some time to collect module information and create a dictionary. 
    The collected module name is used for completion at the time of input in the shell.
    If you start the shell while pressing [C-S-], the dictionary will be recreated.
