#! python3
# -*- coding: utf-8 -*-
"""Graphical debugger
   of the phoenix, by the phoenix, for the phoenix

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from functools import wraps
from pdb import Pdb
import pdb
import re
import importlib
import linecache
import inspect
import wx
try:
    from utilus import FSM
except ImportError:
    from .utilus import FSM


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

Key bindings:
    C-S-h  : help(pdb)
      C-g  : quit
      C-q  : quit
      C-n  : next
      C-r  : return
      C-s  : step
    """
    indent = "  "
    prefix1 = "> "
    prefix2 = "-> "
    verbose = False
    parent = property(lambda self: self.__shellframe)
    logger = property(lambda self: self.__shellframe.Log)
    handler = property(lambda self: self.__handler)
    busy = property(lambda self: self.__handler.current_state == 1)
    
    @property
    def locals(self):
        try:
            return self.curframe.f_locals # cf. curframe_locals
        except AttributeError:
            pass
    
    @property
    def globals(self):
        try:
            return self.curframe.f_globals
        except AttributeError:
            pass
    
    def __init__(self, parent, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.__shellframe = parent
        self.__interactive = None
        self.prompt = self.indent + '(Pdb) ' # default pdb prompt
        if not self.skip:
            self.skip = set()
        self.skip |= {self.__module__, 'bdb', 'pdb'} # skip this module
        self.target = None
        self.code = None
        
        def _input(msg):
            """redirect for cl(ear)"""
            self.message(msg, indent=0)
            return self.stdin.readline()
        pdb.input = _input
        
        def jump_to_entry_point(v):
            ln = self.logger.LineFromPosition(self.logger.mark)
            self.input('j {}'.format(ln + 1))
        
        self.__handler = FSM({
            0 : {
                  'debug_begin' : (1, self.on_debug_begin),
            },
            1 : {
                    'debug_end' : (0, self.on_debug_end),
                   'debug_next' : (1, self.on_debug_next),
                'C-S-h pressed' : (1, lambda v: self.help()),
                  'C-g pressed' : (1, lambda v: self.input('q')),
                  'C-q pressed' : (1, lambda v: self.input('q')),
                  'C-n pressed' : (1, lambda v: self.input('n')),
                  'C-s pressed' : (1, lambda v: self.input('s')),
                  'C-r pressed' : (1, lambda v: self.input('r')),
                  'C-@ pressed' : (1, jump_to_entry_point),
            }
        })
    
    def on_debug_begin(self, frame):
        """Called before set_trace"""
        shell = self.parent.rootshell
        out = shell.GetTextRange(shell.bolc, shell.point)
        self.parent.handler('add_history', out)
        self.parent.handler('debug_begin', frame)
        self.__interactive = shell.point
        def _continue():
            try:
                wx.EndBusyCursor() # cancel the egg timer
            except Exception:
                pass
        wx.CallAfter(_continue)
    
    def on_debug_next(self, frame):
        """Called in preloop (cmdloop)"""
        shell = self.parent.rootshell
        pos = self.__interactive
        def _post():
            out = shell.GetTextRange(pos, shell.point)
            if out == self.prompt or out.endswith(self.prompt*2):
                ## shell.point = pos # backward selection to anchor point
                shell.point -= len(self.prompt)
                shell.ReplaceSelection('')
                shell.goto_char(-1)
                shell.prompt()
            else:
                self.parent.handler('add_history', out)
            self.__interactive = shell.point
        wx.CallAfter(_post)
        self.parent.handler('debug_next', frame)
    
    def on_debug_end(self, frame):
        """Called after set_quit"""
        shell = self.parent.rootshell
        out = shell.GetTextRange(self.__interactive, shell.point) + '\n'
        self.parent.handler('add_history', out)
        self.parent.handler('debug_end', frame)
        self.__interactive = None
    
    def trace(self, target, *args, **kwargs):
        if not callable(target):
            wx.MessageBox("Not callable object\n\n"
                          "Unable to trace {!r}".format(target))
            return
        if inspect.isbuiltin(target):
            wx.MessageBox("Built-in object\n\n"
                          "Unable to trace {!r}".format(target))
            return
        if self.busy:
            wx.MessageBox("Debugger is running\n\n"
                          "Enter [q]uit to exit.")
            return
        try:
            self.target = target
            self.set_trace()
            target(*args, **kwargs)
        finally:
            self.set_quit()
            return
    
    def help(self, cmd=None):
        if cmd is None:
            self.parent.handler('put_help', pdb.__doc__)
        else:
            self.input('h {}'.format(cmd)) # individual command help
    
    def input(self, c):
        self.stdin.input = c
    
    def message(self, msg, indent=-1):
        """(override) Add indent to msg"""
        prefix = self.indent if indent < 0 else ' ' * indent
        print(prefix + str(msg), file=self.stdout)
    
    def error(self, msg):
        print(self.indent + "***", msg, file=self.stdout)
    
    def mark(self, frame, lineno):
        self.logger.MarkerDeleteAll(3)
        self.logger.MarkerAdd(lineno-1, 3) # (->) pointer
        self.logger.goto_char(self.logger.PositionFromLine(lineno-1))
        wx.CallAfter(self.logger.recenter)
    
    ## --------------------------------
    ## Override Bdb methods
    ## --------------------------------
    
    def set_trace(self, frame=None):
        if self.busy:
            wx.MessageBox("Debugger is running\n\n"
                          "Enter [q]uit to exit.")
            return
        if self.target is None:
            self.target = pdb.sys._getframe().f_back
        self.handler('debug_begin', self.target)
        return Pdb.set_trace(self, frame)
    
    def set_break(self, filename, lineno, *args, **kwargs):
        self.logger.MarkerAdd(lineno-1, 1) # new breakpoint
        return Pdb.set_break(self, filename, lineno, *args, **kwargs)
    
    def set_quit(self):
        ## if self.verbose:
        ##     print("+ all stacked frame")
        ##     for frame_lineno in self.stack:
        ##         print("-->", self.format_stack_entry(frame_lineno))
        Pdb.set_quit(self)
        self.handler('debug_end', self.target)
        self.target = None
        self.code = None
    
    ## --------------------------------
    ## Override Pdb methods
    ## --------------------------------
    
    @echo
    def print_stack_entry(self, frame_lineno, prompt_prefix=None):
        """Print the stack entry frame_lineno (frame, lineno).
        (override) Change prompt_prefix;
                   Add trace pointer when jump is called.
        """
        self.mark(*frame_lineno) # for jump
        if not self.verbose:
            return
        if prompt_prefix is None:
            prompt_prefix = '\n' + self.indent + self.prefix2
        Pdb.print_stack_entry(self, frame_lineno, prompt_prefix)
    
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
        code = frame.f_code
        filename = code.co_filename
        ## module = inspect.getmodule(frame)
        m = re.match("<frozen (.*)>", filename)
        if m:
            module = importlib.import_module(m.group(1))
            filename = inspect.getfile(module)
        lineno = frame.f_lineno
        lines = linecache.getlines(filename, frame.f_globals)
        lbps = self.get_file_breaks(filename) # breakpoints
        lx = self.tb_lineno.get(frame) # exception
        
        if lines:
            ## Update logger text
            eol = lines[-1].endswith('\n')
            if self.code and self.code.co_filename != filename\
              or self.logger.LineCount != len(lines) + eol: # add +1
                self.logger.Text = ''.join(lines)
            
            ## Update logger marker
            if self.code != code:
                self.logger.mark = self.logger.PositionFromLine(lineno-1)
            
            for ln in lbps:
                self.logger.MarkerAdd(ln-1, 1) # (> ) breakpoints
            if lx is not None:
                self.logger.MarkerAdd(lx-1, 2) # (>>) exception
            
            self.mark(frame, lineno) # (->) pointer
        
        self.handler('debug_next', frame)
        self.code = code
        Pdb.preloop(self)
    
    @echo
    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to return."""
        Pdb.postloop(self)


if __name__ == "__main__":
    import mwx
    app = wx.App()
    frm = mwx.Frame(None)
    if 1:
        self = frm.shellframe
        shell = frm.shellframe.rootshell
        dbg = Debugger(self,
                       stdin=shell.interp.stdin,
                       stdout=shell.interp.stdout,
                       )
        dbg.handler.debug = 4
        dbg.verbose = 1
        echo.debug = 1
        shell.handler.update({
            None : {
                '* pressed' : [None, lambda v: dbg.handler(shell.handler.event, v)],
            },
        })
        frm.dbg = dbg
        shell.write("self.dbg.trace(self.About)")
        self.Show()
    frm.Show()
    app.MainLoop()
