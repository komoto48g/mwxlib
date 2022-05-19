#! python3
# -*- coding: utf-8 -*-
"""Gnuplot wrapper for py3k

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from subprocess import Popen, PIPE
import warnings
import tempfile
import shutil
import sys
import os
import wx
import numpy as np
try:
    import framework as mwx
    from controls import ControlPanel
except:
    from . import framework as mwx
    from .controls import ControlPanel


class Gnuplot(object):
    """Gnuplot - gnuplot:pipe wrapper
    """
    debug = 0
    data_format = "{:e}".format
    
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
        for t in text.splitlines():
            cmd = t.strip()
            if cmd:
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
                    pcmd.append("temp index {}:{} {}".format(i, i, opt))
            
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
            
            pcmd = ["temp using 1:{} {}".format(j+2,opt) for j,opt in enumerate(opts)]
            data = np.vstack((axis, data))
            with open(self.tempfile, 'w') as o:
                for v in data.T:
                    o.write('\t'.join(self.data_format(x) for x in v) + '\n')
            
        ## self("temp = '{}'".format(self.tempfile))
        self("plot " + ', '.join(pcmd))
    
    def terminate(self):
        if self.__gnuplot is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                try:
                    self('q')
                    ## self.__gnuplot.kill()
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
        self("temp = '{}'".format(self.tempfile)) # set temp:parameter
    
    def wait(self, msg=""):
        input(msg + " (Press ENTER to continue)")
    
    def edit(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            Popen("notepad {}".format(self.startupfile))


class GnuplotFrame(mwx.Frame):
    """Gnuplot Frame
    
    Attributes:
        gnuplot : single class object
    """
    gnuplot = property(lambda self: self.__gplot)
    
    def __init__(self, *args, **kwargs):
        mwx.Frame.__init__(self, *args, **kwargs)
        
        self.__gplot = Gnuplot()
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
                lambda v: self.edit_gnuplot()),
                
            (mwx.ID_(81), "&Reset gnuplot\tCtrl-r", "Reset setting",
                lambda v: self.reset_gnuplot()),
            (),
            (mwx.ID_(82), "Restart gnuplot", "Restart process",
                lambda v: self.restart_gnuplot()),
        ]
        self.menubar.reset()
    
    def edit_gnuplot(self):
        self.gnuplot.edit()
    
    def reset_gnuplot(self):
        self.gnuplot.reset()
    
    def restart_gnuplot(self):
        self.gnuplot.restart()
    
    def Destroy(self):
        del self.__gplot
        return mwx.Frame.Destroy(self)


## for backward compatibility
## Gplot = Gnuplot
## GplotFrame = GnuplotFrame


if __name__ == "__main__":
    Gnuplot.PGNUPLOT = "pgnuplot"
    Gnuplot.init_path("C:/usr/home/bin/gnuplot-4.4/binary")


if __name__ == "__main__":
    from numpy import pi,sin,cos
    
    gp = Gnuplot(None, debug=1)
    X = np.arange(0,2,0.1) * pi
    
    print("\n>>> 数式のプロット 1")
    gp.plot(X, sin(X), "title 'sin' w lp")
    gp.wait()
    
    print("\n>>> 数式のプロット 2")
    gp.plot((X, sin(X), "title 'sin' w lp"),
            (X/2, cos(X), "title 'cos' w lp lt 2 ps 0.5"),
            (cos(X), sin(X), "title 'circ' w lp lt 5 ps 0.5"),
    )
    gp.wait()
    
    print("\n>>> 数式のプロット 3")
    gp.plot(X, sin(X), "title 'sin' w lp",
               cos(X), "title 'cos' w lp lt 5 ps 0.5",
               np.sqrt(X),
    )
    gp.wait()
    
    print("\n>>> ファイル出力＋プロット")
    data = np.vstack((X, sin(X), cos(X)))
    np.savetxt(gp.tempfile, data.T, fmt='%f')
    ## with open(gp.tempfile, 'w') as o:
    ##     for v in data.T:
    ##         print('\t'.join("{:g}".format(x) for x in v), file=o)
    gp("f = '{}'".format(gp.tempfile)) # set local parameter
    gp.plot(
        "f using 1:2 w lp",
        "f using 1:3 w lp",
    )
    gp.wait()


if __name__ == "__main__":
    from numpy import pi
    from mwx.controls import LParam
    
    class TestFrame(GnuplotFrame):
        def __init__(self, *args, **kwargs):
            GnuplotFrame.__init__(self, *args, **kwargs)
            
            self.params = (
                LParam('Amp', (-1, 1, 1e-3), 0, "%8.3e"),
                LParam('k',   (0, 2, 1./100), 1, "%g"),
                LParam('φ',  (-pi, pi, pi/100), 0, "%G"),
            )
            for lp in self.params:
                lp.bind(self.plot)
            
            self.panel.layout(self.params,
                row=1, expand=1, type='slider', cw=-1, lw=32)
            
            self.reset_gnuplot()
        
        def reset_gnuplot(self):
            self.gnuplot.reset()
            self.gnuplot("set yrange [-1:1]")
        
        def plot(self, par):
            a, k, p = [x.value for x in self.params]
            x = np.arange(0, 10, 0.01)
            y = a * np.sin(k * (x- p))
            data = np.vstack((x, y))
            try:
                ## self.gnuplot("plot [:] [-1:1] "
                ##              "{:f} * sin({:f} * (x - {:f}))".format(a,k,p))
                
                ## self.gnuplot.plot(x, y, "title 'y' w l lt 1")
                
                temp = self.gnuplot.tempfile
                np.savetxt(temp, data.T)
                if 1: # 連続書き込み時の読み取りをできるだけ同期する
                    dst = r"C:\temp\mgplt-temp.out"
                    shutil.copyfile(temp, dst)
                else:
                    dst = temp
                self.gnuplot.plot("'{}' using 1:2 title 'y' w l lt 1".format(dst))
            except Exception as e:
                print(e)
                self.statusbar.write("gnuplot fail, try to restart.")
                self.gnuplot.restart()
    
    app = wx.App()
    frm = TestFrame(None)
    frm.Fit()
    frm.Show()
    frm.SetFocus()
    app.MainLoop()
