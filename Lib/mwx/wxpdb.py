#! python3
"""Graphical debugger
   of the phoenix, by the phoenix, for the phoenix.
"""
from functools import wraps
from bdb import BdbQuit
from pdb import Pdb
import pdb
import sys
import re
import inspect
import threading
from importlib import import_module
import wx

from .utilus import FSM, where


def echo(f):
    @wraps(f)
    def _f(*args, **kwargs):
        if echo.verbose > 0:
            print("<{!r}>".format(f.__name__))
        return f(*args, **kwargs)
    return _f
echo.verbose = 0


class Debugger(Pdb):
    """Graphical debugger with extended Pdb.
    
    Args:
        parent: shellframe
        stdin:  shell.interp.stdin
        stdout: shell.interp.stdout
    
    Attributes:
        editor: Notebook to show the stack frames
    
    Key bindings::
    
        C-g     : quit
        C-q     : quit
        C-n     : next   (step-over)
        C-s     : step   (step-in)
        C-r     : return (step-out)
        C-b     : Set a breakpoint at the current line.
        C-@     : Jump to the first lineno of the code.
        C-S-j   : Jump to the lineno of the code.
        C-S-b   : Continue execution until the lineno of the code.
        C-w     : Stamp current where(frame) message.
    """
    verbose = False
    use_rawinput = False
    prompt = property(lambda self: self.indents + '(Pdb) ',
                      lambda self, v: None)  # fake setter
    handler = property(lambda self: self.__handler)

    @property
    def interactive_shell(self):
        return self.__shell

    @interactive_shell.setter
    def interactive_shell(self, v):
        self.__shell = v
        ## Don't use rawinput
        self.stdin = self.__shell.interp.stdin
        self.stdout = self.__shell.interp.stdout

    @property
    def busy(self):
        """Indicates that the current state is debug mode.
        
        Note:
            This flag is True from entering `set_trace` until the end of `set_quit`.
        """
        ## cf. (self.handler.current_state == 1)
        try:
            return self.curframe is not None
        except AttributeError:
            pass

    @property
    def tracing(self):
        """Indicates that the current state is trace mode.
        """
        ## cf. (self.handler.current_state == 2)
        return self.__hookpoint is not None

    def __init__(self, parent, *args, **kwargs):
        Pdb.__init__(self, *args, **kwargs)
        
        self.parent = parent
        self.indents = ' ' * 2
        self.interactive_shell = parent.rootshell
        self.editor = None
        self.code = None
        self.__hookpoint = None
        
        def _input(msg):
            ## redirects input such as cl(ear)
            self.message(msg, indent=0)
            return self.stdin.readline()
        pdb.input = _input
        
        def _help():
            self.parent.handler('add_help', pdb.__doc__, "pdb")
        pdb.help = _help
        
        def dispatch(evt):
            """Fork events to the parent."""
            self.parent.handler(self.handler.current_event, evt)
        
        self.__handler = FSM({ # DNA<Debugger>
            0 : {
                  'debug_begin' : (1, self.on_debug_begin, dispatch),
                  'trace_begin' : (2, dispatch),
            },
            1 : {
                        'abort' : (0, ),
                    'debug_end' : (0, self.on_debug_end, dispatch),
                   'debug_mark' : (1, self.on_debug_mark, dispatch),
                   'debug_next' : (1, self.on_debug_next, dispatch),
                  'C-g pressed' : (1, lambda v: self.send_input('q')),
                  'C-q pressed' : (1, lambda v: self.send_input('q')),
                  'C-n pressed' : (1, lambda v: self.send_input('n')),
                  'C-s pressed' : (1, lambda v: self.send_input('s')),
                  'C-r pressed' : (1, lambda v: self.send_input('r')),
                  'C-b pressed' : (1, lambda v: self.set_breakpoint()),
                  'C-@ pressed' : (1, lambda v: self.jump_to_entry()),
                'C-S-j pressed' : (1, lambda v: self.jump_to_lineno()),
                'C-S-b pressed' : (1, lambda v: self.exec_until_lineno()),
                  'C-w pressed' : (1, lambda v: self.stamp_where()),
            },
            2 : {
                    'trace_end' : (0, dispatch),
                   'trace_hook' : (2, self.on_trace_hook, dispatch),
                  'debug_begin' : (1, self.on_debug_begin, dispatch),
            },
        })

    def set_breakpoint(self):
        """Set a breakpoint at the current line."""
        filename = self.curframe.f_code.co_filename
        ln = self.editor.buffer.cline + 1
        if ln not in self.get_file_breaks(filename):
            self.send_input('b {}'.format(ln), echo=True)

    def jump_to_entry(self):
        """Jump to the first lineno of the code."""
        ln = self.editor.buffer.markline + 1
        if ln:
            self.send_input('j {}'.format(ln), echo=True)

    def jump_to_lineno(self):
        """Jump to the lineno of the code."""
        ln = self.editor.buffer.cline + 1
        if ln:
            self.send_input('j {}'.format(ln), echo=True)

    def exec_until_lineno(self):
        """Continue execution until the lineno of the code."""
        frame = self.curframe
        filename = frame.f_code.co_filename
        lineno = frame.f_lineno
        name = frame.f_code.co_name
        ln = self.editor.buffer.cline + 1
        if ln > lineno:
            self.send_input('until {}'.format(ln))
            self.message("--> {}:{}:{}".format(filename, ln, name), indent=0)
        else:
            self.stamp_where()

    def stamp_where(self):
        """Stamp current where(frame) message."""
        ## cf. (print_stack_entry for frame in self.stack)
        self.send_input('w')
        if not self.verbose:
            self.message("--> {}".format(where(self.curframe)), indent=0)

    def send_input(self, c, echo=False):
        """Send input:str (echo message if needed)."""
        def _send():
            self.stdin.input = c
            if echo or self.verbose:
                self.message(c, indent=0)
        wx.CallAfter(_send)

    def message(self, msg, indent=True):
        """Add prefix and insert msg at the end of command-line."""
        shell = self.interactive_shell
        shell.goto_char(shell.eolc)
        prefix = self.indents if indent else ''
        print("{}{}".format(prefix, msg), file=self.stdout)

    def watch(self, bp):
        """Start tracing."""
        if self.busy: # don't set while debugging
            return
        self.__hookpoint = bp
        self.reset()
        sys.settrace(self.trace_dispatch)
        threading.settrace(self.trace_dispatch)
        self.handler('trace_begin', bp)

    def unwatch(self):
        """End tracing."""
        if self.busy: # don't unset while debugging
            return
        bp = self.__hookpoint
        self.reset()
        sys.settrace(None)
        threading.settrace(None)
        ## delete bp *after* setting dispatcher -> None
        self.__hookpoint = None
        if bp:
            self.handler('trace_end', bp)
        else:
            ## Called to abort when the debugger is invalid status:
            ## e.g., (self.handler.current_state > 0 but not busy)
            self.handler('abort')

    def debug(self, obj, *args, **kwargs):
        """Debug a callable object.
        """
        if not callable(obj):
            wx.MessageBox("Not a callable object.\n\n"
                          "Unable to debug {!r}.".format(obj))
            return
        if self.busy:
            wx.MessageBox("Debugger is running.\n\n"
                          "Enter [q]uit to exit debug mode.")
            return
        self.unwatch()
        try:
            frame = inspect.currentframe().f_back
            self.set_trace(frame)
            obj(*args, **kwargs)
        except BdbQuit:
            pass
        except Exception as e:
            ## Note: post-call to avoid crashing by a kill-focus event.
            wx.CallAfter(wx.MessageBox,
                         f"Debugger has been closed.\n\n{e}")
        finally:
            self.set_quit()

    def run(self, cmd, filename="<string>"):
        """Debug a statement executed via the exec() function.
        """
        if self.busy:
            wx.MessageBox("Debugger is running.\n\n"
                          "Enter [q]uit to exit debug mode.")
            return
        self.unwatch()
        globals = self.interactive_shell.globals
        locals = self.interactive_shell.locals
        if isinstance(cmd, str):
            cmd = compile(cmd, filename, "exec")
        try:
            frame = inspect.currentframe().f_back
            self.set_trace(frame)
            self.send_input('s')
            exec(cmd, globals, locals)
        except BdbQuit:
            pass
        except Exception as e:
            ## Note: post-call to avoid crashing by a kill-focus event.
            wx.CallAfter(wx.MessageBox,
                         f"Debugger has been closed.\n\n{e}")
        finally:
            self.set_quit()

    ## --------------------------------
    ## Actions for handler
    ## --------------------------------

    def _markbp(self, lineno, style):
        """Add a marker to lineno, with the following style markers:
        [1] white_arrow for breakpoints
        [2] red_arrow for exceptions
        """
        if self.editor:
            if lineno:
                self.editor.buffer.MarkerAdd(lineno - 1, style)
            else:
                self.editor.buffer.MarkerDeleteAll(style)

    def on_debug_begin(self, frame):
        """Called before set_trace.
        Note: self.busy -> False or None
        """
        self.__hookpoint = None
        self.indents = ' ' * 2
        self.stdin.input = '' # clear stdin buffer

    def on_debug_mark(self, frame):
        """Called when interaction."""
        code = frame.f_code
        filename = code.co_filename
        firstlineno = code.co_firstlineno
        lineno = frame.f_lineno
        m = re.match("<frozen (.*)>", filename)
        if m:
            module = import_module(m.group(1))
            filename = inspect.getfile(module)
        
        editor = next(self.parent.get_all_editors(code),
                 next(self.parent.get_all_editors(filename), None))
        if not editor:
            editor = self.parent.Log
            ## Note: Need a post-call for a thread debugging.
            wx.CallAfter(editor.load_cache, filename)
        self.editor = editor
        
        if not self.interactive_shell.HasFocus():
            self.editor.buffer.SetFocus()
        
        for ln in self.get_file_breaks(filename):
            self._markbp(ln, 1) # (>>) bp:white-arrow
        
        def _mark():
            buffer = self.editor.buffer
            if filename == buffer.filename:
                if code != self.code:
                    buffer.markline = firstlineno - 1 # (o) entry:mark
                    buffer.goto_marker(1)
                    buffer.recenter(3)
                buffer.goto_line(lineno - 1)
                buffer.pointer = lineno - 1 # (->) pointer:mark
                buffer.ensureLineMoreOnScreen(lineno - 1)
            self.code = code
        wx.CallAfter(_mark)

    def on_debug_next(self, frame):
        """Called in preloop (cmdloop)."""
        shell = self.interactive_shell
        self.__cpos = shell.cpos
        def _next():
            shell.goto_char(shell.eolc)
            pos = self.__cpos
            out = shell.GetTextRange(pos, shell.cpos)
            if out.strip(' ') == self.prompt.strip(' ') and pos > shell.bol:
                shell.cpos = pos # backward selection
                shell.ReplaceSelection('')
                shell.prompt()
            shell.EnsureCaretVisible()
            self.__cpos = shell.cpos
        wx.CallAfter(_next)

    def on_debug_end(self, frame):
        """Called after set_quit.
        Note: self.busy -> True (until this stage)
        """
        if self.editor:
            del self.editor.buffer.pointer
        self.editor = None
        self.code = None
        
        ## Note: Required to terminate the reader of threading pdb.
        self.send_input('\n')

    def on_trace_hook(self, frame):
        """Called when a breakppoint is reached."""
        self.__hookpoint = None
        self.interactive_shell.write('\n', -1) # move to eolc and insert LFD
        self.message(where(frame.f_code), indent=0)

    ## --------------------------------
    ## Override Bdb methods
    ## --------------------------------

    def break_anywhere(self, frame):
        """Return False (override)
        even if there is any breakpoint for frame's filename.
        """
        return False

    def dispatch_line(self, frame):
        """Invoke user function and return trace function for line event.
        
        (override) Watch the hookpoint.
        """
        if self.__hookpoint:
            target, line = self.__hookpoint
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            if target == filename:
                if lineno >= line:
                    self.handler('trace_hook', frame)
                    self.handler('debug_begin', frame)
                else:
                    return None
            else:
                return None
        return Pdb.dispatch_line(self, frame)

    def dispatch_call(self, frame, arg):
        """Invoke user function and return trace function for call event.
        
        (override) Watch the hookpoint.
        """
        if self.__hookpoint:
            target, line = self.__hookpoint
            filename = frame.f_code.co_filename
            lineno = frame.f_lineno
            if target == filename:
                if lineno <= line: # continue to dispatch_line
                    return self.trace_dispatch
                else:
                    return None
            else:
                return None
        return Pdb.dispatch_call(self, frame, arg)

    def dispatch_return(self, frame, arg):
        """Invoke user function and return trace function for return event.
        
        (override) Watch the hookpoint.
        """
        if self.__hookpoint:
            return None
        return Pdb.dispatch_return(self, frame, arg)

    def dispatch_exception(self, frame, arg):
        """Invoke user function and return trace function for exception event.
        
        (override) Watch the hookpoint.
        """
        if self.__hookpoint:
            return None
        return Pdb.dispatch_exception(self, frame, arg)

    def set_trace(self, frame=None):
        if self.busy:
            wx.MessageBox("Debugger is running.\n\n"
                          "Enter [q]uit to exit debug mode.")
            return
        if not frame:
            frame = inspect.currentframe().f_back
        self.handler('debug_begin', frame)
        Pdb.set_trace(self, frame)

    def set_break(self, filename, lineno, *args, **kwargs):
        self._markbp(lineno, 1)
        return Pdb.set_break(self, filename, lineno, *args, **kwargs)

    def set_quit(self):
        try:
            Pdb.set_quit(self)
        finally:
            if self.parent: # Check if the parent is being deleted.
                self.handler('debug_end', self.curframe)

    ## --------------------------------
    ## Override Pdb methods
    ## --------------------------------

    @echo
    def print_stack_entry(self, frame_lineno, prompt_prefix=None):
        """Print the stack entry frame_lineno (frame, lineno).
        
        (override) Change prompt_prefix.
                   Add pointer:mark when step next or jump.
        """
        if self.verbose:
            Pdb.print_stack_entry(self, frame_lineno,
                prompt_prefix or "\n{}-> ".format(self.indents))
        self.handler('debug_mark', frame_lineno[0])

    @echo
    def user_call(self, frame, argument_list):
        """--Call--
        
        (override) Show message to record the history.
                   Add indent spaces.
        """
        if not self.verbose:
            self.message("> {}".format(where(frame)), indent=0)
        self.indents += ' ' * 2
        Pdb.user_call(self, frame, argument_list)

    @echo
    def user_line(self, frame):
        """--Next--
        """
        Pdb.user_line(self, frame)

    @echo
    def user_return(self, frame, return_value):
        """--Return--
        
        (override) Show message to record the history.
                   Remove indent spaces.
        """
        if not self.verbose:
            self.message("$(retval) = {!r}".format(return_value), indent=0)
        if self._wait_for_mainpyfile:
            return
        frame.f_locals['__return__'] = return_value
        self.message('--Return--')
        if len(self.indents) > 2:
            self.indents = self.indents[:-2] # remove '  '
        self.interaction(frame, None)
        ## Pdb.user_return(self, frame, return_value)

    @echo
    def user_exception(self, frame, exc_info):
        """--Exception--
        
        (override) Update exception:markers.
        """
        t, v, tb = exc_info
        self._markbp(tb.tb_lineno, 2)
        self.message(tb.tb_frame, indent=0)
        Pdb.user_exception(self, frame, exc_info)

    @echo
    def bp_commands(self, frame):
        """--Break--
        
        (override) Update breakpoint:markers every time the frame changes.
        """
        filename = frame.f_code.co_filename
        breakpoints = self.get_file_breaks(filename)
        self._markbp(None, 1)
        for lineno in breakpoints:
            self._markbp(lineno, 1)
        return Pdb.bp_commands(self, frame)

    @echo
    def preloop(self):
        """Hook method executed once when the cmdloop() method is called."""
        Pdb.preloop(self)
        self.handler('debug_next', self.curframe)

    @echo
    def postloop(self):
        """Hook method executed once when the cmdloop() method is about to return."""
        Pdb.postloop(self)
