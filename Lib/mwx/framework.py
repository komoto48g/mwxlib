#! python
# -*- coding: utf-8 -*-
"""mwxlib framework

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from __future__ import division, print_function
from __future__ import unicode_literals
from __future__ import absolute_import

__version__ = "0.40.5"
__author__ = "Kazuya O'moto <komoto@jeol.co.jp>"

from collections import OrderedDict
from functools import partial
from functools import wraps
import traceback
import datetime
import keyword
import shlex
import time
import sys
import os
import re
import wx
from wx import aui
from wx import stc
from wx.py.shell import Shell
from wx.py.editwindow import EditWindow
import numpy as np
import fnmatch
import pydoc
import warnings
import inspect
from inspect import (isclass, ismodule, ismethod, isbuiltin,
                     isfunction, isgenerator)
from pprint import pprint, pformat
from six.moves import builtins
## from six import PY3

try:
    from importlib import reload
except ImportError:
    pass

LITERAL_TYPE = (str,) if sys.version_info >= (3,0) else (str,unicode)


def atom(x):
    return not hasattr(x, '__name__')


def instance(*types):
    ## return lambda v: isinstance(v, types)
    def _pred(v):
        return isinstance(v, types)
    _pred.__name__ = str(','.join(p.__name__ for p in types))
    return _pred


def Not(p):
    ## return lambda v: not p(v)
    def _pred(v):
        return not p(v)
    _pred.__name__ = str("not {}".format(p.__name__))
    return _pred


def And(p, q):
    ## return lambda v: p(v) and q(v)
    def _pred(v):
        return p(v) and q(v)
    _pred.__name__ = str("{} and {}".format(p.__name__, q.__name__))
    return _pred


def Or(p, q):
    ## return lambda v: p(v) or q(v)
    def _pred(v):
        return p(v) or q(v)
    _pred.__name__ = str("{} or {}".format(p.__name__, q.__name__))
    return _pred


def predicate(text):
    tokens = [x for x in split_into_words(text.strip()) if not x.isspace()]
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'not' or c == '~':
            tokens[j:j+2] = ["Not({})".format(tokens[j+1])]
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'and' or c == '&':
            tokens[j-1:j+2] = ["And({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'or' or c == '|':
            tokens[j-1:j+2] = ["Or({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    return ' '.join(tokens)


def Dir(obj):
    """As the standard dir, but also listup filelds of COM object
    
    Note:you should check if the COM was created with [win32com.client.gencache.EnsureDispatch]
    """
    keys = dir(obj)
    try:
        if hasattr(obj, '_prop_map_get_'):
            keys += obj._prop_map_get_.keys()
    finally:
        return keys


def docp(f):
    """A helper predicates do nothing but printing doc:str"""
    if not atom(f):
        doc = inspect.getdoc(f)
        if doc:
            print("  --{}".format("-" * 40))
            print("  + {}".format(typename(f)))
            head ="     |"
            for ln in doc.splitlines():
                print(head, ln)
            print(head)
    return True


def getargspec(f):
    try:
        args, _varargs, _keywords, defaults,\
          _kwonlyargs, _kwonlydefaults, _annotations = inspect.getfullargspec(f) #>= PY3
    except AttributeError:
        args, _varargs, _keywords, defaults = inspect.getargspec(f) #<= PY2
    return args, _varargs, _keywords, defaults


def apropos(rexpr, root, ignorecase=True, alias=None, pred=None, locals=None):
    """Put a list of objects having expression `rexpr in `root
    """
    name = alias or typename(root)
    rexpr = (rexpr.replace('\\a','[a-z0-9]')  # \a: identifier chars (custom rule)
                  .replace('\\A','[A-Z0-9]')) # \A: (start of the string) から変更
    
    if isinstance(pred, LITERAL_TYPE):
        pred = eval(predicate(pred) or 'None', None, locals)
    
    if pred:
        if not callable(pred):
            raise TypeError("{} is not callable".format(typename(pred)))
        
        if inspect.isclass(pred): # class ctor: int, float, str, ... etc.
            pred = instance(pred)
        elif not inspect.isbuiltin(pred):
            args, _varargs, _keywords, defaults = getargspec(pred)
            if not args or len(args) - len(defaults or ()) > 1:
                raise TypeError("{} must take exactly one argument".format(typename(pred)))
    
    print("matching to {!r} in {} {} :{}".format(rexpr, name, type(root), typename(pred)))
    try:
        p = re.compile(rexpr, re.I if ignorecase else 0)
        keys = sorted(filter(p.search, Dir(root)), key=lambda s:s.upper())
        n = 0
        for key in keys:
            try:
                value = getattr(root, key)
                if callable(pred) and not pred(value):
                    continue
                word = repr(value)
                word = ' '.join(s.strip() for s in word.splitlines()) # format in line
            except (TypeError, ValueError):
                ## pred:error is ignored
                continue
            except Exception as e:
                word = '#<{!r}>'.format(e) # repr fails in formatting
            ellipsis = ('...' if len(word)>80 else '')
            print("    {}.{:<36s} {}".format(name, key, word[:80] + ellipsis))
            n += 1
        if callable(pred):
            print("... found {} of {} words with :{}".format(n, len(keys), typename(pred)))
        else:
            print("... found {} words.".format(len(keys)))
    except re.error as e:
        print("- re:miss compilation {!r} : {!r}".format(e, rexpr))


def typename(root, docp=False, qualp=False):
    if hasattr(root, '__name__'): # class, module, method, function etc.
        if qualp:
            if hasattr(root, '__qualname__'): # PY3 format
                name = root.__qualname__
            elif hasattr(root, 'im_class'): # PY2 format
                name = root.im_class.__name__ + '.' + root.__name__
        else:
            name = root.__name__
        
        if hasattr(root, '__module__'): # module:callable
            if root.__module__ not in ('__main__', 'mwx.framework', None):
                name = root.__module__ + ':' + name
        
    elif hasattr(root, '__module__'): # atom -> module.class (class-object)
        name = root.__module__ + '.' + root.__class__.__name__
        
    else:
        ## return "{!r}<{!r}>".format(root, pydoc.describe(root))
        return repr(root)
    
    if docp and callable(root) and root.__doc__:
        name += "<{!r}>".format(root.__doc__.splitlines()[0]) # concat the first doc line
    return name


def get_words_hint(cmd, sep=None):
    head, sep, tail = get_words_backward(cmd, sep).rpartition('.')
    return head, sep, tail.strip()


def get_words_backward(text, sep=None):
    """Get words (from text at left side of caret)"""
    try:
        tokens = split_tokens(text)[::-1]
        words = extract_words_from_tokens(tokens, sep, reverse=1)
        return ''.join(reversed(words))
    except ValueError:
        return ''


def get_words_forward(text, sep=None):
    """Get words (from text at right side of caret)"""
    try:
        tokens = split_tokens(text)
        words = extract_words_from_tokens(tokens, sep)
        return ''.join(words)
    except ValueError:
        return ''


def split_tokens(text):
    lexer = shlex.shlex(text)
    lexer.wordchars += '.'
    ## lexer.whitespace = '\r\n' # space(tab) is not a white
    lexer.whitespace = '' # nothing is white (for multiline analysis)
    return list(lexer)


def split_into_words(text):
    phrases = []
    tokens = split_tokens(text)
    while tokens:
        words = extract_words_from_tokens(tokens)
        phrases.append(''.join(words) or tokens.pop(0)) # list extracted words or a separator
    return phrases
    ## return [x for x in phrases if not x.isspace()] # nospace


def extract_words_from_tokens(tokens, sep=None, reverse=False):
    """Extract pythonic expressions from `tokens
    default `sep includes `@, binary-ops, and whitespaces, etc.
    """
    if sep is None:
        sep = "`@=+-/*%<>&|^~,:; \t\r\n!?" # OPS; SEPARATOR_CHARS; !?
    p, q = "({[", ")}]"
    if reverse:
        p,q = q,p
    stack = []
    words = []
    for j,c in enumerate(tokens):
        if c in p:
            stack.append(c)
        elif c in q:
            if not stack: # error("open-paren", c)
                break
            if c != q[p.index(stack.pop())]: # error("mismatch-paren", c)
                break
        elif not stack and c in sep: # ok
            break
        words.append(c) # stack word
    else:
        j = None
        if stack: # error("unclosed-paren", ''.join(stack))
            pass
    del tokens[:j] # 取り出したトークンは消す
    return words   # 取り出したトークンリスト (to be ''.joined to make a pyrepr)


def find_modules(force=False, verbose=True):
    """Find all modules available and write to log file.
    
    Similar to pydoc.help, it scans packages, but also the submodules.
    This creates a log file in ~/.deb and save the list.
    """
    try:
        reload(sys)
        sys.setdefaultencoding('utf-8') # <= PY2
    except AttributeError as e:
        pass
    
    if verbose:
        princ = print
    else:
        def princ(*args, **kwargs):
            pass
    lm = []
    f = os.path.expanduser("~/.deb/deb-modules-{}.log".format(sys.winver))
    if force or not os.path.exists(f):
        print("Please wait a moment "
              "while Py{} gathers a list of all available modules...".format(sys.winver))
        
        def callback(path, modname, desc):
            lm.append(modname)
            princ('\b'*80 + "Scanning {:70s}".format(modname[:70]), end='')
        
        def error(modname):
            ## lm.append(modname + '*') # do not append to the list
            princ('\b'*80 + "- failed: {}".format(modname[:70]))
        
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore') # ignore problems during import
            pydoc.ModuleScanner().run(callback, key='', onerror=error)
            princ('\b'*80 + "The results were written in {!r}.".format(f))
        
        lm.sort(key=str.upper)
        with open(f, 'w') as o:
            pprint(lm, width=256, stream=o) # write moduels
        print("done.")
    else:
        with open(f, 'r') as o:
            lm = eval(o.read()) # read and eval a list of moduels
    return lm


## --------------------------------
## Finite State Machine
## --------------------------------
if not os.path.exists(os.path.expanduser("~/.deb")): # deb 専ディレクトリをホームに作成します
    os.mkdir(os.path.expanduser("~/.deb"))


class SSM(OrderedDict):
    """Single State Machine/Context of FSM
    """
    def __call__(self, event, *args):
        for act in self[event]:
            act(*args)
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(typename(self), id(self))
    
    def __str__(self):
        return '\n'.join("{:>32} : {}".format(
            k, ', '.join(typename(a, docp=1, qualp=0) for a in v)) for k,v in self.items())


class FSM(dict):
    """Finite State Machine
    
    contexts : map of context
        { state : initial state
            { event : event key <str>
                transaction (next_state, *actions ...) }
        }
        state `None` is a wildcard (as executed any time)
        event is a string that can include wildcards `*?[]` (fnmatch rule)
        actions must accept the same *args of function as __call__(*args)
          if no action, FSM carries out only a transition.
            transition is always done before actions
    state : current state
    debug : verbose level
        [1] dump when state transits
        [2] + differnt event comes
        [3] + executed actions (excepting None-state)
        [4] + executed actions (including None-state)
        [5] + and more, all events and executed actions
    """
    debug = 0
    
    current_event = property(lambda self: self.__event)
    current_state = property(lambda self: self.__state)
    previous_state = property(lambda self: self.__prev_state)
    
    @current_state.setter
    def current_state(self, state):
        self.__state = state
        self.__event = None
        self.__debcall__(None)
    
    def clear(self, state):
        """Reset current and previous states"""
        self.__state = self.__prev_state = state
        self.__event = self.__prev_event = None
    
    def __init__(self, contexts=None, default=None):
        dict.__init__(self) # update dict, however, it does not clear
        dict.clear(self)    # if and when __init__ is called, all contents are cleared
        self.clear(default) # the first clear creates object localvars
        self.update(contexts or {})
    
    def __missing__(self, key):
        raise Exception("FSM:logical error - undefined state {!r}".format(key))
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(typename(self), id(self))
    
    def __str__(self):
        return '\n'.join("[ {!r} ]\n{!s}".format(k,v) for k,v in self.items())
    
    def __call__(self, event, *args):
        self.__event = event
        
        ret = False
        if self.__state is not None:
            ret = self.call(event, *args) # Normal process (1)
        
        if None in self:
            self.__state, org = None, self.__state
            try:
                ret = self.call(event, *args) # state `None process (2) forced
            finally:
                if self.__state is None: # restore original
                    self.__state = org
        
        self.__prev_state = self.__state
        self.__prev_event = event
        return ret
    
    def fork(self, *args):
        """Invoke the current event"""
        if self.__state == self.__prev_state: # possibly results in an infinite loop
            self.dump("- FSM:logic error in {!r}".format('fork'),
                      "   event : {}".format(self.__event),
                      "    from : {}".format(self.__prev_state),
                      "   state : {}".format(self.__state), sep='\n')
            raise Exception("FSM:logic error - a fork cannot fork itself")
        return self.call(self.__event, *args)
    
    def call(self, event, *args):
        context = self[self.__state]
        
        if event in context:
            transaction = context[event]
            if not transaction:
                raise Exception("FSM:bad transaction {!r} : {!r}".format(self.__state, event))
            
            self.__prev_state = self.__state # save previos state
            self.__state = transaction[0] # the state transits here
            
            dumpf = self.dump
            
            if self.__state not in self:
                self.__state = self.__prev_state # rewind to previous state
                dumpf("- FSM:unknown transaction {!r}".format(transaction),
                      "   event : {}".format(event),
                      "    from : {}".format(self.__prev_state),
                      "   state : {}".format(self.__state), sep='\n')
                raise Exception("FSM:unknown state {!r}".format(self.__state))
            
            self.__debcall__(event, *args) # check after transition
            
            for act in transaction[1:]:
                try:
                    act(*args) # try actions after transition
                    
                except RuntimeError as e:
                    dumpf("- FSM:runtime error - {!r}".format(e),
                          "   event : {}".format(event),
                          "    from : {}".format(self.__prev_state),
                          "   state : {}".format(self.__state),
                          "  action : {}".format(typename(act)), sep='\n')
                    traceback.print_exc()
                    
                except Exception as e:
                    dumpf("- FSM:exception - {!r}".format(e),
                          "   event : {}".format(event),
                          "    from : {}".format(self.__prev_state),
                          "   state : {}".format(self.__state),
                          "  action : {}".format(typename(act)), sep='\n')
                    traceback.print_exc()
            ## return True # end of transaction
            return len(transaction) > 1
        else:
            ## matching test using fnmatch ファイル名規約によるマッチングテスト
            ## Note: the event must be string
            for pat in context:
                if fnmatch.fnmatchcase(event, pat):
                    return self.call(pat, *args) # recursive call with matched pattern
        
        self.__debcall__(event, *args) # check when no transition
    
    def __debcall__(self, pattern, *args):
        try:
            if self.debug and self.__state is not None:
                transaction = self[self.__prev_state].get(pattern) or []
                actions = ', '.join(typename(a) for a in transaction[1:])
                if (self.debug > 0 and self.__prev_state != self.__state
                 or self.debug > 1 and self.__prev_event != self.__event
                 or self.debug > 2 and actions
                 or self.debug > 3):
                    self.log("{c} {1} --> {2} {0!r} {a}".format(
                        self.__event, self.__prev_state, self.__state,
                        a = '' if not actions else ('=> ' + actions),
                        c = '*' if self.__prev_state != self.__state else ' '))
            
            elif self.debug > 3: # state is None
                transaction = self[None].get(pattern) or []
                actions = ', '.join(typename(a) for a in transaction[1:])
                if actions or self.debug > 4:
                    self.log("\t& {0!r} {a}".format(
                        self.__event,
                        a = '' if not actions else ('=> ' + actions)))
            
            if self.debug > 5:  # whether state is None or not None
                self.log(*args) # max verbose putting all arguments
            
        except Exception as e:
            self.dump("- FSM:exception - {!r}".format(e),
                      "   event : {}".format(self.__event),
                      "    from : {}".format(self.__prev_state),
                      "   state : {}".format(self.__state),
                      " pattern : {}".format(pattern), sep='\n')
            traceback.print_exc()
    
    STDERR = sys.__stderr__
    STDOUT = sys.__stdout__
    
    @staticmethod
    def log(*args, **kwargs):
        print(*args, file=FSM.STDOUT, **kwargs)
    
    @staticmethod
    def dump(*args, **kwargs):
        print(*args, file=FSM.STDERR, **kwargs)
        
        f = os.path.expanduser("~/.deb/deb-dump.log")
        with open(f, 'a') as o:
            exc = traceback.format_exc().strip()
            lex = re.findall("File \"(.*)\", line ([0-9]+), in (.*)\n+(.*)", exc)
            
            print(time.strftime('!!! %Y/%m/%d %H:%M:%S'), file=o)
            print(':'.join(lex[-1]), file=o) # grep error format
            print(*args, file=o, **kwargs) # fsm dump message
            print('\n'.join("  # " + x for x in exc.splitlines()), file=o)
            print('\n', file=o)
    
    def validate(self, state):
        """Sort and move to end items with key which includes `*?[]`"""
        context = self[state]
        ast = []
        bra = []
        for event in list(context): #? OrderedDict mutated during iteration
            if re.search("\[.+\]", event):
                bra.append((event, context.pop(event))) # event key has '[]'
            elif '*' in event or '?' in event:
                ast.append((event, context.pop(event))) # event key has '*?'
        
        temp = sorted(context.items()) # normal event key
        context.clear()
        context.update(temp)
        context.update(sorted(bra, reverse=1))
        context.update(sorted(ast, reverse=1, key=lambda v:len(v[0])))
    
    def update(self, contexts):
        """Update each context or Add new contexts"""
        for k,v in contexts.items():
            if k in self:
                self[k].update(v)
            else:
                ## self[k] = OrderedDict(v)
                self[k] = SSM(v)
            self.validate(k)
        
        keys = list(self)
        if len(keys) == 1:
            self.clear(keys[0])
    
    def append(self, contexts):
        """Append new contexts"""
        for k,v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    k2 = transaction[0]
                    for act in transaction[1:]:
                        self.bind(event, act, k, k2)
            else:
                ## self[k] = OrderedDict(v)
                self[k] = SSM(v)
            self.validate(k)
    
    def remove(self, contexts):
        """Remove old contexts"""
        for k,v in contexts.items():
            for event, transaction in v.items():
                for act in transaction[1:]:
                    self.unbind(event, act, k) # with no error
    
    def hook(self, event, action=None, state=None):
        if not action:
            return lambda f: self.hook(event, f, state)
        
        def _hook(*args, **kwargs):
            action(*args, **kwargs)
            self.unbind(event, _hook) # release hook once called,
        
        return self.bind(event, _hook)
    
    def bind(self, event, action=None, state=None, state2=None):
        """Append a transaction to the context
        equiv. self[state] += {event : [state2, action]}
        The transaction is exepcted to be a list (not a tuple).
        When action is not given, this does nothing, but returns @decor(event-binder)
        """
        if not action:
            return lambda f: self.bind(event, f, state, state2)
        
        if state not in self:
            self[state] = SSM()
        
        context = self[state]
        if state2 is None:
            state2 = state
        if event in context:
            if state2 != context[event][0]:
                print("- FSM:warning - transaction may conflict"
                      " (state {2!r} and the original state is not the same)"
                      " {0!r} : {1!r} --> {2!r}".format(event, state, state2))
                context[event][0] = state2 # change transition
                pass
        else:
            if state2 not in self:
                print("- FSM:warning - transaction may contradict"
                      " (state {2!r} is not found in the contexts)"
                      " {0!r} : {1!r} --> {2!r}".format(event, state, state2))
                pass
            context[event] = [state2] # new event:transaction
        
        if action not in context[event]:
            context[event].append(action)
        return action
    
    def unbind(self, event, action, state=None):
        """Remove a transaction from the contex
        equiv. self[state] -= {event : [*, action]}
        The transaction is exepcted to be a list (not a tuple).
        """
        if state not in self:
            print("- FSM:warning - context of [{!r}] does not exist.")
            return
        
        context = self[state]
        if event in context and action in context[event]:
            try:
                context[event].remove(action) # must be list type
                if len(context[event]) == 1:
                    context.pop(event)
                    if not context:
                        self.pop(state)
            except AttributeError:
                print("- FSM:warning - removing action from context"
                      "({!r} : {!r}) must be a list, not tuple".format(state, event))
        else:
            pass # transaction not found, nothing to be done


## --------------------------------
## Hotkey control interface
## --------------------------------

speckeys = {
    wx.WXK_ALT                  : 'alt',
    wx.WXK_BACK                 : 'backspace',
    wx.WXK_CANCEL               : 'break',
    wx.WXK_CAPITAL              : 'capital',
    wx.WXK_CONTROL              : 'ctrl',
    wx.WXK_DELETE               : 'delete',
    wx.WXK_DOWN                 : 'down',
    wx.WXK_END                  : 'end',
    wx.WXK_ESCAPE               : 'escape',
    wx.WXK_F1                   : 'f1',
    wx.WXK_F2                   : 'f2',
    wx.WXK_F3                   : 'f3',
    wx.WXK_F4                   : 'f4',
    wx.WXK_F5                   : 'f5',
    wx.WXK_F6                   : 'f6',
    wx.WXK_F7                   : 'f7',
    wx.WXK_F8                   : 'f8',
    wx.WXK_F9                   : 'f9',
    wx.WXK_F10                  : 'f10',
    wx.WXK_F11                  : 'f11',
    wx.WXK_F12                  : 'f12',
    wx.WXK_F13                  : 'f13',
    wx.WXK_F14                  : 'f14',
    wx.WXK_F15                  : 'f15',
    wx.WXK_F16                  : 'f16',
    wx.WXK_F17                  : 'f17',
    wx.WXK_F18                  : 'f18',
    wx.WXK_F19                  : 'f19',
    wx.WXK_F20                  : 'f20',
    wx.WXK_F21                  : 'f21',
    wx.WXK_F22                  : 'f22',
    wx.WXK_F23                  : 'f23',
    wx.WXK_F24                  : 'f24',
    wx.WXK_HOME                 : 'home',
    wx.WXK_INSERT               : 'insert',
    wx.WXK_LEFT                 : 'left',
    wx.WXK_NONE                 : 'none',
    wx.WXK_NUMLOCK              : 'num_lock',
    wx.WXK_NUMPAD_ADD           : '+',
    wx.WXK_NUMPAD_DECIMAL       : 'dec',
    wx.WXK_NUMPAD_DELETE        : 'delete',
    wx.WXK_NUMPAD_DIVIDE        : '/',
    wx.WXK_NUMPAD_DOWN          : 'down',
    wx.WXK_NUMPAD_END           : 'end',
    wx.WXK_NUMPAD_ENTER         : 'enter',
    wx.WXK_NUMPAD_HOME          : 'home',
    wx.WXK_NUMPAD_INSERT        : 'insert',
    wx.WXK_NUMPAD_LEFT          : 'left',
    wx.WXK_NUMPAD_MULTIPLY      : '*',
    wx.WXK_NUMPAD_PAGEDOWN      : 'pagedown',
    wx.WXK_NUMPAD_PAGEUP        : 'pageup',
    wx.WXK_NUMPAD_RIGHT         : 'right',
    wx.WXK_NUMPAD_SUBTRACT      : '-',
    wx.WXK_NUMPAD_UP            : 'up',
    wx.WXK_NUMPAD0              : '0',
    wx.WXK_NUMPAD1              : '1',
    wx.WXK_NUMPAD2              : '2',
    wx.WXK_NUMPAD3              : '3',
    wx.WXK_NUMPAD4              : '4',
    wx.WXK_NUMPAD5              : '5',
    wx.WXK_NUMPAD6              : '6',
    wx.WXK_NUMPAD7              : '7',
    wx.WXK_NUMPAD8              : '8',
    wx.WXK_NUMPAD9              : '9',
    wx.WXK_PAGEDOWN             : 'pagedown',
    wx.WXK_PAGEUP               : 'pageup',
    wx.WXK_PAUSE                : 'break',
    wx.WXK_RETURN               : 'enter',
    wx.WXK_RIGHT                : 'right',
    wx.WXK_SCROLL               : 'scroll_lock',
    wx.WXK_SHIFT                : 'shift',
    wx.WXK_SNAPSHOT             : 'snapshot',
    wx.WXK_SPACE                : 'space',
    wx.WXK_TAB                  : 'tab',
    wx.WXK_UP                   : 'up',
    wx.WXK_WINDOWS_LEFT         : 'Lwin',
    wx.WXK_WINDOWS_MENU         : 'appskey',
    wx.WXK_WINDOWS_RIGHT        : 'Rwin',
    ## wx.WXK_CONTROL_A            : 'a',
    ## wx.WXK_CONTROL_B            : 'b',
    ## wx.WXK_CONTROL_C            : 'c',
    ## wx.WXK_CONTROL_D            : 'd',
    ## wx.WXK_CONTROL_E            : 'e',
    ## wx.WXK_CONTROL_F            : 'f',
    ## wx.WXK_CONTROL_G            : 'g',
    ## wx.WXK_CONTROL_H            : 'h', # 8=WXK_BACK (C-h)
    ## wx.WXK_CONTROL_I            : 'i', # 9=WXK_TAB (C-i)
    ## wx.WXK_CONTROL_J            : 'j',
    ## wx.WXK_CONTROL_K            : 'k',
    ## wx.WXK_CONTROL_L            : 'l',
    ## wx.WXK_CONTROL_M            : 'm', # 13=WXK_RETURN (C-m)
    ## wx.WXK_CONTROL_N            : 'n',
    ## wx.WXK_CONTROL_O            : 'o',
    ## wx.WXK_CONTROL_P            : 'p',
    ## wx.WXK_CONTROL_Q            : 'q',
    ## wx.WXK_CONTROL_R            : 'r',
    ## wx.WXK_CONTROL_S            : 's',
    ## wx.WXK_CONTROL_T            : 't',
    ## wx.WXK_CONTROL_U            : 'u',
    ## wx.WXK_CONTROL_V            : 'v',
    ## wx.WXK_CONTROL_W            : 'w',
    ## wx.WXK_CONTROL_X            : 'x',
    ## wx.WXK_CONTROL_Y            : 'y',
    ## wx.WXK_CONTROL_Z            : 'z',
}

def speckey_state(key):
    k = next((k for k,v in speckeys.items() if v == key), None)
    if k:
        return wx.GetKeyState(k) #cf. wx.GetMouseState


def hotkey(evt):
    """Interpret evt.KeyCode as Hotkey string and overwrite evt.key.
    The modifiers are aranged in the same order as matplotlib as
    [LR]win + ctrl + alt(meta) + shift.
    """
    key = evt.GetKeyCode()
    mod = ""
    for k,v in ((wx.WXK_WINDOWS_LEFT, 'Lwin-'),
                (wx.WXK_WINDOWS_RIGHT, 'Rwin-'),
                (wx.WXK_CONTROL, 'C-'),
                (wx.WXK_ALT,     'M-'),
                (wx.WXK_SHIFT,   'S-')):
        if key != k and wx.GetKeyState(k):
            mod += v
    
    key = mod + (speckeys.get(key) or chr(key).lower())
    if key:
        head, sep, tail = key.rpartition('-')
        evt.rawkey = tail or sep
    else:
        evt.rawkey = key
    evt.key = key
    return key


def regulate_key(key):
    return (key.replace("ctrl+",  "C-") # modifier keys abbreviation
               .replace("alt+",   "M-")
               .replace("shift+", "S-")
               .replace("win+", "win-")
               .replace("M-C-", "C-M-") # modifier key regulation C-M-S-
               .replace("S-M-", "M-S-")
               .replace("S-C-", "C-S-"))


## --------------------------------
## Interfaces of Controls
## --------------------------------

def funcall(f, doc=None, alias=None, **kwargs):
    """Decorator as curried function with `doc (`alias)
    equiv. (lambda *v: f`alias<'doc'>(*v, **kwargs))
    """
    @wraps(f)
    def _Act(*v):
        return f(*v, **kwargs) # ufunc with one event args
    action = _Act
    
    ## event 引数などが省略できるかどうかチェックし，
    ## 省略できる場合 (kwargs で必要な引数が与えられる場合) その関数を返す
    ## 
    ## Check if the event argument etc. can be omitted,
    ## If it can be (if required arguments are given by kwargs) return the function.
    ## 
    def explicit_args(args, defaults):
        ## k = len(args) - n - len(kwargs) # NG
        ## defaults と kwargs がかぶることがある．次のようにして引数を数える
        n = len(defaults or ())
        xargs = args[:-n] if n else args # explicit, non-default args that must be given
        k = len(xargs)                   # if k > 0: kwargs must give the rest (xargs)
        for kw in kwargs:
            if kw not in args:
                raise TypeError("{} got an unexpected keyword {!r}".format(f, kw))
            if kw in xargs:
                k -= 1
        return k
    
    if not inspect.isbuiltin(f):
        args, _varargs, _keywords, defaults = getargspec(f)
        k = explicit_args(args, defaults)
        if k == 0 or inspect.ismethod(f) and k == 1: # 暗黙の引数 'self' は除く
            @wraps(f)
            def _Act2(*v):
                return f(**kwargs) # function with no explicit args
            action = _Act2
    else:
        ## Builtin functions don't have an argspec that we can get.
        ## Try alalyzing the doc:str to get argspec info.
        try:
            m = re.search("(\w+)\((.*)\)", inspect.getdoc(f))
            name, argspec = m.groups()
            args = [x for x in argspec.strip().split(',') if x]
            defaults = re.findall("\w+\s*=(\w+)", argspec)
            k = explicit_args(args, defaults)
            if k == 0:
                @wraps(f)
                def _Act3(*v):
                    return f(**kwargs) # function with no explicit args
                action = _Act3
        except TypeError:
            raise
        except Exception:
            pass
    
    action.__name__ = str(alias or f.__name__) #.replace('<lambda>', 'lambda'))
    action.__doc__ = doc if doc is not None else f.__doc__
    return action


def postcall(f):
    """A decorator of wx.CallAfter
    Post event message to call `f in app.
    Wx posts the message that forces calling `f to take place in the main thread.
    """
    @wraps(f)
    def _f(*args, **kwargs):
        wx.CallAfter(f, *args, **kwargs)
    _f.__name__ = f.__name__
    _f.__doc__ = f.__doc__
    return _f


def connect(obj, event, f=None, **kwargs):
    """An event binder: equiv. obj.Bind(event, f) -> f"""
    if not f:
        return lambda f: connect(obj, event, f, **kwargs)
    obj.Bind(event, lambda v: f(v, **kwargs))
    return f


def disconnect(obj, event, f=None):
    """An event unbinder: equiv. obj.Unbind(event, f) -> f"""
    return obj.Unbind(event, handler=f)


def skip(v):
    v.Skip()


class CtrlInterface(object):
    """Mouse/Key event interface class
    """
    handler = property(lambda self: self.__handler)
    
    def __init__(self):
        self.__key = ''
        self.__handler = FSM({})
        
        self.handler.update({ #<CtrlInterface handler>
            0 : {
                 '* dclick' : (0, skip),
                '* pressed' : (0, skip),
               '* released' : (0, skip),
            },
        })
        
        ## self.Bind(wx.EVT_CHAR, self.on_char) # for TextCtrl only
        
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_press)
        self.Bind(wx.EVT_KEY_UP, self.on_key_release)
        self.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel)
        
        self.Bind(wx.EVT_MOTION, lambda v: self.window_handler('motion', v))
        self.Bind(wx.EVT_SET_FOCUS, lambda v: self.window_handler('focus_set', v))
        self.Bind(wx.EVT_KILL_FOCUS, lambda v: self.window_handler('focus_kill', v))
        self.Bind(wx.EVT_ENTER_WINDOW, lambda v: self.window_handler('window_enter', v))
        self.Bind(wx.EVT_LEAVE_WINDOW, lambda v: self.window_handler('window_leave', v))
        
        self.Bind(wx.EVT_LEFT_DOWN, lambda v: self.mouse_handler('Lbutton pressed', v))
        self.Bind(wx.EVT_RIGHT_DOWN, lambda v: self.mouse_handler('Rbutton pressed', v))
        self.Bind(wx.EVT_MIDDLE_DOWN, lambda v: self.mouse_handler('Mbutton pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DOWN, lambda v: self.mouse_handler('Xbutton1 pressed', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DOWN, lambda v: self.mouse_handler('Xbutton2 pressed', v))
        
        self.Bind(wx.EVT_LEFT_UP, lambda v: self.mouse_handler('Lbutton released', v))
        self.Bind(wx.EVT_RIGHT_UP, lambda v: self.mouse_handler('Rbutton released', v))
        self.Bind(wx.EVT_MIDDLE_UP, lambda v: self.mouse_handler('Mbutton released', v))
        self.Bind(wx.EVT_MOUSE_AUX1_UP, lambda v: self.mouse_handler('Xbutton1 released', v))
        self.Bind(wx.EVT_MOUSE_AUX2_UP, lambda v: self.mouse_handler('Xbutton2 released', v))
        
        self.Bind(wx.EVT_LEFT_DCLICK, lambda v: self.mouse_handler('Lbutton dclick', v))
        self.Bind(wx.EVT_RIGHT_DCLICK, lambda v: self.mouse_handler('Rbutton dclick', v))
        self.Bind(wx.EVT_MIDDLE_DCLICK, lambda v: self.mouse_handler('Mbutton dclick', v))
        self.Bind(wx.EVT_MOUSE_AUX1_DCLICK, lambda v: self.mouse_handler('Xbutton1 dclick', v))
        self.Bind(wx.EVT_MOUSE_AUX2_DCLICK, lambda v: self.mouse_handler('Xbutton2 dclick', v))
    
    def on_char(self, evt): #<wx._core.KeyEvent>
        """Called when char inputs (in TextCtrl)
        if and when self.on_key_press calls evt.Skip()
        """
        evt.key = key = chr(evt.GetKeyCode())
        self.handler('{} pressed'.format(key), evt)
    
    def on_key_press(self, evt): #<wx._core.KeyEvent>
        """Called when key down"""
        key = hotkey(evt)
        self.__key = regulate_key(key + '+')
        self.handler('{} pressed'.format(key), evt)
    
    def on_key_release(self, evt): #<wx._core.KeyEvent>
        """Called when key up"""
        key = hotkey(evt)
        self.__key = ''
        self.handler('{} released'.format(key), evt)
    
    def on_mousewheel(self, evt): #<wx._core.MouseEvent>
        """Called when wheel event"""
        ## if evt.WheelAxis: # [left|right] <= phoenix 4.0.7
        if evt.GetWheelAxis():
            p = 'right' if evt.WheelRotation > 0 else 'left'
        else:
            p = 'up' if evt.WheelRotation > 0 else 'down'
        evt.key = self.__key + "wheel{}".format(p)
        self.handler('{} pressed'.format(evt.key), evt)
    
    def window_handler(self, event, evt):
        self.handler(event, evt)
        evt.Skip()
    
    def mouse_handler(self, event, evt): #<wx._core.MouseEvent>
        """Called when mouse event"""
        event = self.__key + event  # 'key+[LMRX]button pressed/released/dclick'
        evt.key = event.rsplit()[0] # event-key removes 'pressed/released/dclick'
        self.handler(event, evt)


class KeyCtrlInterfaceMixin(object):
    """Keymap interface mixin
    
    This interface class defines extended keymaps for inherited class handler.
    The class that mixes this in must have,
      - handler <FSM>
      - message <statusbar>
    
    map : event key name that excluds 'pressed'
        global-map : (0 :default)
         ctl-x-map : 'ctrl+x'
          spec-map : 'ctrl+c'
           esc-map : 'escape'
    """
    message = print
    
    def make_keymap(self, keymap, state=0, default=0):
        """Make a basis of extension map in the handler.
        """
        def _Pass(v):
            self.message("{} {}".format(keymap, v.key))
        _Pass.__name__ = str('pass')
        
        keyevent = keymap +' pressed'
        
        self.handler.update({ #<KeyCtrlInterfaceMixin handler>
            state : {
                       keyevent : [keymap, self.prefix_command_hook],
            },
            keymap : {
                         'quit' : [default, ],
                    '* pressed' : [default, _Pass],
                 '*alt pressed' : [keymap, _Pass],
                '*ctrl pressed' : [keymap, _Pass],
               '*shift pressed' : [keymap, _Pass],
             '*[LR]win pressed' : [keymap, _Pass],
            },
        })
    
    def prefix_command_hook(self, evt):
        win = wx.Window.FindFocus()
        if isinstance(win, wx.TextEntry) and win.StringSelection\
        or isinstance(win, stc.StyledTextCtrl) and win.SelectedText:
          # or any other of pre-selection-p?
            self.handler('quit', evt)
            evt.Skip()
            return
        self.message(evt.key + '-')
    
    def define_key(self, keymap, action=None, doc=None, alias=None, **kwargs):
        """Define [map key-pressed] action at default 0=state
        If no action, invalidates the keymap and returns a decor @ keymap-binder.
        keymap must be in C-M-S order (ctrl + alt(meta) + shift).
        """
        keymap = regulate_key(keymap)
        ls = keymap.rsplit(' ', 1)
        map, key = ls if len(ls)>1 else (0, ls[0])
        if map == '*':
            map = None
        
        if map not in self.handler: # make key map automatically
            self.make_keymap(map)
        
        self.handler[map][key+' pressed'] = transaction = [0] # overwrite transaction
        self.handler.validate(map)
        if action:
            transaction.append(funcall(action, doc, alias, **kwargs))
            return action
        return lambda f: self.define_key(keymap, f, doc, alias, **kwargs)


## --------------------------------
## wx Framework and Designer
## --------------------------------

def ID_(id): # Free ID - どこで使っているか検索できるように．
    return id + wx.ID_HIGHEST # not to use [ID_LOWEST(4999):ID_HIGHEST(5999)]


def pack(self, *args, **kwargs):
    """Do layout
  usage:
    self.SetSizer(
        pack(self,
            (label, 0, wx.ALIGN_CENTER|wx.LEFT, 4),
            ( ctrl, 1, wx.ALIGN_CENTER|wx.LEFT, 4),
        )
    )
    *args : wx objects `obj (with some packing directives)
          - (obj, 1) ... packed by size with ratio 1 (orient 同じ方向)
                         他に 0 以外を指定しているオブジェクトとエリアを分け合う
          - (obj, x, wx.EXPAND) ... packed with expand (orient の垂直方向に引き伸ばす) with ratio
          - (obj, 0, wx.ALIGN_CENTER|wx.LEFT, 4) ... packed at center with 4 pixel at wx.LEFT
          - ((-1,-1), 1, wx.EXPAND) ... stretched space
          - wx.StaticLine(self) ... border
          - (-1,-1) ... a fix blank
 **kwargs : 
   orient : HORIZONTAL or VERTICAL
    style : (proportion=0, flag=0, border=2)
             proportion = EXPAND
                 border = TOP, BOTTOM, LEFT, RIGHT, ALL
                  align = ALIGN_CENTER, ALIGN_LEFT, ALIGN_TOP, ALIGN_RIGHT, ALIGN_BOTTOM,
                          ALIGN_CENTER_VERTICAL, ALIGN_CENTER_HORIZONTAL
    label : label of StaticBox
    """
    label = kwargs.get("label")
    orient = kwargs.get("orient") or wx.HORIZONTAL
    style = kwargs.get("style") or (0, wx.EXPAND|wx.ALL, 0)
    
    if label is not None:
        box = wx.StaticBox(self, -1, label)
        sizer = wx.StaticBoxSizer(box, orient)
    else:
        sizer = wx.BoxSizer(orient)
    
    for item in args:
        if item is None:
            item = ((0,0), 0,0,0) # dummy spacing
        if not item:
            item = ((0,0),) + style # padding with specified style
        try:
            sizer.Add(item, *style) # using style
        except Exception:
            sizer.Add(*item) # using item-specific style
    return sizer


class TreeList(object):
    def __init__(self, ls=None):
        self.__items = ls or []
    
    def __getattr__(self, attr):
        return getattr(self.__items, attr)
    
    def __contains__(self, k):
        return self.getf(self.__items, k)
    
    def __iter__(self):
        return self.__items.__iter__()
    
    def __getitem__(self, k):
        if isinstance(k, LITERAL_TYPE):
            return self.getf(self.__items, k) or []
        return self.__items.__getitem__(k)
    
    def __setitem__(self, k, v):
        if isinstance(k, LITERAL_TYPE):
            return self.setf(self.__items, k, v)
        return self.__items.__setitem__(k, v)
    
    def __delitem__(self, k):
        if isinstance(k, LITERAL_TYPE):
            return self.delf(self.__items, k)
        return self.__items.__delitem__(k)
    
    def __str__(self):
        return pformat(self.__items)
    
    def items(self, root=None):
        """Generates all branches [key, value(s)]"""
        for branch in root or self:
            if not branch:
                continue
            key, data = branch[0], branch[-1]
            if not isinstance(data, (list, tuple)):
                yield branch
            else:
                for v in self.items(data):
                    yield v
    
    @classmethod
    def getf(self, ls, key):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.getf(la, b)
            return # None item
        return next((x[-1] for x in ls if x and x[0] == key), None)
    
    @classmethod
    def setf(self, ls, key, value):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.setf(la, b, value)
            p, key = key.rsplit('/', 1)
            return self.setf(ls, p, [[key, value]]) # >>> ls[p].append([key, value])
        try:
            li = next((x for x in ls if x and x[0] == key), None)
            if li is not None:
                if isinstance(value, list):
                    li[-1][:] = value # assign value:list to items:list
                else:
                    li[-1] = value # assign value to item (li must be a list)
            else:
                ls.append([key, value]) # append to items:list
        except (TypeError, AttributeError)  as e:
            print("- TreeList:warning [{}]".format(key), e)
    
    @classmethod
    def delf(self, ls, key):
        if '/' in key:
            p, key = key.rsplit('/', 1)
            ls = self.getf(ls, p)
        ls.remove(next(x for x in ls if x and x[0] == key))


class Menu(wx.Menu):
    def __init__(self, owner, values):
        wx.Menu.__init__(self)
        self.owner = owner
        self.Id = None
        
        for item in values:
            if not item:
                self.AppendSeparator()
                
            elif isinstance(item[0], LITERAL_TYPE): # Submenu
                argv = item[:-1]
                subitems = item[-1]
                submenu = Menu(owner, subitems)
                ## if len(argv) > 1:
                ##     submenu.SetTitle(argv[1])
                submenu_item = wx.MenuItem(self, wx.ID_ANY, *argv, kind=wx.ITEM_CHECK)
                submenu_item.SetSubMenu(submenu)
                ## submenu_item.SetBitmap(wx.NullBitmap) # ビットマップ設定用 (現バージョンは無効)
                self.Append(submenu_item)
                submenu.Id = submenu_item.Id # <- ID_ANY
                self.Enable(submenu_item.Id, bool(subitems)) # 空のメニューは無効にする
                
            elif isinstance(item[0], tuple): # :old-menu-style
                    self.append_items(*item)
            else:
                handlers = list(filter(callable, item)) # :new-menu-style
                argv = item[:-len(handlers) or None]
                self.append_items(argv, *handlers)
    
    def append_items(self, argv, handler1=None, handler2=None, handler3=None):
        id = argv[0]
        if id == -1:
            print("- Menu:warning: Id(-1) given as NewId") # may cause resource error
            id = wx.NewId()
            argv = (id,) + argv[1:]
        
        bitmap = None
        if isinstance(argv[-1], wx.Bitmap): # the last argument is bitmap
            bitmap = argv[-1]
            argv = argv[:-1]
        
        item = wx.MenuItem(self, *argv)
        if bitmap:
            item.SetBitmap(bitmap)
        self.Append(item)
        
        if handler1:
            self.owner.Unbind(wx.EVT_MENU, id=id)
            self.owner.Bind(wx.EVT_MENU, handler1, id=id)
        if handler2:
            self.owner.Unbind(wx.EVT_UPDATE_UI, id=id)
            self.owner.Bind(wx.EVT_UPDATE_UI, handler2, id=id)
        if handler3:
            self.owner.Unbind(wx.EVT_MENU_HIGHLIGHT, id=id)
            self.owner.Bind(wx.EVT_MENU_HIGHLIGHT, handler3, id=id)
    
    @staticmethod
    def Popup(parent, menu, *args):
        menu = Menu(parent, menu)
        parent.PopupMenu(menu, *args)
        menu.Destroy()


class MenuBar(wx.MenuBar, TreeList):
    """Construt menubar as is orderd map
    
    ネストされたリストの順番どおりに GUI 上にマップしたメニューバーを構築する
    menus <list> is the root of nest list (as directory structrue)
    root
     ├ key ─┬ item
     │       ├ item
     │       ├ key ─┬ item
     │       │       ├ item ...
    [key, [item:
          ((id, text, hint, *style, *bitmap), ... Menu.Append arguments
                *action, *updater, *hilight), ... Menu Event handlers
    ]],
    style : menu style in (ITEM_SEPARATOR, ITEM_NORMAL, ITEM_CHECK, ITEM_RADIO, ITEM_MAX)
   bitmap : menu icon (Bitmap object)
   action : EVT_MENU にバインドされるハンドラ
  updater : EVT_UPDATE_UI にバインドされるハンドラ
  hilight : EVT_MENU_HIGHLIGHT にバインドされるハンドラ
    """
    def __init__(self, *args, **kwargs):
        wx.MenuBar.__init__(self, *args, **kwargs)
        TreeList.__init__(self)
    
    def getmenu(self, root, key):
        key = key.replace('\\','/')
        if '/' in key:
            a, b = key.split('/', 1)
            branch = self.getmenu(root, a)
            return self.getmenu(branch, b)
        if root is None:
            return next((menu for menu,label in self.Menus if menu.Title == key), None)
        ## return next((item.SubMenu for item in root.MenuItems if item.Text == key), None)
        return next((item.SubMenu for item in root.MenuItems if item.ItemLabel == key), None)
    
    def update(self, key):
        """Call when the menulist is changed,
        Updates items of the menu that has specified `key: root/branch
        """
        if self.Parent:
            menu = self.getmenu(None, key)
            if not menu:     # 新規のメニューアイテムを挿入する
                self.reset() # リセットして終了
                return
            
            for item in menu.MenuItems: # remove and delete all items
                menu.Delete(item)
            
            menu2 = Menu(self.Parent, self[key]) # new menu2 to swap menu
            for item in menu2.MenuItems:
                menu.Append(menu2.Remove(item)) # 重複しないようにいったん切り離して追加する
                
            ## cf. Menu.submenu.Id
            if menu.Id:
                self.Enable(menu.Id, menu.MenuItemCount > 0) # 空のメニューは無効にする
    
    def reset(self):
        """Call when the menulist is changed,
        Recreates menubar if the Parent were attached by SetMenuBar
        """
        if self.Parent:
            for j in range(self.GetMenuCount()): # remove and del all attached root-menu
                menu = self.Remove(0)
                menu.Destroy()
            
            for j, (key, values) in enumerate(self):
                menu = Menu(self.Parent, values) # 空のメインメニューでも表示に追加する
                self.Append(menu, key)
                if not values:
                    self.EnableTop(j, False) # 空のメインメニューは無効にする


class StatusBar(wx.StatusBar):
    """Construt statusbar with read/write
    
   field : list of field widths
    pane : index of status text field
    """
    lock = None
    
    def __init__(self, *args, **kwargs):
        wx.StatusBar.__init__(self, *args, **kwargs)
    
    def __call__(self, *args, **kwargs):
        text = ' '.join(str(v) for v in args)
        if not self.lock:
            return self.write(text, **kwargs)
        return text
    
    def resize(self, field):
        self.SetFieldsCount(len(field))
        self.SetStatusWidths(list(field)) # oldver requires list type
    
    def write(self, text, pane=0):
        if text and text[0] == '\b':
            text = self.read(pane) + text[1:]
        self.SetStatusText(text, pane % self.GetFieldsCount())
        return text
    
    def read(self, pane=0):
        return self.GetStatusText(pane % self.GetFieldsCount())



class Frame(wx.Frame, KeyCtrlInterfaceMixin):
    """Frame base class
    
    menubar : MenuBar
  statusbar : StatusBar
  inspector : Inspector frame of the shell
    """
    handler = property(lambda self: self.__handler)
    message = property(lambda self: self.statusbar)
    
    def __init__(self, *args, **kwargs):
        wx.Frame.__init__(self, *args, **kwargs)
        
        self.inspector = InspectorFrame(None, target=self)
        
        ## statusbar/menubar などのカスタマイズを行う
        ## レイアウト系コマンドは statusbar/menubar の作成後
        
        self.menubar = MenuBar()
        self.menubar["File"] = [
            (ID_(1), "&Inspector\tF12", "Shell for object inspection", wx.ITEM_CHECK,
                lambda v: (self.inspector.Show(),
                           self.inspector.shell.SetFocus()),
                lambda v: v.Check(self.inspector.IsShown())),
            (),
            (wx.ID_EXIT, "E&xit\tCtrl-w", "Exit the program",
                lambda v: self.Close()),
                
            (wx.ID_ABOUT, "&About\tF1", "About this software",
                lambda v: self.About()),
        ]
        self.SetMenuBar(self.menubar)
        self.menubar.reset()
        
        ## ステータスバーを作成し，起動されたタイマーのカウントを出力する
        self.statusbar = StatusBar(self)
        self.statusbar.resize((-1,78))
        self.SetStatusBar(self.statusbar)
        
        ## ステータスバーに時刻表示 (/msec)
        ## self.timer = wx.PyTimer(
        ##     lambda: self.statusbar.write(time.strftime('%m/%d %H:%M'), -1))
        self.timer = wx.Timer(self)
        self.timer.Start(1000)
        self.Bind(wx.EVT_TIMER,
            lambda v: self.statusbar.write(time.strftime('%m/%d %H:%M'), -1))
        
        ## AcceleratorTable mimic
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)
        
        def close(v):
            """Close the window and exit the program"""
            self.Close()
        
        self.__handler = FSM({})
        
        self.handler.update({ #<Frame handler>
            0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
            },
        })
        self.make_keymap('C-x')
    
    def OnCharHook(self, evt):
        """Called when key down (let the handler call skip event)"""
        self.handler('{} pressed'.format(hotkey(evt)), evt)
    
    def About(self):
        wx.MessageBox(__import__('__main__').__doc__ or 'no information',
                        caption="About this software")
    
    def Destroy(self):
        self.timer.Stop()
        self.inspector.Destroy() # inspector is not my child
        return wx.Frame.Destroy(self)



class MiniFrame(wx.MiniFrame, KeyCtrlInterfaceMixin):
    """MiniFrame base class
    
    menubar : MenuBar (not created by default)
  statusbar : StatusBar (not shown by default)
    """
    handler = property(lambda self: self.__handler)
    message = property(lambda self: self.statusbar)
    
    def __init__(self, *args, **kwargs):
        wx.MiniFrame.__init__(self, *args, **kwargs)
        
        ## To disable, self.SetMenuBar(None)
        self.menubar = MenuBar()
        self.SetMenuBar(self.menubar)
        
        self.statusbar = StatusBar(self)
        self.statusbar.Show(0)
        self.SetStatusBar(self.statusbar)
        
        ## To defalut close, use self.Unbind(wx.EVT_CLOSE)
        self.Bind(wx.EVT_CLOSE, lambda v: self.Show(0)) # hide only, no skip
        
        ## AcceleratorTable mimic
        self.Bind(wx.EVT_CHAR_HOOK, self.OnCharHook)
        
        def close(v):
            """Close the window"""
            self.Close()
        
        self.__handler = FSM({})
        
        self.handler.update({ #<MiniFrame handler>
            0 : {
                    '* pressed' : (0, skip),
                  'M-q pressed' : (0, close),
            },
        })
        self.make_keymap('C-x')
    
    def OnCharHook(self, evt):
        """Called when key down (let the handler call skip event)"""
        self.handler('{} pressed'.format(hotkey(evt)), evt)
    
    def Destroy(self):
        return wx.MiniFrame.Destroy(self)



class InspectorFrame(MiniFrame):
    """MiniFrame of shell for inspection, debug, and break `target
-------------------------------------------------------------------
     target : Inspection target `self, any wx.Object, otherwise __main__
      shell : Nautilus Inspector shell based on <wx.py.shell.Shell>
      ghost : Notebook <Editor> as an tooltip ghost in the shell
    scratch : temporary buffer for scratch text
       Help : temporary buffer for help
        Log : logging buffer
    History : shell history (read only)
    
Prefix:
        C-x : extention map for the frame
        C-c : spefific map for the editors and the shell
        
Global bindings:
        C-f : Find text
        M-f : Filter text
    """
    def __init__(self, parent, target=None, title=None,
            size=(1000,500), style=wx.DEFAULT_FRAME_STYLE, **kwargs):
        MiniFrame.__init__(self, parent, size=size, style=style)
        
        if target is None:
            target = __import__('__main__')
        
        self.SetTitle(title or "Nautilus - {!r}".format(target))
        
        self.statusbar.resize((-1,200))
        self.statusbar.Show(1)
        
        self.shell = Nautilus(self, target, **kwargs)
        
        self.scratch = Editor(self)
        self.Help = Editor(self)
        self.Log = Editor(self)
        self.History = Editor(self)
        
        ## self.Log.ViewEOL = True
        self.Log.ViewWhiteSpace = True
        
        self.ghost = aui.AuiNotebook(self, size=(600,400),
            style = (aui.AUI_NB_DEFAULT_STYLE|aui.AUI_NB_BOTTOM)
                  &~(aui.AUI_NB_CLOSE_ON_ACTIVE_TAB|aui.AUI_NB_MIDDLE_CLICK_CLOSE)
        )
        self.ghost.AddPage(self.scratch, "*scratch*")
        self.ghost.AddPage(self.Help,    "*Help*")
        self.ghost.AddPage(self.Log,     "Log")
        self.ghost.AddPage(self.History, "History")
        
        self._mgr = aui.AuiManager()
        self._mgr.SetManagedWindow(self)
        self._mgr.AddPane(self.shell, aui.AuiPaneInfo().Name("shell").CenterPane())
        self._mgr.AddPane(self.ghost, aui.AuiPaneInfo().Name("ghost").Right().Show(0)
            .Caption("Ghost in the Shell").CaptionVisible(1).Gripper(0))
        self._mgr.Update()
        
        self.findDlg = None
        self.findData = wx.FindReplaceData(wx.FR_DOWN|wx.FR_MATCHCASE)
        
        self.Bind(wx.EVT_FIND, self.OnFindNext)
        self.Bind(wx.EVT_FIND_NEXT, self.OnFindNext)
        self.Bind(wx.EVT_FIND_CLOSE, self.OnFindClose)
        
        _P = funcall
        
        self.handler.update({ #<InspectorFrame handler>
            0 : {
                   'f1 pressed' : (0, self.About),
                  'M-c pressed' : (0, self.OnFilterSetStyling),
                  'M-f pressed' : (0, self.OnFilterSetStyling, self.OnFilterText),
                  'C-f pressed' : (0, self.OnFindText),
                   'f3 pressed' : (0, self.OnFindNext),
                 'S-f3 pressed' : (0, self.OnFindPrev),
                  'f11 pressed' : (0, _P(self.PopupWindow, show=None, doc="Toggle the ghost")),
                'S-f11 pressed' : (0, _P(self.PopupWindow, show=True, doc="Show the ghost")),
                  'f12 pressed' : (0, _P(self.Close, alias="close", doc="Close the window")),
                'S-f12 pressed' : (0, _P(self.shell.clear)),
                'C-f12 pressed' : (0, _P(self.shell.clone)),
            },
        })
        
        @self.define_key('C-x j', win=self.scratch, doc="Show scratch window")
        @self.define_key('C-x l', win=self.Log, doc="Show Log window")
        @self.define_key('C-x h', win=self.Help, doc="Show Help window")
        @self.define_key('C-x C-h', win=self.History, doc="Show History")
        def popup(v, win, show=True):
            self.PopupWindow(win, show)
        
        @self.define_key('S-f11', loop=True)
        @self.define_key('Xbutton1', p=-1)
        @self.define_key('Xbutton2', p=+1)
        def other_editor(v, p=1, loop=False):
            "Focus moves to other editor"
            j = self.ghost.Selection + p
            if loop:
                j %= self.ghost.PageCount
            self.ghost.SetSelection(j)
        
        @self.define_key('M-right', p=1)
        @self.define_key('M-left', p=-1)
        def other_window(v, p=1):
            "Focus moves to other window"
            pages = (self.ghost.GetPage(i) for i in range(self.ghost.PageCount))
            pages = [self.shell] + [w for w in pages if w.IsShownOnScreen()]
            j = (pages.index(self.current_editor) + p) % len(pages)
            pages[j].SetFocus()
        
        @self.define_key('C-d')
        def duplicate(v):
            """Duplicate an expression at the caret-line"""
            win = self.current_editor
            text = win.SelectedText or win.pyrepr_at_caret
            if text:
                self.shell.clearCommand()
                self.shell.write(text, -1)
                self.shell.SetFocus()
        
        f = os.path.expanduser("~/.deb/deb-logging.log")
        if os.path.exists(f):
            if sys.version_info >= (3,0):
                with open(f, newline='') as i:
                    self.Log.Value = i.read()
            else:
                with open(f) as i:
                    self.Log.Value = i.read()
    
    def Destroy(self):
        f = os.path.expanduser("~/.deb/deb-logging.log")
        if sys.version_info >= (3,0):
            with open(f, 'w', newline='') as o:
                o.write(self.Log.Value)
        else:
            with open(f, 'w') as o:
                o.write(self.Log.Value)
        
        f = os.path.expanduser("~/.deb/deb-history.log")
        with open(f, 'w') as o:
            o.write("#! Last updated: <{}>\r\n".format(datetime.datetime.now()))
            o.write(self.History.Value)
        
        self._mgr.UnInit()
        return MiniFrame.Destroy(self)
    
    def About(self, evt=None):
        self.Help.SetValue('\n\n'.join((
            "#<module 'mwx' from {!r}>".format(__file__),
            "Author: {!r}".format(__author__),
            "Version: {!s}".format(__version__),
            ## __doc__,
            self.__doc__,
            self.shell.__doc__,
            
            "================================\n" # Thanks to wx.py.shell
            "#{!r}".format(wx.py.shell),
            "Author: {!r}".format(wx.py.version.__author__),
            "Version: {!s}".format(wx.py.version.VERSION),
            wx.py.__doc__,
            wx.py.shell.__doc__,
            "*original{}".format(wx.py.shell.HELP_TEXT.lower()),
            
            "================================\n" # Thanks are also due to phoenix
            "#{!r}".format(wx),
            "To show the credit, press C-M-Mbutton.",
            ))
        )
        self.PopupWindow(self.Help)
    
    def PopupWindow(self, win=None, show=True):
        """Popup ghost window
        win : the editor window in the gohst
       show : True, False, otherwise None:toggle
        """
        if show is None:
            show = not self.ghost.IsShown()
            self.ghost.Show(show) # when floating ghost, has the Shown flag no effect?
        self._mgr.GetPane(self.ghost).Show(show)
        self._mgr.Update()
        if win:
            j = self.ghost.GetPageIndex(win) # win=None -> -1
            self.ghost.SetSelection(j)
            self.shell.SetFocus()
    
    ## --------------------------------
    ## Find text dialog
    ## --------------------------------
    
    @property
    def current_editor(self):
        win = wx.Window.FindFocus()
        if isinstance(win, wx.MiniFrame): # floating ghost ?
            return self.ghost.CurrentPage # select the Editor window
        
        ## pages = (self.scratch, self.Help, self.Log, self.History)
        pages = (self.ghost.GetPage(i) for i in range(self.ghost.PageCount))
        if win in pages:
            return win
        return self.shell # default editor
    
    def OnFilterSetStyling(self, evt):
        win = self.current_editor
        if wx.VERSION >= (4,1,0):
            win.StartStyling(0)
        else:
            win.StartStyling(0, 0x1f)
        win.SetStyling(0, stc.STC_P_WORD3) # is dummy selection necessary?
    
    @postcall
    def OnFilterText(self, evt):
        win = self.current_editor
        word = win.topic_at_caret.encode()
        if word:
            text = win.GetText().encode() # for multi-byte string
            pos = text.find(word)
            n = 0
            while pos in range(win.TextLength):
                if wx.VERSION >= (4,1,0):
                    win.StartStyling(pos)
                else:
                    win.StartStyling(pos, 0x1f)
                win.SetStyling(len(word), stc.STC_P_WORD3)
                pos = text.find(word, pos+1)
                n += 1
            self.findData.FindString = word
            self.message("{}: {} found".format(word.decode(), n))
    
    ## *** The following code is a modification of <wx.py.frame.Frame> ***
    
    def OnFindText(self, evt):
        if self.findDlg is not None:
            self.findDlg.SetFocus()
            return
        
        win = self.current_editor
        self.findData.FindString = win.topic_at_caret
        self.findDlg = wx.FindReplaceDialog(win, self.findData,
                            "Find", style=wx.FR_NOWHOLEWORD|wx.FR_NOUPDOWN)
        self.findDlg.Show()
    
    def OnFindNext(self, evt, backward=False): #<wx._core.FindDialogEvent>
        if self.findDlg:
            self.findDlg.Close()
            self.findDlg = None
        
        data = self.findData
        down_p = data.Flags & wx.FR_DOWN
        if (backward and down_p) or (not backward and not down_p):
            data.Flags ^= wx.FR_DOWN # toggle up/down flag
        
        win = self.current_editor # or self.findDlg.Parent #<EditWindow>
        win.DoFindNext(data)
    
    def OnFindPrev(self, evt):
        self.OnFindNext(evt, backward=True)
    
    def OnFindClose(self, evt): #<wx._core.FindDialogEvent>
        self.findDlg.Destroy()
        self.findDlg = None



class EditorInterface(CtrlInterface, KeyCtrlInterfaceMixin):
    """Python code editor interface with Keymap
    """
    message = print
    
    def __init__(self):
        CtrlInterface.__init__(self)
        
        def fork_parent(v):
            try:
                self.parent.handler(self.handler.current_event, v)
            except AttributeError:
                pass
        
        _P = funcall
        
        self.handler.update({ #<Editor handler>
            -1 : {  # original action of the Editor
                    '* pressed' : (0, skip, lambda v: self.message("ESC {}".format(v.key))),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
            },
            0 : {
             '*button* pressed' : (0, skip, fork_parent),
            '*button* released' : (0, skip, fork_parent),
                    '* pressed' : (0, skip),
               'escape pressed' : (-1, _P(lambda v: self.message("ESC-"), alias="escape")),
               'insert pressed' : (0, _P(lambda v: self.over(None), "toggle-over")),
                   'f9 pressed' : (0, _P(lambda v: self.wrap(None), "toggle-fold-type")),
                  'C-l pressed' : (0, _P(lambda v: self.recenter(), "recenter")),
                'C-S-l pressed' : (0, _P(lambda v: self.recenter(-1), "recenter-bottom")),
               'C-M-up pressed' : (0, _P(lambda v: self.ScrollLines(-2), "scroll-up")),
             'C-M-down pressed' : (0, _P(lambda v: self.ScrollLines(+2), "scroll-down")),
               'C-left pressed' : (0, _P(self.WordLeft)),
              'C-right pressed' : (0, _P(self.WordRightEnd)),
               'C-S-up pressed' : (0, _P(self.LineUpExtend)),
             'C-S-down pressed' : (0, _P(self.LineDownExtend)),
             'C-S-left pressed' : (0, _P(self.selection_backward_word_or_paren)),
            'C-S-right pressed' : (0, _P(self.selection_forward_word_or_paren)),
                  'C-a pressed' : (0, _P(self.beggining_of_line)),
                  'C-e pressed' : (0, _P(self.end_of_line)),
                  'M-a pressed' : (0, _P(self.back_to_indentation)),
                  'M-e pressed' : (0, _P(self.end_of_line)),
                  'C-k pressed' : (0, _P(self.kill_line)),
                'C-S-f pressed' : (0, _P(self.set_mark)), # override key
              'C-space pressed' : (0, _P(self.set_mark)),
              'S-space pressed' : (0, skip),
          'C-backspace pressed' : (0, skip),
          'S-backspace pressed' : (0, _P(self.backward_kill_line)),
                  ## 'C-d pressed' : (0, ),
                  ## 'C-/ pressed' : (0, ), # cf. C-a home
                  ## 'C-\ pressed' : (0, ), # cf. C-e end
                ## 'M-S-, pressed' : (0, _P(self.goto_char, pos=0, doc="beginning-of-buffer")),
                ## 'M-S-. pressed' : (0, _P(self.goto_char, pos=-1, doc="end-of-buffer")),
            },
        })
        
        self.define_key('C-c C-c', self.goto_matched_paren, "goto matched paren")
        
        ## EditWindow.OnUpdateUI は Shell.OnUpdateUI によってオーバーライドされるので
        ## ここでは別途に EVT_STC_UPDATEUI ハンドラを追加する (EVT_UPDATE_UI ではない !)
        
        ## cf. wx.py.editwindow.EditWindow.OnUpdateUI => Check for matching braces
        self.Bind(stc.EVT_STC_UPDATEUI, self.OnMatchBrace) # no skip
        
        ## Keyword(2) setting
        self.SetLexer(stc.STC_LEX_PYTHON)
        self.SetKeyWords(0, ' '.join(keyword.kwlist))
        self.SetKeyWords(1, ' '.join(builtins.__dict__))
        
        ## Global style for all languages
        ## wx.Font style
        ##    family : DEFAULT, DECORATIVE, ROMAN, SCRIPT, SWISS, MODERN, TELETYPE
        ##     slant : NORMAL, SLANT, ITALIC
        ##    weight : NORMAL, LIGHT, BOLD
        ## underline : False
        ## font = wx.Font(9, wx.MODERN, wx.NORMAL, wx.NORMAL, False, "MS Gothic")
        ## self.StyleSetFont(stc.STC_STYLE_DEFAULT, font)
        
        ## self.StyleClearAll()
        ## self.SetSelForeground(True, wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT))
        ## self.SetSelBackground(True, wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT))
        
        ## self.SetCaretStyle(stc.STC_CARETSTYLE_LINE)
        ## self.SetCaretWidth(2)
        ## self.SetCaretForeground("#000000")
        ## self.SetCaretLineBackground("#ffff00")
        ## self.SetCaretLineVisible(1)
        
        ## default no magin for line number
        self.SetMarginLeft(2)
        
        ## default style of control-char
        ## self.ViewEOL = True
        ## self.ViewWhiteSpace = True
        
        self.WrapMode = 0
        self.WrapIndentMode = 1
        
        ## custom constants to be embedded in stc
        stc.STC_P_WORD3 = 16
        
        self.MarkerDefine(0, stc.STC_MARK_CIRCLE,    '#0080f0', "#0080f0") # o:blue-mark
        self.MarkerDefine(1, stc.STC_MARK_ARROW,     '#000000', "#ffffff") # >:fold-arrow
        self.MarkerDefine(2, stc.STC_MARK_ARROWDOWN, '#000000', "#ffffff") # v:expand-arrow
        self.MarkerDefine(3, stc.STC_MARK_ARROW,     '#7f0000', "#ff0000")
        self.MarkerDefine(4, stc.STC_MARK_ARROWDOWN, '#7f0000', "#ff0000")
        
        self.MarkerSetAlpha(0, 0x80)
        ## m = 0
        ## self.SetMarginType(0, stc.STC_MARGIN_SYMBOL)
        ## self.SetMarginMask(0, 0xffff^(1<<m)) # marker display mask
        ## self.SetMarginMask(1, 1<<m)
        ## self.SetMarginWidth(0, 10)
        ## self.SetMarginSensitive(0,True)
        ## self.SetMarginSensitive(1,True)
        ## 
        ## @connect(self, stc.EVT_STC_MARGINCLICK)
        ## def on_margin_click(v):
        ##     self.handler("margin_clicked", v)
        ##     v.Skip()
        
        self.__mark = None
    
    mark = property(
        lambda self: self.get_mark(),
        lambda self,v: self.set_mark(v),
        lambda self: self.del_mark())
    
    def get_mark(self):
        return self.__mark
    
    def set_mark(self, pos=None, marker=0):
        if pos is None:
            pos = self.cur
        elif pos < 0:
            pos += self.TextLength + 1
        if marker == 0:
            self.__mark = pos
            self.MarkerDeleteAll(0)
        self.MarkerAdd(self.LineFromPosition(pos), marker)
    
    def del_mark(self):
        self.__mark = None
    
    def set_style(self, spec=None, **kwargs):
        spec = spec and spec.copy() or {}
        spec.update(kwargs)
        
        if "STC_STYLE_DEFAULT" in spec:
            self.StyleSetSpec(stc.STC_STYLE_DEFAULT, spec.pop("STC_STYLE_DEFAULT"))
            self.StyleClearAll()
        
        if "STC_STYLE_LINENUMBER" in spec:
            lxc = spec["STC_STYLE_LINENUMBER"]
            
            ## [0] for numbers, 0 pixels wide, mask=0 (default?)
            ## [1] for symbols, 16 pixels wide, mask=0x1ffffff
            ## [2] for folding, 1 pixels wide, mask=0
            self.SetMarginType(1, stc.STC_MARGIN_NUMBER)
            self.SetMarginType(2, stc.STC_MARGIN_SYMBOL) # margin(2) for symbols
            self.SetMarginMask(2, stc.STC_MASK_FOLDERS) # set up mask for folding symbols
            self.SetMarginWidth(1, 32 if lxc else 0)
            self.SetMarginWidth(2, 1 if lxc else 0)
            
            for lx in lxc.split(','):
                key, value = lx.partition(':')[::2]
                if key == 'fore': # set colors used as a chequeboard pattern
                    self.SetFoldMarginColour(True, value) # back: one of the colors
                    self.SetFoldMarginHiColour(True, value) # fore: other color (same as the one)
        
        ## Custom style for caret and line colour
        if "STC_STYLE_CARETLINE" in spec:
            lxc = spec.pop("STC_STYLE_CARETLINE")
            
            self.SetCaretLineVisible(0) # no back
            for lx in lxc.split(','):
                key, value = lx.partition(':')[::2]
                
                if key == 'fore':
                    self.SetCaretForeground(value)
                
                elif key == 'back':
                    self.SetCaretLineBackground(value)
                    self.SetCaretLineVisible(1)
                
                elif key == 'size':
                    self.SetCaretWidth(int(value))
                    self.SetCaretStyle(stc.STC_CARETSTYLE_LINE)
                
                elif key == 'bold':
                    self.SetCaretStyle(stc.STC_CARETSTYLE_BLOCK)
        
        for key, value in spec.items():
            self.StyleSetSpec(getattr(stc, key), value)
    
    def OnMatchBrace(self, evt):
        cur = self.cur
        if self.following_char in "({[<":
            pos = self.BraceMatch(cur)
            if pos != -1:
                self.BraceHighlight(cur, pos) # matched to following char
            else:
                self.BraceBadLight(cur)
        elif self.preceding_char in ")}]>":
            pos = self.BraceMatch(cur-1)
            if pos != -1:
                self.BraceHighlight(pos, cur-1) # matched to preceding char
            else:
                self.BraceBadLight(cur-1)
        else:
            self.BraceHighlight(-1,-1) # no highlight
    
    def over(self, mode=1):
        """Set overwt(insertion) mode. toggle when mode is None"""
        self.Overtype = mode if mode is not None else not self.Overtype
        self.Refresh()
    
    def wrap(self, mode=1):
        """Set fold type (override) of wrap
        mode in {0:no-wrap, 1:word-wrap (2:no-word-wrap), None:toggle}
        """
        self.WrapMode = mode if mode is not None else not self.WrapMode
    
    def recenter(self, ln=None):
        """Scroll the cursor line to the center of screen (ln default None)
        if ln=0, the cursor goes top of the screen. ln=-1 the bottom
        """
        n = self.LinesOnScreen() # lines completely visible
        ln = self.CurrentLine - (n/2 if ln is None else ln%n if ln < n else n)
        self.ScrollToLine(ln)
    
    ## --------------------------------
    ## Attributes of the editor
    ## --------------------------------
    following_char = property(lambda self: chr(self.GetCharAt(self.cur)))
    preceding_char = property(lambda self: chr(self.GetCharAt(self.cur-1)))
    
    @property
    def following_symbol(self):
        ln = self.GetTextRange(self.cur, self.eol)
        return next((c for c in ln if not c.isspace()), '')
    
    @property
    def preceding_symbol(self):
        ln = self.GetTextRange(self.bol, self.cur)[::-1]
        return next((c for c in ln if not c.isspace()), '')
    
    cur = property(lambda self: self.CurrentPos)
    
    @property
    def bol(self):
        """beginning of line"""
        text, lp = self.CurLine
        return self.cur - lp
        ## return self.PositionFromLine(self.CurrentLine)
    
    @property
    def eol(self):
        """end of line"""
        text, lp = self.CurLine
        ## if text[-2:] == '\r\n': lp += 2
        ## elif text[-1:] == '\n': lp += 1
        if text.endswith(os.linesep):
            lp += len(os.linesep)
        return (self.cur - lp + len(text.encode()))
    
    @property
    def pyrepr_at_caret(self):
        """Pythonic expression at the caret
        The caret scouts back and forth to scoop a chunk of expression.
        """
        ## ls = self.GetTextRange(self.bol, self.cur)
        ## rs = self.GetTextRange(self.cur, self.eol)
        text, lp = self.CurLine
        ls, rs = text[:lp], text[lp:]
        lhs = get_words_backward(ls) or ls.rpartition(' ')[-1]
        rhs = get_words_forward(rs) or rs.partition(' ')[0]
        return lhs + rhs
    
    @property
    def topic_at_caret(self):
        """Topic word at the caret or selected substring
        The caret scouts back and forth to scoop a topic.
        """
        return self.get_selection_or_topic()
    
    @property
    def right_paren(self):
        if self.following_char in "({[<":
            return self.BraceMatch(self.cur) # (0 <= cur < pos+1)
        return -1
    
    @property
    def left_paren(self):
        if self.preceding_char in ")}]>":
            return self.BraceMatch(self.cur-1) # (0 <= pos < cur-1)
        return -1
    
    @property
    def right_quotation(self):
        text = self.GetTextRange(self.cur, self.TextLength)
        if text and text[0] in "\"\'":
            try:
                lexer = shlex.shlex(text)
                return self.cur + len(lexer.get_token())
            except ValueError:
                pass # no closing quotation
        return -1
    
    @property
    def left_quotation(self):
        text = self.GetTextRange(0, self.cur)[::-1]
        if text and text[0] in "\"\'":
            try:
                lexer = shlex.shlex(text)
                return self.cur - len(lexer.get_token())
            except ValueError:
                pass # no closing quotation
        return -1
    
    ## --------------------------------
    ## Goto, Skip, Selection, etc.
    ## --------------------------------
    
    def goto_char(self, pos):
        if pos < 0:
            pos += self.TextLength + 1 # end-of-buffer (+1:\0)
        self.GotoPos(pos)
        return self.cur
    
    def select_char(self, pos):
        if pos < 0:
            pos += self.TextLength + 1 # end-of-buffer (+1:\0)
        self.SetCurrentPos(pos)
        return self.cur
    
    def goto_line(self, ln):
        if ln < 0:
            ln += self.LineCount
        self.GotoLine(ln)
        return self.cur
    
    def skip_chars_forward(self, rexpr='\s'):
        p = re.compile(rexpr)
        while p.search(self.following_char):
            c = self.cur
            if c == self.TextLength:
                break
            self.GotoPos(c + 1)
        return self.cur
    
    def skip_chars_backward(self, rexpr='\s'):
        p = re.compile(rexpr)
        while p.search(self.preceding_char):
            c = self.cur
            if c == 0:
                break
            self.GotoPos(c - 1)
        return self.cur
    
    def back_to_indentation(self):
        self.ScrollToColumn(0)
        self.GotoPos(self.bol)
        return self.skip_chars_forward('\s')
    
    def beggining_of_line(self):
        self.ScrollToColumn(0)
        self.GotoPos(self.bol)
        return self.cur
    
    def end_of_line(self):
        self.GotoPos(self.eol)
        return self.cur
    
    def goto_matched_paren(self):
        p = self.right_paren
        if p != -1:
            return self.GotoPos(p+1)
        p = self.left_paren
        if p != -1:
            return self.GotoPos(p)
        q = self.right_quotation
        if q != -1:
            return self.GotoPos(q)
        q = self.left_quotation
        if q != -1:
            return self.GotoPos(q)
    
    def selection_forward_word_or_paren(self):
        p = self.right_paren
        if p != -1:
            self.SetCurrentPos(p+1) # forward selection to parenthesized words
            return
        q = self.right_quotation
        if q != -1:
            self.SetCurrentPos(q) # forward selection to quoted words
            return
        self.WordRightEndExtend()  # othewise, extend selection forward word
    
    def selection_backward_word_or_paren(self):
        p = self.left_paren
        if p != -1:
            self.SetCurrentPos(p) # backward selection to parenthesized words
            return
        q = self.left_quotation
        if q != -1:
            self.SetCurrentPos(q) # forward selection to quoted words
            return
        self.WordLeftExtend() # otherwise, extend selection backward word
    
    def get_selection_or_topic(self):
        """selected substring or topic word at the caret"""
        topic = self.SelectedText
        if topic:
            return topic
        with self.save_excursion():
            ## org = self.cur # save-excursion
            p = q = self.cur
            if not self.preceding_char.isspace():
                self.WordLeft()
                p = self.cur
            if not self.following_char.isspace():
                self.WordRightEnd()
                q = self.cur
            ## self.GotoPos(org) # restore-excursion
            return self.GetTextRange(p, q)
    
    def save_excursion(self):
        return self.Excursion(self)
    
    class Excursion(object):
        def __init__(self, target):
            self.target = target
        
        def __enter__(self):
            self.pos = self.target.cur
        
        def __exit__(self, t, v, tb):
            self.target.GotoPos(self.pos)
    
    ## --------------------------------
    ## Edit /eat /kill
    ## --------------------------------
    
    def eat_white_forward(self):
        p = self.cur
        q = self.skip_chars_forward('\s')
        self.Replace(p, q, '')
    
    def eat_white_backward(self):
        p = self.cur
        q = self.skip_chars_backward('\s')
        self.Replace(max(q, self.bol), p, '')
    
    def kill_line(self):
        if self.CanEdit():
            p = self.eol
            ## if p == self.cur:
            ##     if self.GetTextRange(p, p+2) == '\r\n': p += 2
            ##     elif self.GetTextRange(p, p+1) == '\n': p += 1
            text, lp = self.CurLine
            if text[:lp] == os.linesep:
                p += len(os.linesep)
            self.Replace(self.cur, p, '')
    
    def backward_kill_line(self):
        if self.CanEdit():
            p = self.bol
            ## if p == self.cur:
            ##     n = len(sys.ps2)
            ##     if self.GetTextRange(p-2, p) == '\r\n': p -= 2
            ##     elif self.GetTextRange(p-1, p) == '\n': p -= 1
            ##     elif self.GetTextRange(p-n, p) == sys.ps2: p -= n
            text, lp = self.CurLine
            if text[:lp] == '' and p: # caret at the beginning of the line
                p -= len(os.linesep)
            elif text[:lp] == sys.ps2: # caret at the prompt head
                p -= len(sys.ps2)
            self.Replace(p, self.cur, '')


class Editor(EditWindow, EditorInterface):
    """Python code editor
    """
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    PALETTE_STYLE = { #<Editor>
      # Default style for all languages
        "STC_STYLE_DEFAULT"     : "fore:#000000,back:#ffffb8,face:MS Gothic,size:9",
        "STC_STYLE_CARETLINE"   : "fore:#000000,back:#ffff7f,size:2",
        "STC_STYLE_LINENUMBER"  : "fore:#000000,back:#ffffb8,size:9",
        "STC_STYLE_BRACELIGHT"  : "fore:#000000,back:#ffffb8,bold",
        "STC_STYLE_BRACEBAD"    : "fore:#000000,back:#ff0000,bold",
        "STC_STYLE_CONTROLCHAR" : "size:9",
      # Python lexical style
        "STC_P_DEFAULT"         : "fore:#000000,back:#ffffb8",
        "STC_P_IDENTIFIER"      : "fore:#000000",
        "STC_P_COMMENTLINE"     : "fore:#007f7f,back:#ffcfcf",
        "STC_P_COMMENTBLOCK"    : "fore:#007f7f,back:#ffcfcf,eol",
        "STC_P_CHARACTER"       : "fore:#7f7f7f",
        "STC_P_STRING"          : "fore:#7f7f7f",
        "STC_P_TRIPLE"          : "fore:#7f7f7f,eol",
        "STC_P_TRIPLEDOUBLE"    : "fore:#7f7f7f,eol",
        "STC_P_STRINGEOL"       : "fore:#7f7f7f",
        "STC_P_WORD"            : "fore:#0000ff",
        "STC_P_WORD2"           : "fore:#b8007f",
        "STC_P_WORD3"           : "fore:#ff0000,back:#ffff00", # custom style for search word
        "STC_P_DEFNAME"         : "fore:#0000ff,bold",
        "STC_P_CLASSNAME"       : "fore:#0000ff,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#7f0000",
    }
    
    def __init__(self, parent, **kwargs):
        EditWindow.__init__(self, parent, **kwargs)
        EditorInterface.__init__(self)
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        
        ## To prevent @filling from *HARD-CRASH*
        ## We never allow DnD of text, file, etc.
        self.SetDropTarget(None)
        
        self.set_style(self.PALETTE_STYLE)


class Nautilus(Shell, EditorInterface):
    """Shell of the Nautilus with Editor interface
--------------------------------------------------
Features:
    All objects in the process can be accessed
    using
        self : the target of the shell,
        this : the module which includes target.
    
    So as you are diving into the sea of python process,
    watch, change, and break everything in the target.
    
    Nautilus supports you to dive confortably with
    special syntax, several utilities, five autocomp modes, etc.
    See below.

Magic syntax:
   backquote : x`y --> y=x  | x`y`z --> z=y=x
    pullback : x@y --> y(x) | x@y@z --> z(y(x))
     apropos : x.y? [not] p --> shows apropos (not-)matched by predicates `p
                equiv. apropos(y, x [,ignorecase ?:True,??:False] [,pred=p])
                y can contain regular expressions.
                    (RE) \\a:[a-z], \\A:[A-Z] can be used in addition.
                p can be ?atom, ?callable, ?instance(*types), and
                    predicates imported from inspect
                    e.g., isclass, ismodule, ismethod, isfunction, etc.
  
  *     info :  ?x (x@?) --> info(x) shows short information
  *     help : ??x (x@??) --> help(x) shows full description
  *   system :  !x (x@!) --> sx(x) executes command in external shell
  
  * denotes original syntax defined in wx.py.shell,
    for which, at present version, enabled with USE_MAGIC switch being on

Shell built-in utility:
    @p          synonym of print
    @pp         synonym of pprint
    @info   @?  short info
    @help   @?? full description
    @dive       clone the shell with new target
    @timeit     measure the duration cpu time
    @execute    exec in the locals (PY2-compatible)
    @filling    inspection using wx.lib.filling.Filling
    @watch      inspection using wx.lib.inspection.InspectionTool
    @edit       open with your editor (undefined)
    @file       inspect.getfile -> str
    @code       inspect.getsource -> str
    @module     inspect.getmodule -> module

Autocomp key bindings:
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
  * Autocomps are incremental when pressed any alnums, and decremental when backspace.

Enter key bindings:
     C-enter : insert-line-break
     S-enter : execute-command

This module is based on the implementation of wx.py.shell.
    Some of the original key bindings are overrided in the FSM framework.
    To read the original key bindings, see 'wx.py.shell.HELP_TEXT'.
    The original key bindings are mapped in esc-map, i.e.,
    e.g., if you want to do 'select-all', type [ESC C-a], not [C-a]
    
The most convenient way to see the details of keymaps on the shell:
    >>> self.shell.handler @p
     or self.shell.handler @filling
    
Flaky nutshell:
    Half-baked by Patrik K. O'Brien,
    and the other half by K. O'moto ;)
    """
    target = property(lambda self: self.__target)
    parent = property(lambda self: self.__parent)
    message = property(lambda self: self.__parent.statusbar)
    
    @target.setter
    def target(self, target):
        self.__target = target
        target.self = target
        try:
            target.this = sys.modules[target.__module__]
        except Exception:
            target.this = __import__('__main__')
        target.shell = self
        
        self.interp.locals.update(target.__dict__)
        try:
            self.parent.Title = re.sub(
                "(.*) - (.*)", "\\1 - {!r}".format(target), self.parent.Title)
        except Exception:
            pass
    
    ## Default classvar string to Execute when starting the shell was deprecated.
    ## You should better describe the starter in your script ($PYTHONSTARTUP:~/.py)
    ## SHELLSTARTUP = ""
    
    PALETTE_STYLE = { #<Shell>
     ## Default style for all languages
        "STC_STYLE_DEFAULT"     : "fore:#cccccc,back:#202020,face:MS Gothic,size:9",
        "STC_STYLE_CARETLINE"   : "fore:#ffffff,back:#012456,size:2",
        "STC_STYLE_LINENUMBER"  : "fore:#000000,back:#f0f0f0,size:9",
        "STC_STYLE_BRACELIGHT"  : "fore:#ffffff,back:#202020,bold",
        "STC_STYLE_BRACEBAD"    : "fore:#ffffff,back:#ff0000,bold",
        "STC_STYLE_CONTROLCHAR" : "size:9",
     ## Python lexical style
        "STC_P_DEFAULT"         : "fore:#cccccc,back:#202020",
        "STC_P_IDENTIFIER"      : "fore:#cccccc",
        "STC_P_COMMENTLINE"     : "fore:#42c18c,back:#004040",
        "STC_P_COMMENTBLOCK"    : "fore:#42c18c,back:#004040,eol",
        "STC_P_CHARACTER"       : "fore:#a0a0a0",
        "STC_P_STRING"          : "fore:#a0a0a0",
        "STC_P_TRIPLE"          : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_TRIPLEDOUBLE"    : "fore:#a0a0a0,back:#004040,eol",
        "STC_P_STRINGEOL"       : "fore:#808080",
        "STC_P_WORD"            : "fore:#80a0ff",
        "STC_P_WORD2"           : "fore:#ff80ff",
        "STC_P_WORD3"           : "fore:#ff0000,back:#ffff00", # optional for search word
        "STC_P_DEFNAME"         : "fore:#e0c080,bold",
        "STC_P_CLASSNAME"       : "fore:#e0c080,bold",
        "STC_P_DECORATOR"       : "fore:#e08040",
        "STC_P_OPERATOR"        : "",
        "STC_P_NUMBER"          : "fore:#ffc080",
    }
    
    def __init__(self, parent, target, locals=None,
                        introText = None,
                    startupScript = None,
                execStartupScript = True):
        Shell.__init__(self, parent, locals=target.__dict__,
                        introText = introText,
                    startupScript = startupScript,
                execStartupScript = execStartupScript) # if True, executes ~/.py
        EditorInterface.__init__(self)
        
        if locals:
            self.interp.locals.update(locals)
        
        self.modules = find_modules(force=speckey_state('ctrl')
                                         &speckey_state('shift'))
        
        self.__parent = parent #= self.Parent, but not always if whose son is floating
        self.__target = target # see interp <wx.py.interpreter.Interpreter>
        
        wx.py.shell.USE_MAGIC = True
        wx.py.shell.magic = self.magic # called when USE_MAGIC
        
        ## このシェルはプロセス内で何度もコールされることが想定されます．
        ## デバッグポイントとして使用される場合，また，クローンされる場合がそうです．
        ## ビルトインがデッドオブジェクトを参照することにならないように以下の方法で回避します．
        ## 
        ## This shell is expected to be called many times in the process,
        ## e.g., when used as a debug point and when cloned.
        ## To prevent the builtins from referring dead objects, we use the following method.
        ## 
        ## Assign objects each time it is activated so that the target
        ## does not refer to dead objects in the shell clones (to be deleted).
        @connect(self.parent, wx.EVT_ACTIVATE)
        def on_activate(v):
            self.handler('shell_activated' if v.Active else 'shell_inactivated', self)
            v.Skip()
        
        self.on_activated(self)
        
        ## Keywords(2) setting for *STC_P_WORD*
        self.SetKeyWords(0, ' '.join(keyword.kwlist))
        self.SetKeyWords(1, ' '.join(builtins.__dict__)
                          + ' self this help info dive timeit execute puts')
        
        self.Bind(wx.EVT_UPDATE_UI, self.OnUpdate)
        
        ## テキストドラッグの禁止
        ## We never allow DnD of text, file, etc.
        self.SetDropTarget(None)
        
        def clear(v):
            ## Clear selection and statusline, no skip.
            ## *do not* clear autocomp, so that the event can skip to AutoComp properly.
            ## if self.AutoCompActive():
            ##     self.AutoCompCancel() # may delete selection
            if self.CanEdit():
                self.ReplaceSelection("")
            self.message("")
        
        def fork(v):
            self.handler.fork(v) # fork event to 0=default
        
        _P = funcall
        
        self.handler.update({ #<Shell handler>
            None : {
                'shell_cloned' : [ None, ],
             'shell_activated' : [ None, self.on_activated ],
           'shell_inactivated' : [ None, ],
            },
            -1 : { # original action of the wx.py.shell
                    '* pressed' : (0, skip, lambda v: self.message("ESC {}".format(v.key))),
                 '*alt pressed' : (-1, ),
                '*ctrl pressed' : (-1, ),
               '*shift pressed' : (-1, ),
             '*[LR]win pressed' : (-1, ),
            },
            0 : { # Normal mode
             '*f[0-9]* pressed' : (0, ),
                    '* pressed' : (0, skip),
               'escape pressed' : (-1, self.OnEscape),
                'space pressed' : (0, self.OnSpace),
           '*backspace pressed' : (0, self.OnBackspace),
               '*enter pressed' : (0, ), # --> OnShowCompHistory 無効
                'enter pressed' : (0, self.OnEnter),
              'S-enter pressed' : (0, self.OnEnter),
              'C-enter pressed' : (0, _P(self.insertLineBreak)),
                 ## 'C-up pressed' : (0, _P(lambda v: self.OnHistoryReplace(+1), "prev-command")),
               ## 'C-down pressed' : (0, _P(lambda v: self.OnHistoryReplace(-1), "next-command")),
               ## 'C-S-up pressed' : (0, ), # --> Shell.OnHistoryInsert(+1) 無効
             ## 'C-S-down pressed' : (0, ), # --> Shell.OnHistoryInsert(-1) 無効
                 'M-up pressed' : (0, _P(self.goto_previous_mark)),
               'M-down pressed' : (0, _P(self.goto_next_mark)),
                  'C-a pressed' : (0, _P(self.beggining_of_command_line)),
                  'C-e pressed' : (0, _P(self.end_of_command_line)),
                  'M-j pressed' : (0, self.call_tooltip2),
                  'C-j pressed' : (0, self.call_tooltip),
                  'M-h pressed' : (0, self.call_ghost),
                  'C-h pressed' : (0, self.call_autocomp),
                    '. pressed' : (2, self.OnEnterDot), # autoCompleteKeys -> AutoCompShow
                  'tab pressed' : (1, self.call_history_comp),
                  'M-p pressed' : (1, self.call_history_comp),
                  'M-n pressed' : (1, self.call_history_comp),
                  'M-. pressed' : (2, self.call_word_autocomp),
                  'M-/ pressed' : (3, self.call_apropos_autocomp),
                  'M-, pressed' : (4, self.call_text_autocomp),
                  'M-m pressed' : (5, self.call_module_autocomp),
            },
            1 : { # history auto completion S-mode
                         'quit' : (0, clear),
                    '* pressed' : (0, fork),
                  '*up pressed' : (1, self.on_completion_forward), # 古いヒストリへ進む
                '*down pressed' : (1, self.on_completion_backward), # 新しいヒストリへ戻る
               'S-left pressed' : (1, skip),
              'S-right pressed' : (1, skip),
              'shift* released' : (1, self.call_history_comp),
                  'tab pressed' : (1, self.on_completion_forward),
                'S-tab pressed' : (1, self.on_completion_backward),
                  'M-p pressed' : (1, self.on_completion_forward),
                  'M-n pressed' : (1, self.on_completion_backward),
                'enter pressed' : (0, lambda v: self.goto_char(-1)),
               'escape pressed' : (0, clear),
            '[a-z0-9_] pressed' : (1, skip),
           '[a-z0-9_] released' : (1, self.call_history_comp),
             'S-[a-z\] pressed' : (1, skip),
            'S-[a-z\] released' : (1, self.call_history_comp),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (1, ),
                '*ctrl pressed' : (1, ),
               '*shift pressed' : (1, ),
             '*[LR]win pressed' : (1, ),
             '*f[0-9]* pressed' : (1, ),
            },
            2 : { # word auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (2, self.on_completion_backward, skip),
                 'down pressed' : (2, self.on_completion_forward, skip),
               'S-left pressed' : (2, skip),
              'S-right pressed' : (2, skip),
              'shift* released' : (2, self.call_word_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, skip),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (2, skip),
          '[a-z0-9_.] released' : (2, self.call_word_autocomp),
             'S-[a-z\] pressed' : (2, skip),
            'S-[a-z\] released' : (2, self.call_word_autocomp),
              '*delete pressed' : (2, skip),
           '*backspace pressed' : (2, self.skipback_autocomp, skip),
          '*backspace released' : (2, self.call_word_autocomp, self.decrback_autocomp),
                  'M-j pressed' : (2, self.call_tooltip2),
                  'C-j pressed' : (2, self.call_tooltip),
                  'M-h pressed' : (2, self.call_ghost),
                  'C-h pressed' : (2, self.call_autocomp),
                  ## 'M-. pressed' : (2, self.on_completion),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (2, ),
                '*ctrl pressed' : (2, ),
               '*shift pressed' : (2, ),
             '*[LR]win pressed' : (2, ),
             '*f[0-9]* pressed' : (2, ),
            },
            3 : { # apropos auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (3, self.on_completion_backward, skip),
                 'down pressed' : (3, self.on_completion_forward, skip),
               'S-left pressed' : (3, skip),
              'S-right pressed' : (3, skip),
              'shift* released' : (3, self.call_apropos_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, skip),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (3, skip),
          '[a-z0-9_.] released' : (3, self.call_apropos_autocomp),
             'S-[a-z\] pressed' : (3, skip),
            'S-[a-z\] released' : (3, self.call_apropos_autocomp),
              '*delete pressed' : (3, skip),
           '*backspace pressed' : (3, self.skipback_autocomp, skip),
          '*backspace released' : (3, self.call_apropos_autocomp, self.decrback_autocomp),
                  'M-j pressed' : (3, self.call_tooltip2),
                  'C-j pressed' : (3, self.call_tooltip),
                  'M-h pressed' : (3, self.call_ghost),
                  'C-h pressed' : (3, self.call_autocomp),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, self.on_completion),
                  ## 'M-, pressed' : (4, clear, self.call_text_autocomp),
                 '*alt pressed' : (3, ),
                '*ctrl pressed' : (3, ),
               '*shift pressed' : (3, ),
             '*[LR]win pressed' : (3, ),
             '*f[0-9]* pressed' : (3, ),
            },
            4 : { # text auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (4, self.on_completion_backward, skip),
                 'down pressed' : (4, self.on_completion_forward, skip),
               'S-left pressed' : (4, skip),
              'S-right pressed' : (4, skip),
              'shift* released' : (4, self.call_text_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, skip),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (4, skip),
          '[a-z0-9_.] released' : (4, self.call_text_autocomp),
             'S-[a-z\] pressed' : (4, skip),
            'S-[a-z\] released' : (4, self.call_text_autocomp),
              '*delete pressed' : (4, skip),
           '*backspace pressed' : (4, self.skipback_autocomp, skip),
          '*backspace released' : (4, self.call_text_autocomp),
                  'M-j pressed' : (4, self.call_tooltip2),
                  'C-j pressed' : (4, self.call_tooltip),
                  'M-h pressed' : (4, self.call_ghost),
                  'C-h pressed' : (4, self.call_autocomp),
                  ## 'M-. pressed' : (2, clear, self.call_word_autocomp),
                  ## 'M-/ pressed' : (3, clear, self.call_apropos_autocomp),
                  ## 'M-, pressed' : (4, self.on_completion),
                 '*alt pressed' : (4, ),
                '*ctrl pressed' : (4, ),
               '*shift pressed' : (4, ),
             '*[LR]win pressed' : (4, ),
             '*f[0-9]* pressed' : (4, ),
            },
            5 : { # module auto completion AS-mode
                         'quit' : (0, self.clear_autocomp),
                    '* pressed' : (0, self.clear_autocomp, fork),
                   'up pressed' : (5, self.on_completion_backward, skip),
                 'down pressed' : (5, self.on_completion_forward, skip),
               'S-left pressed' : (5, skip),
              'S-right pressed' : (5, skip),
              'shift* released' : (5, self.call_module_autocomp),
                  'tab pressed' : (0, clear, skip),
                'enter pressed' : (0, clear, skip),
               'escape pressed' : (0, self.clear_autocomp),
           '[a-z0-9_.] pressed' : (5, skip),
          '[a-z0-9_.] released' : (5, self.call_module_autocomp),
             'S-[a-z\] pressed' : (5, skip),
            'S-[a-z\] released' : (5, self.call_module_autocomp),
           '*backspace pressed' : (5, self.skipback_autocomp, skip),
          '*backspace released' : (5, self.call_module_autocomp),
                 '*alt pressed' : (5, ),
                '*ctrl pressed' : (5, ),
               '*shift pressed' : (5, ),
             '*[LR]win pressed' : (5, ),
             '*f[0-9]* pressed' : (5, ),
            },
        })
        
        self.set_style(self.PALETTE_STYLE)
        
        self.__cur = 0
        self.__text = None
        self.__start = 0
        self.__history = []
        self.__bolc_marks = [self.bolc]
        self.__eolc_marks = [self.eolc]
    
    def OnUpdate(self, evt):
        if self.cur != self.__cur:
            ln = self.CurrentLine
            text, lp = self.CurLine
            self.message("{:>6d}:{} ({})".format(ln, lp, self.cur), pane=-1)
            self.__cur = self.cur
            
            if self.handler.current_state != 0:
                return
            
            text = self.pyrepr_at_caret
            if text != self.__text:
                name, argspec, tip = self.interp.getCallTip(text)
                if tip:
                    tip = tip.splitlines()[0]
                self.message(tip)
                self.__text = text
        evt.Skip()
    
    def OnEscape(self, evt):
        """Called when escape pressed"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CallTipActive():
            self.CallTipCancel()
        if self.eolc < self.bolc: # check if prompt is in valid state
            self.prompt()
        self.message("ESC-")
    
    def OnSpace(self, evt):
        """Called when space pressed"""
        if not self.CanEdit():
            return
        
        if re.match("(import|from)\s*$", self.cmdlc)\
        or re.match("from\s+([\w.]+)\s+import\s*$", self.cmdlc):
            self.ReplaceSelection(' ')
            self.handler('M-m pressed', None) # call_module_autocomp
            return
        evt.Skip()
    
    def OnBackspace(self, evt):
        """Called when backspace pressed"""
        if self.cur == self.bolc:
            ## do not skip to prevent autocomp eats prompt
            ##      so not to backspace over the latest non-continuation prompt
            if self.AutoCompActive():
                self.AutoCompCancel()
        evt.Skip()
    
    def OnEnter(self, evt):
        """Called when enter pressed"""
        if not self.CanEdit(): # go back to the end of command line
            self.goto_char(-1)
            return
        
        if self.AutoCompActive(): # skip to auto completion
            evt.Skip()
            return
        
        if self.eolc < self.bolc: # check if prompt is in valid state
            self.prompt()
            evt.Skip()
            return
        
        text = self.GetTextRange(self.bolc, self.eolc).lstrip()
        if not text or self.reader.isreading:
            evt.Skip()
            return
        
        if self.CallTipActive():
            self.CallTipCancel()
        
        ## set marks, reset history point, etc.
        self.on_text_input(text)
        
        ## skip to wx.py.magic if text begins with !(sx), ?(info), and ??(help)
        if text[0] in '!?':
            evt.Skip()
            return
        
        ## cast magic for `@?
        try:
            tokens = split_tokens(text)
            if any(x in tokens for x in '`@?'):
                cmd = self.magic_interpret(tokens)
                if '\n' in cmd:
                    self.Execute(cmd) # for multi-line commands
                else:
                    self.run(cmd, verbose=0, prompt=0)
                    self.message(cmd)
                return
        except ValueError:
            pass
        
        ## normal execute/run
        if '\n' in text:
            self.Execute(text) # for multi-line commands, no skip
        else:
            evt.Skip()
    
    def OnEnterDot(self, evt):
        """Called when dot(.) pressed"""
        sep = "`@=+-/*%<>&|^~,:; \t\r\n!?([{" # OPS; SEPARATOR_CHARS; !? and open-parens
        
        if not self.CanEdit():
            return
        
        if self.following_char.isalnum(): # e.g., self[.]abc, 0[.]123, etc.,
            self.handler('quit', evt)
        
        ## elif self.preceding_char in sep:
        elif self.preceding_symbol in sep: # i.e., skip-white-backward
            self.ReplaceSelection("self")
        
        self.ReplaceSelection('.') # just write down a dot.
        evt.Skip(False)            # and do not skip to default autocomp mode
    
    ## --------------------------------
    ## Magic suite of the shell
    ## --------------------------------
    
    def magic_interpret(self, tokens):
        """Called when [Enter] command, or eval-time for tooltip
        Interpret magic syntax
           backquote : x`y --> y=x
            pullback : x@y --> y(x)
             partial : x@(y1,..,yn) --> partial(y1,..,yn,x)
             apropos : x.y?p --> apropos(y,x,...,p)
        
        Note: This is called before run, execute, and original magic.
        """
        sep1 = "`@=+-/*%<>&|^~;\t\r\n"   # ` OPS; SEPARATOR_CHARS; nospace, nocomma
        sep2 = "`@=+-/*%<>&|^~;, \t\r\n" # @ OPS; SEPARATOR_CHARS;
        for j,c in enumerate(tokens):
            l, r = tokens[:j], tokens[j+1:]
            
            if c == '@':
                f = "{rhs}({lhs})"
                if r and r[0] == '*': # x@*y => y(*x)
                    f = "{rhs}(*{lhs})"
                    r = r[1:]
                while r and r[0].isspace(): # skip whites
                    r = r[1:]
                lhs = ''.join(l).strip() or '_'
                rhs = ''.join(extract_words_from_tokens(r, sep2)).strip()
                
                m = re.match("\(.*\)$", rhs) # x@(y,...) => partial(y,...)(x)
                if m:
                    try:
                        p = "partial{}".format(m.group(0))
                        self.eval(p)
                        rhs = p
                    except Exception:
                        pass
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + r)
            
            if c == '`':
                f = "{rhs}={lhs}"
                lhs = ''.join(l).strip() or '_'
                rhs = ''.join(extract_words_from_tokens(r, sep1)).strip()
                return self.magic_interpret([f.format(lhs=lhs, rhs=rhs)] + r)
            
            if c == '?':
                head, sep, hint = ''.join(l).rpartition('.')
                cc, pred = re.search("(\?+)\s*(.*)", c+''.join(r)).groups()
                
                return ("apropos({0!r}, {1}, ignorecase={2}, alias={1!r}, "
                        "pred={3!r}, locals=self.shell.interp.locals)".format(
                        hint.strip(), head or 'this', len(cc) < 2, pred or None))
            
            if c == sys.ps2.strip(): # ...
                i = next((k for k,a in enumerate(r) if not a.isspace()), len(r))
                return ''.join(l) + c + ''.join(r[:i]) + self.magic_interpret(r[i:])
            
            if c in ';\r\n':
                return ''.join(l) + c + self.magic_interpret(r)
            
        return ''.join(tokens)
    
    def magic(self, cmd):
        """Called before command pushed
        (override) with magic: f x => f(x) disabled
        """
        if cmd:
            if cmd[0:2] == '??': cmd = 'help({})'.format(cmd[2:])
            elif cmd[0] == '?': cmd = 'info({})'.format(cmd[1:])
            elif cmd[0] == '!': cmd = 'sx({!r})'.format(cmd[1:])
        return cmd
    
    def setBuiltinKeywords(self):
        """Create pseudo keywords as part of builtins (override)"""
        Shell.setBuiltinKeywords(self)
        
        ## Add some useful global abbreviations to builtins
        builtins.typename = typename
        builtins.apropos = apropos
        builtins.reload = reload
        builtins.partial = partial
        builtins.pp = pprint
        builtins.p = print
        builtins.watch = watch
        builtins.filling = filling
        builtins.file = inspect.getfile
        builtins.code = inspect.getsource
        builtins.module = inspect.getmodule
        
        def fileno(object):
            return (inspect.getsourcefile(object),
                    inspect.getsourcelines(object)[1])
        builtins.fileno = fileno
    
    def on_activated(self, shell):
        """Called when activated"""
        target = shell.target # cf. target.setter, new target (not locals)
        target.self = target
        try:
            target.this = sys.modules[target.__module__]
        except Exception:
            target.this = __import__('__main__')
        target.shell = self # overwrite the facade <wx.py.shell.ShellFacade>
        
        builtins.help = self.help # utilities functions to builtins (not locals)
        builtins.info = self.info # if locals could have the same name functions.
        builtins.dive = self.clone
        builtins.timeit = self.timeit
        builtins.execute = postcall(self.Execute)
        builtins.puts = postcall(lambda v: self.write(str(v)))
    
    def on_text_input(self, text):
        """Called when [Enter] text (before push)
        
        Note: The text is raw input:str, no magic cast
        """
        if text.rstrip():
            self.MarkerAdd(self.CurrentLine, 1) # input-Marker
            
            self.__bolc_marks.append(self.bolc)
            self.__eolc_marks.append(self.eolc)
    
    def on_text_output(self, text):
        """Called when [Enter] text (after push)
        
        Note: The text is raw output:str, no magic cast
        """
        lex = re.findall("File \"(.*)\", line ([0-9]+)(.*)", text) # check traceback
        if lex:
            self.MarkerAdd(self.LineFromPosition(self.__bolc_marks[-1]), 3) # error-marker
            return False
        
        ## Check if input starts with the definition of a function or a class.
        ## If so, we set the `_' variables to the function or class.
        ## m = re.match("(def|class)\s+(\w+)", text.strip())
        ## if m:
        ##     builtins._ = self.eval(m.group(2))
        return True
    
    ## --------------------------------
    ## Attributes of the shell
    ## --------------------------------
    fragmwords = set(keyword.kwlist + dir(builtins)) # to be used in text-autocomp
    
    @property
    def history(self):
        return self.__history
    
    @history.setter
    def history(self, v):
        self.__history = v
    
    @history.deleter
    def history(self):
        self.__history = []
    
    def addHistory(self, command):
        """Add command to the command history
        (override) if the command is new (i.e., not found in the head of the list).
        Then, write the command to History buffer.
        """
        if self.history and self.history[0] == command\
          or not command:
            return
        
        Shell.addHistory(self, command)
        
        ## この段階では push された直後で，次のようになっている
        ## bolc : begginning of command-line
        ## eolc : end of the output-buffer
        try:
            input = self.GetTextRange(self.bolc, self.__eolc_marks[-1])
            output = self.GetTextRange(self.__eolc_marks[-1], self.eolc)
            substr = self.GetTextRange(self.bolc, self.eolc)
            lf = '\n'
            input = (input.replace(os.linesep + sys.ps1, lf)
                          .replace(os.linesep + sys.ps2, lf)
                          .replace(os.linesep, lf)
                          .lstrip())
            if input:
                self.history[0] = input
            
            self.fragmwords |= set(re.findall("[a-zA-Z_][\w.]+", substr)) # for text-comp
            noerr = self.on_text_output(output.strip(os.linesep))
            
            ed = self.parent.History
            ed.ReadOnly = 0
            ed.write(command + os.linesep)
            ln = ed.LineFromPosition(ed.TextLength - len(command)) # pos to mark
            if noerr:
                ed.MarkerAdd(ln, 1)
            else:
                ed.MarkerAdd(ln, 3)
            ed.ReadOnly = 1
        except AttributeError:
            ## execStartupScript 実行時は出力先 (owner) が存在しないのでパス
            pass
    
    def _In(self, j):
        """Input command:str"""
        return self.GetTextRange(self.__bolc_marks[j], self.__eolc_marks[j])
    
    def _Out(self, j):
        """Output result:str"""
        marks = self.__bolc_marks[1:] + [self.bolc]
        return self.GetTextRange(self.__eolc_marks[j]+len(os.linesep), marks[j]-len(sys.ps1))
    
    def goto_previous_mark(self):
        marks = self.__bolc_marks + [self.bolc]
        j = np.searchsorted(marks, self.cur, 'left')
        if j > 0:
            self.goto_char(marks[j-1])
    
    def goto_next_mark(self):
        marks = self.__bolc_marks + [self.bolc]
        j = np.searchsorted(marks, self.cur, 'right')
        if j < len(marks):
            self.goto_char(marks[j])
    
    def clear(self):
        """Clear all text in the shell (override) and put new prompt"""
        self.ClearAll()
        self.prompt()
        self.prompt() # i dont know why twice
        self.Refresh()
        self.__bolc_marks = []
        self.__eolc_marks = []
    
    def write(self, text, pos=None):
        """Display text in the shell (override) with :option pos"""
        if pos is not None:
            self.goto_char(pos)
        if self.CanEdit():
            Shell.write(self, text)
    
    def wrap(self, mode=1):
        """Sets whether text is word wrapped (override) with
        mode in {0:no-wrap, 1:word-wrap (2:no-word-wrap), None:toggle}
        """
        EditorInterface.wrap(self, mode)
    
    ## input = classmethod(Shell.ask)
    
    bolc = property(lambda self: self.promptPosEnd, doc="begginning of command-line")
    eolc = property(lambda self: self.TextLength, doc="end of command-line")
    
    @property
    def bol(self):
        """beginning of line (override) excluding prompt"""
        text, lp = self.CurLine
        for p in (sys.ps1, sys.ps2, sys.ps3):
            if text.startswith(p):
                lp -= len(p)
                break
        return (self.cur - lp)
    
    ## cf. getCommand(), getMultilineCommand() ... caret-line-text that has a prompt (>>>)
    
    @property
    def cmdlc(self):
        """cull command-line (with no prompt)"""
        return self.GetTextRange(self.bol, self.cur)
    
    ## @property
    ## def cmdln(self):
    ##     """full command-(multi-)line (with prompts)"""
    ##     return self.GetTextRange(self.bolc, self.eolc)
    
    def beggining_of_command_line(self):
        self.goto_char(self.bolc)
        self.ScrollToColumn(0)
    
    def end_of_command_line(self):
        self.goto_char(self.eolc)
    
    def indent_line(self):
        """Auto-indent the current line"""
        line = self.GetTextRange(self.bol, self.eol) # no-prompt
        lstrip = line.strip()
        indent = self.calc_indent()
        pos = max(self.bol + len(indent),
                  self.cur + len(indent) - (len(line) - len(lstrip)))
        self.goto_char(self.eol)
        self.select_char(self.bol)
        self.ReplaceSelection(indent + lstrip)
        self.goto_char(pos)
    
    def calc_indent(self):
        """Calculate indent spaces from prefious line"""
        ## cf. wx.py.shell.Shell.prompt
        line = self.GetLine(self.CurrentLine-1)
        for p in (sys.ps1, sys.ps2, sys.ps3):
            if line.startswith(p):
                line = line[len(p):]
                break
        lstrip = line.lstrip()
        if not lstrip:
            indent = line.strip(os.linesep)
        else:
            indent = line[:(len(line)-len(lstrip))]
            if line.strip()[-1] == ':':
                m = re.match("[a-z]+", lstrip)
                if m and m.group(0) in (
                    'if','else','elif','for','while','with',
                    'def','class','try','except','finally'):
                    indent += ' '*4
        return indent
    
    ## --------------------------------
    ## Utility functions of the Shell 
    ## --------------------------------
    
    def about(self):
        """About the shell (to be overrided)"""
        print( # >>> self.write
            "#<module 'mwx' from {!r}>".format(__file__),
            "Author: {!r}".format(__author__),
            "Version: {!s}".format(__version__),
            '',
            "#{!r}".format(wx.py.shell), sep='\n', file=self)
        return Shell.about(self)
    
    def _clip(self, data):
        """Transfer data to clipboard when copy and paste
        (override) and transfer the data to the Log board
        """
        try:
            ed = self.parent.Log
            pos = ed.TextLength
            ed.write(data.Text + os.linesep)
            ed.set_mark(pos, 0)
            ed.set_mark(pos, 1)
            ed.goto_char(-1)
        except AttributeError:
            pass
        Shell._clip(self, data)
    
    def info(self, root=None):
        """Short information"""
        if root is None:
            root = self
        doc = inspect.getdoc(root) or "No information about {}".format(root)
        try:
            ed = self.parent.Help
            ed.SetValue(doc)
            self.parent.PopupWindow(ed)
        except AttributeError:
            print(doc)
            pass
    
    def help(self, root=None):
        """Full description"""
        if root is None:
            self.message("The stream is currently piped to stdout (see command porompt).")
            wx.CallAfter(pydoc.help)
            return
        doc = pydoc.plain(pydoc.render_doc(root)) or "No description about {}".format(root)
        try:
            self.message("help({})".format(typename(root)))
            ed = self.parent.Help
            ed.SetValue(doc)
            self.parent.PopupWindow(ed)
        except AttributeError:
            print(doc)
            pass
    
    def eval(self, text):
        ## return eval(text, self.__target.__dict__)
        return eval(text, self.interp.locals)
    
    def Execute(self, text):
        """Replace selection with text, run commands,
        (override) and check clock +fix finally block indent
        """
        self.__start = self.clock()
        
        ## *** The following code is a modification of <wx.py.shell.Shell.Execute>
        ##     We override (and simplified) it to make up for missing `finally`.
        lf = '\n'
        text = (text.replace(os.linesep + sys.ps1, lf)
                    .replace(os.linesep + sys.ps2, lf)
                    .replace(os.linesep, lf))
        commands = []
        c = ''
        for line in text.split(lf):
            ## if line.strip() == sys.ps2.strip():
            ##     line = ''
            lstrip = line.lstrip()
            if (lstrip and lstrip == line
                and not any(lstrip.startswith(x) for x in (
                    'else', 'elif',
                    'except', 'finally'))): # <-- add `finally` to the original code
                if c:
                    commands.append(c)
                c = line
            else:
                c += lf + line
        commands.append(c)
        
        self.Replace(self.bolc, self.eolc, '')
        for c in commands:
            self.write(c.replace(lf, os.linesep + sys.ps2))
            self.processLine()
    
    def run(self, *args, **kwargs):
        """Execute command as if it was typed in directly
        (override) and check clock
        """
        self.__start = self.clock()
        
        return Shell.run(self, *args, **kwargs)
    
    @staticmethod
    def clock():
        try:
            return time.perf_counter()
        except AttributeError:
            return time.clock()
    
    def timeit(self, *args, **kwargs):
        t = self.clock()
        print("... duration time: {:g} s".format(t-self.__start), file=self)
    
    def clone(self, target=None):
        if target is None:
            target = self.target
        elif not hasattr(target, '__dict__'):
            raise TypeError("You cannot dive into an primitive object")
        
        frame = deb(target,
             # locals=self.interp.locals,
             size=self.parent.Size,
             title="Clone of Nautilus - {!r}".format(target))
        
        ## frame.shell.__root = self
        ## frame.shell.__class__.root = property(lambda _: self)
        
        self.handler("shell_cloned", frame.shell)
        return frame.shell
    
    ## --------------------------------
    ## Auto-comp actions of the shell
    ## --------------------------------
    
    def CallTipShow(self, pos, tip):
        """Call standard ToolTip (override) and write the tips to scratch"""
        Shell.CallTipShow(self, pos, tip)
        try:
            if tip:
                ## pt = self.ClientToScreen(self.PointFromPosition(pos))
                self.parent.scratch.SetValue(tip)
        except AttributeError:
            pass
    
    def AutoCompShow(self, *args, **kwargs):
        """Display an auto-completion list.
        (override) catch AssertionError (phoenix >= 4.1.1)
        """
        try:
            Shell.AutoCompShow(self, *args, **kwargs)
        except AssertionError:
            pass
        
    def gen_tooltip(self, text):
        """Call ToolTip of the selected word or focused line"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CallTipActive():
            self.CallTipCancel()
        try:
            tokens = split_tokens(text)
            text = self.magic_interpret(tokens)
            self.CallTipShow(self.cur, pformat(self.eval(text)))
            self.message(text)
        except Exception as e:
            self.message("{}: {!r}".format(e, text))
    
    def call_tooltip2(self, evt):
        """Call ToolTip of the selected word or repr"""
        self.gen_tooltip(self.SelectedText or self.pyrepr_at_caret)
    
    def call_tooltip(self, evt):
        """Call ToolTip of the selected word or command line"""
        self.gen_tooltip(self.SelectedText or self.getCommand() or self.pyrepr_at_caret)
    
    def call_ghost(self, evt):
        try:
            text = self.SelectedText
            if text:
                self.help(self.eval(text) or '')
                return
            try:
                text = self.pyrepr_at_caret
                self.help(self.eval(text) or '')
            except Exception:
                text = self.topic_at_caret
                self.help(self.eval(text) or '')
        except Exception as e:
            self.message("{} : {!r}".format(e, text))
    
    def call_autocomp(self, evt, argp=True):
        """Call Autocomp to show a tooltip of args.
        stc.CallTipShow if argp (=1 default), otherwise stc.AutoCompShow
        """
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CallTipActive():
            self.CallTipCancel()
        if self.CanEdit():
            self.OnCallTipAutoCompleteManually(argp) # autoCallTipShow
        else:
            text = self.SelectedText or self.pyrepr_at_caret
            self.autoCallTipShow(text, False, True)
    
    def clear_autocomp(self, evt):
        """Clear Autocomp, selection, and message"""
        if self.AutoCompActive():
            self.AutoCompCancel()
        if self.CanEdit():
            self.ReplaceSelection("")
        self.message("")
    
    def skipback_autocomp(self, evt):
        """Backspace-guard from Autocomp eating over a prompt white"""
        if self.cur == self.bolc:
            ## Do not skip to prevent autocomp eats prompt
            ## so not to backspace over the latest non-continuation prompt
            if self.AutoCompActive():
                self.AutoCompCancel()
            self.handler('quit', evt)
    
    def decrback_autocomp(self, evt):
        if self.following_char.isalnum() and self.preceding_char == '.':
            pos = self.cur
            self.WordRight()
            self.SetCurrentPos(pos) # backward selection to anchor point
        elif self.cur == self.bol:
            self.handler('quit', evt)
    
    def on_completion_forward(self, evt):
        self.on_completion(evt, 1)
    
    def on_completion_backward(self, evt):
        self.on_completion(evt, -1)
    
    def on_completion(self, evt, step=0):
        """Show completion with selection"""
        try:
            N = len(self.__comp_words)
            j = self.__comp_ind + step
            j = 0 if j < 0 else j if j < N else N-1
            word = self.__comp_words[j]
            n = len(self.__comp_hint)
            pos = self.cur
            self.ReplaceSelection(word[n:]) # 選択された範囲を変更する(または挿入する)
            self.SetCurrentPos(pos) # backward selection to anchor point
            self.__comp_ind = j
        except IndexError:
            self.message("no completion words")
    
    def call_history_comp(self, evt):
        """Called when history-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            hint = self.cmdlc
            if hint.isspace() or self.bol != self.bolc:
                self.handler('quit', evt)
                self.indent_line()
                ## evt.Skip()
                return
            
            hint = hint.strip()
            ls = [x.replace('\n', os.linesep + sys.ps2)
                    for x in self.history if x.startswith(hint)] # case-sensitive match
            words = sorted(set(ls), key=ls.index, reverse=0)     # keep order, no duplication
            
            self.__comp_ind = 0
            self.__comp_hint = hint
            self.__comp_words = words
            self.on_completion(evt) # show completion always
            
            ## the latest history stacks in the head of the list (time-descending)
            self.message("[history] {} candidates matched with {!r}".format(len(words), hint))
        except Exception:
            raise
    
    def call_text_autocomp(self, evt):
        """Called when text-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            ## hint = re.split("[^\w.]+", self.cmdlc)[-1] # get the last word or possibly ''
            hint = re.search("[\w.]*$", self.cmdlc).group(0)
            
            ls = [x for x in self.fragmwords if x.startswith(hint)] # case-sensitive match
            words = sorted(ls, key=lambda s:s.upper())
            
            self.__comp_ind = 0 if words else -1
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.AutoCompShow(len(hint), ' '.join(words))
            self.message("[text] {} candidates matched with {!r}".format(len(words), hint))
        except Exception:
            raise
    
    def call_module_autocomp(self, evt):
        """Called when module-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            ## hint = re.split("[^\w.]+", self.cmdlc)[-1] # get the last word or possibly ''
            hint = re.search("[\w.]*$", self.cmdlc).group(0)
            
            m = re.match("from\s+([\w.]+)\s+import\s+(.*)", self.cmdlc)
            if m:
                text = m.group(1)
                modules = [x[len(text)+1:] for x in self.modules if x.startswith(text)]
                modules = [x for x in modules if x and '.' not in x]
            else:
                m = re.match("(import|from)\s+(.*)", self.cmdlc)
                if m:
                    if not hint: # return (not quit)
                        return
                    text = '.'
                    modules = self.modules
                else:
                    text, sep, hint = get_words_hint(self.cmdlc)
                    root = self.eval(text or 'self')
                    modules = [k for k,v in inspect.getmembers(root, inspect.ismodule)]
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in modules if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.AutoCompShow(len(hint), ' '.join(words))
            self.message("[module] {} candidates"
                         " matched with {!r} in {}".format(len(words), hint, text))
            
        except (AttributeError, NameError, SyntaxError) as e:
            self.message("{} : {!r}".format(e, text))
    
    def call_word_autocomp(self, evt):
        """Called when word-comp mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = get_words_hint(self.cmdlc)
            root = self.eval(text)
            
            if isinstance(root, (bool,int,float,type(None))):
                self.handler('quit', evt)
                self.message("- Nothing to complete")
                return
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in Dir(root) if p.match(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            self.__comp_ind = j
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.AutoCompShow(len(hint), ' '.join(words))
            self.message("[word] {} candidates"
                         " matched with {!r} in {}".format(len(words), hint, text))
            
        except re.error as e:
            self.message("re:miss compilation {!r} : {!r}".format(e, hint))
            
        except (AttributeError, NameError, SyntaxError) as e:
            self.message("{} : {!r}".format(e, text))
    
    def call_apropos_autocomp(self, evt):
        """Called when apropos mode"""
        if not self.CanEdit():
            self.handler('quit', evt)
            return
        try:
            text, sep, hint = get_words_hint(self.cmdlc)
            root = self.eval(text)
            
            if isinstance(root, (bool,int,float,type(None))):
                self.handler('quit', evt)
                self.message("- Nothing to complete")
                return
            
            P = re.compile(hint)
            p = re.compile(hint, re.I)
            words = sorted([x for x in Dir(root) if p.search(x)], key=lambda s:s.upper())
            
            j = next((k for k,w in enumerate(words) if P.match(w)),
                next((k for k,w in enumerate(words) if p.match(w)), -1))
            
            ## self.__comp_ind = j if hint.isidentifier() else -1
            self.__comp_ind = j if not hint.endswith('?') else -1
            self.__comp_hint = hint
            self.__comp_words = words
            
            self.AutoCompShow(len(hint), ' '.join(words))
            self.message("[apropos] {} candidates"
                         " matched with {!r} in {}".format(len(words), hint, text))
            
        except re.error as e:
            self.message("re:miss compilation {!r} : {!r}".format(e, hint))
            
        except (AttributeError, NameError, SyntaxError) as e:
            self.message("{} : {!r}".format(e, text))


def deb(target=None, app=None, startup=None, **kwargs):
    """Dive into the process from your diving point
    for debug, break, and inspection of the target
    --- Put me at breakpoint.
    
    target : object or module. Default None sets target as __main__.
       app : an instance of App.
                Default None may create a local App and the mainloop.
                If app is given and not started the mainloop yet,
                the app will enter the mainloop herein.
   startup : called after started up (not before)
  **kwargs : Nautilus arguments
    locals : additional context (localvars:dict) to the shell
    execStartupScript : First, execute your script ($PYTHONSTARTUP:~/.py)

Note:
    PyNoAppError will be raised when the App is missing in pocess.
    When this may cause bad traceback, please restart.
    """
    if app is None:
        app = wx.GetApp() or wx.App()
    
    frame = InspectorFrame(None, target, **kwargs)
    frame.Show()
    frame.shell.SetFocus()
    frame.Unbind(wx.EVT_CLOSE) # EVT_CLOSE surely close window
    if startup:
        try:
            startup(frame.shell)
            frame.shell.handler.bind("shell_cloned", startup)
        except Exception:
            traceback.print_exc()
            frame.shell.write(traceback.format_exc())
            frame.shell.prompt()
            
    if not isinstance(app, wx.App):
        ## print("- Argument app has unexpected type {!r}".format(typename(app)))
        pass
    elif not app.GetMainLoop():
        app.MainLoop()
    return frame


def watch(target=None, **kwargs):
    """Diver's watch to go deep into the wx process to inspect the target
    Wx.py tool for watching tree structure and events across the wx.Objects
    
  **kwargs : InspectionTool arguments
    pos, size, conifg, locals, and app
    """
    from wx.lib.inspection import InspectionTool
    it = InspectionTool()
    it.Init(**kwargs)
    it.Show(target)
    return it


def filling(target=None, **kwargs):
    """Wx.py tool for watching ingredients of the target
    """
    from wx.py.filling import FillingFrame
    frame = FillingFrame(rootObject=target, rootLabel=typename(target), **kwargs)
    frame.filling.text.WrapMode = 0
    frame.Show()
    return frame



if __name__ == '__main__':
    SHELLSTARTUP = """
if 1:
    self
    self.inspector
    root = self.inspector.shell
    """
    np.set_printoptions(linewidth=256) # default 75
    if 0:
        from scipy import constants
        apropos('', constants, pred='atom')
    
    app = wx.App()
    frm = Frame(None,
        title = repr(Frame),
        ## style = wx.DEFAULT_FRAME_STYLE&~wx.CAPTION,
        ## style = wx.DEFAULT_FRAME_STYLE&~(wx.MINIMIZE_BOX|wx.MAXIMIZE_BOX|wx.RESIZE_BORDER),
        size=(200,80),
    )
    ## To defalut close, use self.Unbind(wx.EVT_CLOSE)
    ## frm.inspector.Unbind(wx.EVT_CLOSE)
    
    frm.SetBackgroundColour(
        '#012456' or wx.Colour(1,36,86)
       #'#f0f0f0' or 'light_grey'
    )
    frm.editor = Editor(frm)
    frm.Show()
    
    frm.handler.debug = 0
    frm.editor.handler.debug = 0
    frm.inspector.handler.debug = 0
    frm.inspector.shell.handler.debug = 0
    frm.inspector.shell.Execute(SHELLSTARTUP)
    frm.inspector.shell.SetFocus()
    frm.inspector.shell.wrap(0)
    frm.inspector.Show()
    
    app.MainLoop()
