#! python3
"""Gnuplot wrapper for py3k.
"""
from subprocess import Popen, PIPE
import warnings
import tempfile
import os
import wx
import numpy as np

from . import framework as mwx
from .controls import ControlPanel


class Gnuplot:
    """Gnuplot backend - gnuplot pipe wrapper.
    """
    debug = 0
    
    PGNUPLOT = "gnuplot" # Note: gnuplot/pgnuplot is integrated
    
    @staticmethod
    def init_path(path):
        if not os.path.isdir(path):
            print("- {!r} is not a directory.".format(path))
            return False
        os.environ['PATH'] = "{};{}".format(path, os.environ['PATH'])
    
    def __init__(self, startup="__init__.plt", debug=0):
        print("Launching new gnuplot...")
        self.__gnuplot = Popen([self.PGNUPLOT],
                               shell=True, stdin=PIPE)
        
        self.data_format = "{:e}".format
        self.startupfile = startup or ""
        self.tempfile = tempfile.mktemp()
        self.debug = debug
        self.reset()
    
    def __del__(self):
        print("bye gnuplot...")
        self.terminate()
        if os.path.isfile(self.tempfile):
            os.remove(self.tempfile)
    
    def __call__(self, text):
        for cmd in filter(None, (t.strip() for t in text.splitlines())):
            self.__gnuplot.stdin.write((cmd + '\n').encode())
            if self.debug:
                print("pgnupot>", cmd)
        self.__gnuplot.stdin.flush()
        return self
    
    def plot(self, *args):
        if isinstance(args[0], str): # text command
            pcmd = [v.strip() for v in args]
            if pcmd[-1].endswith(','):
                pcmd[-1] = pcmd[-1][:-1]
            
        ## multiplot with args = (x1, y1[,opt]), (x2, y2[,opt]), ...
        elif all((type(x) is tuple) for x in args):
            pcmd = []
            with open(self.tempfile, 'w') as o:
                for i, arg in enumerate(args):
                    data = arg[:2]
                    opt = arg[2] if len(arg) > 2 else "w l"
                    for v in zip(*data):
                        o.write('\t'.join(self.data_format(x) for x in v) + '\n')
                    o.write('\n\n')
                    pcmd.append("tempfile index {}:{} {}".format(i, i, opt))
            
        ## plot with args = (axis, y1[,opt], y2[,opt], ...)
        else:
            axis, args = args[0], args[1:]
            data, opts = [], []
            for v in args:
                if not isinstance(v, str):
                    data.append(v)
                    if len(data) - len(opts) > 1: # opts 指定が省略されたのでデフォルト指定
                        opts.append("w l")
                else:
                    opts.append(v)
            
            while len(data) > len(opts): # opts 指定の数が足りない場合 (maybe+1)
                opts.append("w l")
            
            pcmd = ["tempfile using 1:{} {}".format(j+2,opt) for j,opt in enumerate(opts)]
            data = np.vstack((axis, data))
            with open(self.tempfile, 'w') as o:
                for v in data.T:
                    o.write('\t'.join(self.data_format(x) for x in v) + '\n')
        
        self("plot " + ', '.join(pcmd))
    
    def terminate(self):
        if self.__gnuplot is not None:
            try:
                self('q')
                ## self.__gnuplot.kill()
                outs, errs = self.__gnuplot.communicate()
            except Exception:
                pass
            self.__gnuplot = None
    
    def restart(self):
        self.terminate()
        self.__init__(self.startupfile)
    
    def reset(self, startup=None):
        if startup:
            self.startupfile = startup
        if self.startupfile:
            self("load '{}'".format(self.startupfile))
        self("tempfile = '{}'".format(self.tempfile))
    
    def wait(self, msg=""):
        input(msg + " (Press ENTER to continue)")
    
    def edit(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            Popen("notepad {}".format(self.startupfile))


class GnuplotFrame(mwx.Frame):
    """Gnuplot frontend frame.
    """
    def __init__(self, *args, **kwargs):
        mwx.Frame.__init__(self, *args, **kwargs)
        
        self.gnuplot = Gnuplot()
        self.panel = ControlPanel(self)
        
        self.menubar["Edit"] = [
            (wx.ID_COPY, "&Copy params\tCtrl-c", "Copy params to clipboard",
                lambda v: self.panel.copy_to_clipboard()),
                
            (wx.ID_PASTE, "&Paste params\tCtrl-v", "Read params from clipboard",
                lambda v: self.panel.paste_from_clipboard()),
            (),
            (wx.ID_RESET, "&Reset params\tCtrl-n", "Reset params to ini-value",
                lambda v: self.panel.reset_params()),
        ]
        self.menubar["Gnuplot"] = [
            (mwx.ID_(80), "&Gnuplot setting\tCtrl-g", "Edit settings",
                lambda v: self.gnuplot.edit()),
                
            (mwx.ID_(81), "&Reset gnuplot\tCtrl-r", "Reset setting",
                lambda v: self.gnuplot.reset()),
            (),
            (mwx.ID_(82), "Restart gnuplot", "Restart process",
                lambda v: self.gnuplot.restart()),
        ]
        self.menubar.reset()
    
    def Destroy(self):
        del self.gnuplot
        return mwx.Frame.Destroy(self)
