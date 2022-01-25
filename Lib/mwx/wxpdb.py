#! python3
# -*- coding: utf-8 -*-
"""Graphical debugger
   of the phoenix, by the phoenix, for the phoenix

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from functools import wraps
from pdb import Pdb, bdb
import pdb
import linecache
import inspect
import wx


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
    logger : ShellFrame Log
      busy : The flag of being running now
   verbose : Verbose messages are output from Pdb
    module : The module of the currently stacked frame on Pdb
    locals : The namespace of the currently stacked frame on Pdb
   globals : (ditto)

Args:
    parent : shellframe
     stdin : shell.interp.stdin
    stdout : shell.interp.stdout
    """
    indent = "  "
    prefix1 = "> "
    prefix2 = "-> "
    verbose = False
    parent = property(lambda self: self.__shellframe)
    logger = property(lambda self: self.__shellframe.Log)
    busy = property(lambda self: self.target is not None)
    locals = property(lambda self: self.curframe.f_locals) # cf. curframe_locals
    globals = property(lambda self: self.curframe.f_globals)
    
    def __init__(self, parent, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.__shellframe = parent
        self.prompt = self.indent + '(Pdb) ' # (overwrite) pdb prompt
        self.skip = [self.__module__, 'bdb', 'pdb'] # (overwrite) skip this module
        self.target = None
        self.module = None
    
    def trace(self, target, *args, **kwargs):
        if not callable(target):
            print("- cannot break {!r} (not callable)".format(target))
            return
        if inspect.isbuiltin(target):
            print("- cannot break {!r}".format(target))
            return
        if self.target:
            wx.MessageBox("Debugger is running\n\n"
                          "Enter [q]uit to exit before closing.")
            return
        try:
            def _continue():
                try:
                    wx.EndBusyCursor() # cancel the egg timer
                except Exception:
                    pass
            wx.CallAfter(_continue)
            self.logger.clear()
            self.logger.Show()
            self.target = target
            self.parent.handler('debug_begin', self.target)
            self.set_trace(inspect.currentframe())
            target(*args, **kwargs)
        except bdb.BdbQuit:
            pass
        finally:
            self.set_quit()
            self.module = None
            self.target = None
            self.parent.handler('debug_end', self.target)
    
    def help(self, cmd=None):
        if cmd is None:
            self.parent.handler('put_help', pdb.__doc__)
        else:
            self.input('h {}'.format(cmd)) # individual command help
    
    def quit(self):
        self.input('q') # quit interactively
    
    def input(self, c):
        if self.target:
            self.stdin.input = c
    
    def message(self, msg, indent=-1):
        """(override) Add indent to msg"""
        prefix = self.indent if indent < 0 else ' ' * indent
        print(prefix + str(msg), file=self.stdout)
    
    def error(self, msg):
        print(self.indent + "***", msg, file=self.stdout)
    
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
        Pdb.print_stack_entry(self, frame_lineno, prompt_prefix)
    
    ## --------------------------------
    ## Override Bdb methods
    ## --------------------------------
    
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
        return Pdb.set_quit(self)
    
    ## --------------------------------
    ## Override Pdb methods
    ## --------------------------------
    
    @echo
    def user_call(self, frame, argument_list):
        """--Call--"""
        ## Note: argument_list(=None) is no longer used
        filename = frame.f_code.co_filename
        lineno = frame.f_code.co_firstlineno
        name = frame.f_code.co_name
        if not self.verbose:
            self.message("{}{}:{}:{}".format(
                         self.prefix1, filename, lineno, name), indent=0)
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
            eol = lines[-1].endswith('\n')
            if self.module is not module\
              or self.logger.LineCount != len(lines) + eol: # add +1
                self.logger.Text = ''.join(lines)
            
            for ln in breaklist:
                self.logger.MarkerAdd(ln-1, 1) # (B ) breakpoints
            if lx is not None:
                self.logger.MarkerAdd(lx-1, 2) # (>>) exception
            
            self.trace_pointer(frame, lineno)  # (->) pointer
            self.parent.handler('debug_next', frame)
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
        self = frm.shellframe
        frm.dbg = Debugger(self,
                           stdin=self.rootshell.interp.stdin,
                           stdout=self.rootshell.interp.stdout
                           )
        self.rootshell.Execute("dive(self.dbg)")
        self.rootshell.write("self.dbg.trace(self.About)")
        frm.dbg.verbose = 1
        echo.debug = 0
        self.Show()
    frm.Show()
    app.MainLoop()
