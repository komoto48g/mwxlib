#! python3
# -*- coding: utf-8 -*-
"""Graphical debugger
 of the phoenix, by the phoenix, for the phoenix

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import
from functools import wraps
from pdb import Pdb, bdb
import linecache
import inspect
import wx
from wx.py.filling import FillingFrame


def echo(f):
    @wraps(f)
    def _f(*args, **kwargs):
        if echo.debug > 0:
            print("<{!r}>".format(f.__name__))
        return f(*args, **kwargs)
    return _f
echo.debug = 0


class Debugger(Pdb):
    """Graphical debugger with extended Pdb
    
Attributes:
    viewer : Py.filling frame to display locals
    logger : ShellFrame Log
     shell : Nautilus in the ShellFrame
      busy : The flag of being running now (eq. when module is not None)
   verbose : Activates verbose mode in which default messages are output from Pdb.
    module : The module of the currently stacked frame on Pdb
    locals : The namespace of the currently stacked frame on Pdb
   globals : (ditto)

Args:
    inspector : Inspector frame of the shell

Note:
    + set_trace -> reset -> set_step -> sys.settrace
                   reset -> forget
    > user_line
    > bp_commands
    > interaction -> setup -> execRcLines
    > print_stack_entry
    > preloop
        - cmd:cmdloop --> stdin.readline
    (Pdb)
    > postloop
        - user_line
        - user_call
        - user_return
        - user_exception -> interaction
    [EOF]
    """
    indent = "  "
    prefix1 = "> "
    prefix2 = "--> "
    verbose = False
    logger = property(lambda self: self.inspector.Log)
    shell = property(lambda self: self.inspector.shell)
    busy = property(lambda self: self.module is not None)
    
    def __init__(self, inspector, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.inspector = inspector
        self.prompt = self.indent + '(Pdb) ' # (overwrite)
        self.skip = [self.__module__, 'bdb', 'pdb'] # (overwrite) skip this module
        self.locals = {}
        self.globals = {}
        self.viewer = None
        self.module = None
        ## self.stdin = self.shell.interp.stdin
        ## self.stdiout = self.shell.interp.stdout
    
    def open(self, frame=None):
        if self.busy:
            return
        self.module = None # inspect.getmodule(frame)
        self.viewer = FillingFrame(rootObject=self.locals,
                                   rootLabel='locals',
                                   static=False, # update each time pushed
                                   )
        self.viewer.filling.text.WrapMode = 0
        self.viewer.filling.text.Zoom = -1
        self.viewer.Show()
        self.logger.clear()
        self.logger.Show()
        self.shell.SetFocus()
        self.shell.redirectStdin()
        self.shell.redirectStdout()
        wx.CallAfter(wx.EndBusyCursor) # cancel the egg timer
        ## wx.CallAfter(self.shell.Execute, 'step') # step into the target
        self.set_trace(frame)
    
    def close(self):
        if self.busy:
            self.set_quit()
        if self.viewer:
            self.viewer.Close()
        self.viewer = None
        self.module = None
        self.locals.clear()
        self.globals.clear()
    
    def trace(self, target, *args, **kwargs):
        if not callable(target):
            print("- cannot break {!r} (not callable)".format(target))
            return
        if inspect.isbuiltin(target):
            print("- cannot break {!r}".format(target))
            return
        if self.busy:
            wx.MessageBox("Debugger is running\n\n"
                          "Enter [q]uit to exit before closing.")
            return
        try:
            self.shell.handler('debug_begin')
            self.open(inspect.currentframe())
            target(*args, **kwargs)
        except bdb.BdbQuit:
            pass
        finally:
            self.close()
            self.shell.handler('debug_end')
    
    def message(self, msg, indent=-1):
        """(override) Add indent to msg"""
        prefix = self.indent if indent < 0 else ' ' * indent
        print(prefix + str(msg), file=self.stdout)
    
    def trace_pointer(self, frame, lineno):
        self.logger.MarkerDeleteAll(3)
        self.logger.MarkerAdd(lineno-1, 3) # (->) pointer
        self.logger.goto_char(self.logger.PositionFromLine(lineno-1))
        wx.CallAfter(self.logger.recenter)
    
    @echo
    def print_stack_entry(self, frame_lineno, prompt_prefix=None):
        """Print the stack entry frame_lineno (frame, lineno).
        (override) Change prompt_prefix; Add trace pointer.
        """
        self.trace_pointer(*frame_lineno) # for jump
        
        if not self.verbose:
            return
        if prompt_prefix is None:
            prompt_prefix = '\n' + self.indent + self.prefix2
        
        ## Pdb.print_stack_entry(self, frame_lineno, prompt_prefix)
        frame, lineno = frame_lineno
        if frame is self.curframe:
            prefix = self.indent + self.prefix1
        else:
            prefix = self.indent
        self.message(prefix
          + self.format_stack_entry(frame_lineno, prompt_prefix), indent=0)
    
    ## --------------------------------
    ## Override Bdb methods
    ## --------------------------------
    
    ## @echo
    ## def trace_dispatch(self, frame, event, arg):
    ##     return Pdb.trace_dispatch(self, frame, event, arg)
    
    @echo
    def set_until(self, frame, lineno=None):
        return Pdb.set_until(self, frame, lineno)
    
    @echo
    def set_step(self):
        return Pdb.set_step(self)
    
    @echo
    def set_next(self, frame):
        return Pdb.set_next(self, frame)
    
    @echo
    def set_return(self, frame):
        return Pdb.set_return(self, frame)
    
    @echo
    def set_trace(self, frame=None):
        return Pdb.set_trace(self, frame)
    
    @echo
    def set_continue(self):
        return Pdb.set_continue(self)
    
    @echo
    def clear_break(self, filename, lineno):
        return Pdb.clear_break(self, filename, lineno)
    
    @echo
    def clear_all_breaks(self):
        return Pdb.clear_all_breaks(self)
    
    @echo
    def set_break(self, filename, lineno, *args, **kwargs):
        self.logger.MarkerAdd(lineno-1, 1) # new breakpoint
        return Pdb.set_break(self, filename, lineno, *args, **kwargs)
    
    @echo
    def set_quit(self):
        ## if self.verbose:
        ##     print("+ all stacked frame")
        ##     for frame_lineno in self.stack:
        ##         self.message(self.format_stack_entry(frame_lineno))
        self.module = None
        return Pdb.set_quit(self)
    
    ## --------------------------------
    ## Override Pdb methods
    ## --------------------------------
    
    @echo
    def user_call(self, frame, argument_list):
        """--Call--
        Note: argument_list(=None) is no longer used
        """
        filename = frame.f_code.co_filename
        lineno = frame.f_code.co_firstlineno
        name = frame.f_code.co_name
        if not self.verbose:
            print("{}{}:{}:{}".format(self.prefix1, filename, lineno, name))
        Pdb.user_call(self, frame, argument_list)
    
    @echo
    def user_line(self, frame):
        """--Step/Line--"""
        Pdb.user_line(self, frame)
    
    @echo
    def user_return(self, frame, return_value):
        """--Return--"""
        self.message("$(return_value) = {!r}".format((return_value)))
        Pdb.user_return(self, frame, return_value)
    
    @echo
    def user_exception(self, frame, exc_info):
        """--Exception--"""
        self.message("$(exc_info) = {!r}".format((exc_info)))
        Pdb.user_exception(self, frame, exc_info)
    
    @echo
    def bp_commands(self, frame):
        """--Break--"""
        ## filename = frame.f_code.co_filename
        ## line = linecache.getline(filename, frame.f_lineno, frame.f_globals)
        ## if filename == __file__ and 'self.close()' in line:
        ##     wx.CallAfter(self.shell.Execute, 'next') # step over closing
        return Pdb.bp_commands(self, frame)
    
    @echo
    def interaction(self, frame, traceback):
        Pdb.interaction(self, frame, traceback)
    
    @echo
    def preloop(self):
        """Hook method executed once when the cmdloop() method is called.
        (override) output buffer to the logger (cf. pdb._print_lines)
        """
        frame = self.curframe
        module = inspect.getmodule(frame)
        if module:
            filename = frame.f_code.co_filename
            breaklist = self.get_file_breaks(filename)
            lines = linecache.getlines(filename, frame.f_globals)
            lineno = frame.f_lineno # current line number
            lx = self.tb_lineno.get(frame) # exception
            
            ## Update logger (text and marker)
            if self.module is not module:
                self.logger.Text = ''.join(lines)
            
            for ln in breaklist:
                self.logger.MarkerAdd(ln-1, 1) # (B ) breakpoints
            if lx is not None:
                self.logger.MarkerAdd(lx-1, 2) # (>>) exception
            
            self.trace_pointer(frame, lineno)  # (->) pointer
            
            ## Update view (namespace)
            self.globals.clear()
            self.globals.update(frame.f_globals)
            self.locals.clear()
            self.locals.update(frame.f_locals)
            try:
                tree = self.viewer.filling.tree
                tree.display()
                ## tree.Expand(tree.root)
            except Exception:
                pass
        self.module = module
        Pdb.preloop(self)
    
    @echo
    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to return."""
        lineno = self.curframe.f_lineno
        self.logger.MarkerDeleteAll(0)
        self.logger.MarkerAdd(lineno-1, 0) # (=>) last pointer
        Pdb.postloop(self)


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.inspector
        frm.dbg = Debugger(self)
    frm.Show()
    app.MainLoop()
