#! python3
# -*- coding: utf-8 -*-
"""mwxlib core

Author: Kazuya O'moto <komoto@jeol.co.jp>
"""
from collections import OrderedDict
from functools import wraps
from bdb import BdbQuit
import traceback
import warnings
import shlex
import time
import sys
import os
import re
import fnmatch
import pkgutil
import pydoc
import inspect
from inspect import (isclass, ismodule, ismethod, isbuiltin,
                     isfunction, isgenerator, isframe, iscode, istraceback)
from pprint import pprint


def atom(v):
    return not hasattr(v, '__name__')


def isobject(v):
    ## return atom(v) and hasattr(v, '__module__')
    return re.match(r"<([\w.]+) object at \w+>", repr(v))


def instance(*types):
    ## return lambda v: isinstance(v, types)
    def _pred(v):
        return isinstance(v, types)
    _pred.__name__ = str("instance<{}>".format(','.join(p.__name__ for p in types)))
    return _pred


def subclass(*types):
    ## return lambda v: issubclass(v, types)
    def _pred(v):
        return issubclass(v, types)
    _pred.__name__ = str("subclass<{}>".format(','.join(p.__name__ for p in types)))
    return _pred


def _Not(p):
    ## return lambda v: not p(v)
    if isinstance(p, type):
        p = instance(p)
    def _pred(v):
        return not p(v)
    _pred.__name__ = str("not {}".format(p.__name__))
    return _pred


def _And(p, q):
    ## return lambda v: p(v) and q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    def _pred(v):
        return p(v) and q(v)
    _pred.__name__ = str("{} and {}".format(p.__name__, q.__name__))
    return _pred


def _Or(p, q):
    ## return lambda v: p(v) or q(v)
    if isinstance(p, type):
        p = instance(p)
    if isinstance(q, type):
        q = instance(q)
    def _pred(v):
        return p(v) or q(v)
    _pred.__name__ = str("{} or {}".format(p.__name__, q.__name__))
    return _pred


def predicate(text, locals):
    tokens = [x for x in split_words(text.strip()) if not x.isspace()]
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'not' or c == '~':
            tokens[j:j+2] = ["_Not({})".format(tokens[j+1])]
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'and' or c == '&':
            tokens[j-1:j+2] = ["_And({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    j = 0
    while j < len(tokens):
        c = tokens[j]
        if c == 'or' or c == '|':
            tokens[j-1:j+2] = ["_Or({},{})".format(tokens[j-1], tokens[j+1])]
            continue
        j += 1
    return eval(' '.join(tokens) or 'None', None, locals)


def apropos(obj, rexpr='', ignorecase=True, alias=None, pred=None, locals=None):
    """Prints a list of objects having expression rexpr in obj.
    """
    name = alias or typename(obj)
    
    rexpr = (rexpr.replace('\\a','[a-z0-9]')  #\a: identifier chars (custom rule)
                  .replace('\\A','[A-Z0-9]')) #\A: 
    
    if isinstance(pred, str):
        pred = predicate(pred, locals)
    
    if isinstance(pred, type):
        pred = instance(pred)
    
    if pred is not None:
        if not callable(pred):
            raise TypeError("{!r} is not callable".format(pred))
        try:
            pred(None)
        except (TypeError, ValueError):
            pass
    
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        
        print("matching to {!r} in {} {} :{}".format(
              rexpr, name, type(obj), pred and pred.__name__))
        try:
            p = re.compile(rexpr, re.I if ignorecase else 0)
        except re.error as e:
            print("- re:miss compilation {!r} : {!r}".format(e, rexpr))
        else:
            keys = sorted(filter(p.search, dir(obj)), key=lambda s:s.upper())
            n = 0
            for key in keys:
                try:
                    value = getattr(obj, key)
                    if pred and not pred(value):
                        continue
                    word = repr(value)
                    word = ' '.join(s.strip() for s in word.splitlines())
                    n += 1
                except (TypeError, ValueError):
                    continue
                except Exception as e:
                    word = '#<{!r}>'.format(e)
                if len(word) > 80:
                    word = word[:80] + '...' # truncate words +3 ellipsis
                print("    {}.{:<36s} {}".format(name, key, word))
            if pred:
                print("found {} of {} words with :{}".format(n, len(keys), pred.__name__))
            else:
                print("found {} words.".format(len(keys)))


def typename(obj, docp=False, qualp=True):
    """Formatted object type name.
    """
    if hasattr(obj, '__name__'): # module, class, method, function, etc.
        if qualp:
            name = getattr(obj, '__qualname__', obj.__name__)
        else:
            name = obj.__name__
    elif hasattr(obj, '__module__'): # atom -> module.class
        name = obj.__class__.__name__
    else:
        return pydoc.describe(obj) # atom -> short description
    
    modname = getattr(obj, '__module__', None)
    if modname and modname != "__main__" and not modname.startswith('mwx'):
        name = modname + '.' + name
    
    if docp and callable(obj) and obj.__doc__:
        name += "<{!r}>".format(obj.__doc__.splitlines()[0]) # concat the first doc line
    return name


def where(obj):
    """Show @where (filename, lineno) the obj is defined
    """
    if inspect.isframe(obj):
        filename = obj.f_code.co_filename
        lineno = obj.f_lineno
        name = obj.f_code.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    if inspect.iscode(obj):
        filename = obj.co_filename
        lineno = obj.co_firstlineno
        name = obj.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    if inspect.istraceback(obj):
        filename = obj.tb_frame.f_code.co_filename
        lineno = obj.tb_lineno
        name = obj.tb_frame.f_code.co_name
        return "{}:{}:{}".format(filename, lineno, name)
    
    ## if inspect.isbuiltin(obj):
    ##     return None
    
    def _where(obj):
        obj = inspect.unwrap(obj)
        filename = inspect.getsourcefile(obj)
        src, lineno = inspect.getsourcelines(obj)
        name = src[0].rstrip()
        if not lineno:
            return filename
        return "{}:{}:{}".format(filename, lineno, name)
    
    try:
        try:
            return _where(obj) # module, class, method, function, frame, or code
        except TypeError:
            return _where(obj.__class__) # otherwise, class of the object
    except Exception:
        pass
    ## The source code cannot be retrieved.
    ## Try to get filename where the object is defined.
    try:
        try:
            return inspect.getfile(obj) # compiled file?
        except TypeError:
            return inspect.getfile(obj.__class__) # or a special class?
    except Exception:
        pass
    
    if hasattr(obj, '__module__'):
        return obj.__module__
    return None


def mro(obj):
    """Show @mro (method resolution order) of obj.
    
    Prints a list of filenames and lineno, or the module-names.
    """
    if not isinstance(obj, type):
        obj = type(obj)
    for base in obj.__mro__:
        f = where(base)
        print("  {:40s} {}".format(str(base),
                        getattr(f, '__file__', None) or
                        getattr(f, '__name__', None) or f))


def pp(obj):
    pprint(obj, **pp.__dict__)

if pp:
    pp.indent = 1
    pp.width = 80 # default 80
    pp.depth = None
    if sys.version_info >= (3,6):
        pp.compact = False
    if sys.version_info >= (3,8):
        pp.sort_dicts = True


def split_words(text, reverse=False):
    tokens = _split_tokens(text)
    if reverse:
        tokens = tokens[::-1]
    while tokens:
        words = _extract_words_from_tokens(tokens, reverse)
        if not words:
            words = tokens.pop(0)
        yield words


def _split_tokens(text):
    lexer = shlex.shlex(text)
    lexer.wordchars += '.'
    lexer.whitespace = '' # nothing is white (for multiline analysis)
    lexer.commenters = '' # don't ignore comment lines
    ls = []
    n = 0
    p = re.compile(r"([a-zA-Z])[\"\']") # check [bfru]-string
    try:
        for token in lexer:
            m = p.match(token)
            if m:
                ls.append(m.group(1))
                return ls + _split_tokens(text[n+1:])
            ls.append(token)
            n += len(token)
    except ValueError:
        pass
    return ls


def _extract_words_from_tokens(tokens, reverse=False):
    """Extract pythonic expressions from tokens.
    default sep includes `@, binary-ops, and whitespaces, etc.
    """
    sep = "`@=+-/*%<>&|^~!?,:; \t\r\n#"
    p, q = "({[", ")}]"
    if reverse:
        p, q = q, p
    stack = []
    words = []
    for j, c in enumerate(tokens):
        if c in p:
            stack.append(c)
        elif c in q:
            if not stack: # error("open-paren", c)
                break
            if c != q[p.index(stack.pop())]: # error("mismatch-paren", c)
                break
        elif not stack and c in sep: # ok
            break
        words.append(c)
    else:
        j = None
        if stack: # error("unclosed-paren", ''.join(stack))
            pass
    del tokens[:j] # remove extracted tokens
    return ''.join(reversed(words) if reverse else words)


def find_modules(force=False, verbose=True):
    """Find all modules available and write to log file.
    
    Similar to pydoc.help, it scans packages, but also submodules.
    This creates a log file in ~/.mwxlib and save the list.
    """
    f = get_rootpath("deb-modules-{}.log".format(sys.winver))
    
    def _callback(path, modname, desc=''):
        if verbose:
            print("Scanning {:70s}".format(modname[:70]), end='\r',
                  file=sys.__stdout__)
        lm.append(modname)
    
    def _error(modname):
        if verbose:
            print("- failed: {}".format(modname),
                  file=sys.__stderr__)
    
    if not force and os.path.exists(f):
        with open(f, 'r') as o:
            lm = eval(o.read()) # read and evaluate module list
        
        ## Check additional packages/modules
        verbose = False
        for root in pkgutil.iter_modules():
            if root.name not in lm:
                _callback(None, root.name)
                if root.ispkg:
                    try:
                        #<FileFinder object>
                        path = [os.path.join(root.module_finder.path, root.name)]
                    except AttributeError:
                        #<zipimporter object> e.g. egg
                        path = [os.path.join(root.module_finder.archive, root.name)]
                    for info in pkgutil.walk_packages(path, root.name+'.', onerror=_error):
                        _callback(None, info.name)
    else:
        print("Please wait a moment "
              "while Py{} gathers a list of all available modules... "
              "(This is executed once)".format(sys.winver))
        
        lm = list(sys.builtin_module_names)
        
        ## pydoc.ModuleScanner().run(_callback, key='', onerror=_error)
        for info in pkgutil.walk_packages(onerror=_error):
            _callback(None, info.name)
        
        lm.sort(key=str.upper)
        with open(f, 'w') as o:
            pprint(lm, stream=o) # write module list
        print("The results were written in {!r}.".format(f))
    return lm


def get_rootpath(f):
    """Return pathname ~/.mwxlib/f.
    If ~/.mwxlib/ does not exist, it will be created.
    """
    home = os.path.normpath(os.path.expanduser("~/.mwxlib"))
    if not os.path.exists(home):
        os.mkdir(home)
    return os.path.join(home, f)


## --------------------------------
## Finite State Machine
## --------------------------------

class SSM(OrderedDict):
    """Single State Machine/Context of FSM
    """
    def __call__(self, event, *args, **kwargs):
        for act in self[event]:
            act(*args, **kwargs)
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(self.__class__.__name__, id(self))
    
    def __str__(self):
        def lstr(v):
            def _name(a):
                if callable(a):
                    return typename(a, docp=1, qualp=0)
                return repr(a)
            return ', '.join(_name(a) for a in v)
        return '\n'.join("{:>32} : {}".format(str(k), lstr(v)) for k, v in self.items())
    
    def bind(self, event, action=None):
        """Append a transaction to the context."""
        transaction = self[event]
        if action is None:
            return lambda f: self.bind(event, f)
        if not callable(action):
            raise TypeError("{!r} is not callable".format(action))
        if action not in transaction:
            transaction.append(action)
        return action
    
    def unbind(self, event, action=None):
        """Remove a transaction from the context."""
        transaction = self[event]
        if action is None:
            del self[event]
            return True
        if not callable(action):
            raise TypeError("{!r} is not callable".format(action))
        if action in transaction:
            transaction.remove(action)
            return True
        return False


class FSM(dict):
    """Finite State Machine
    
    Args:
        contexts: map of context <DNA>
            {state: {event: transaction (next_state, actions ...)}}
            
            * The state `None` is a wildcard (as executed any time).
            * An event (str) can include wildcards ``*?[]`` (fnmatch rule).
            * Actions must accept the same args as __call__.
    
    If no action, FSM carries out only a transition.
    The transition is always done before actions.
    
    To debug FSM handler, set ``debug`` switch as follows::
    
        [0] no trace, warnings only
        [1] trace when state transits
        [2] + when different event comes
        [3] + trace all events and actions
        [4] ++ all events (+ including state:None)
        [5] ++ all events (even if no actions + state:None)
        [8] +++ (max verbose level) to put all args and kwargs.
    
    Note:
        A default=None is given as an argument of the init.
        If there is only one state, that state will be the default.
    
    Note:
        There is no enter/exit event handler.
    """
    debug = 0
    debugger = None
    
    default_state = None
    current_state = property(lambda self: self.__state)
    previous_state = property(lambda self: self.__prev_state)
    
    event = property(lambda self: self.__event)
    current_event = property(lambda self: self.__event)
    previous_event = property(lambda self: self.__prev_event)
    
    @current_state.setter
    def current_state(self, state):
        self.__state = state
        self.__event = '*forced*'
        self.__debcall__(self.__event)
    
    def clear(self, state):
        """Reset current and previous states."""
        self.__state = state
        self.__prev_state = state
        self.__event = None
        self.__prev_event = None
        self.__matched_pattern = None
    
    def __init__(self, contexts=None, default=None):
        dict.__init__(self) # update dict, however, it does not clear
        dict.clear(self)    # if and when __init__ is called, all contents are cleared
        if contexts is None:
            contexts = {}
        if default is None: # if no default given, reset the first state as the default
            if self.default_state is None:
                default = next((k for k in contexts if k is not None), None)
        self.default_state = default
        self.clear(default) # the first clear creates object localvars
        self.update(contexts)
    
    def __missing__(self, key):
        raise Exception("FSM:logic-error: undefined state {!r}".format(key))
    
    def __repr__(self):
        return "<{} object at 0x{:X}>".format(self.__class__.__name__, id(self))
    
    def __str__(self):
        return '\n'.join("[ {!r} ]\n{!s}".format(k, v) for k, v in self.items())
    
    def __call__(self, event, *args, **kwargs):
        """Handle the event.
        First, call handlers with the state:None.
        Then, call handlers with the current state.
        
        Returns:
            list or None depending on the handler
            
            - process the event (with actions) -> [retvals]
            - process the event (no actions) -> []
            - no event:transaction -> None
        """
        recept = False # Is transaction performed?
        retvals = [] # retvals of actions
        if None in self:
            org = self.__state
            prev = self.__prev_state
            try:
                self.__event = event
                self.__state = None
                ret = self.call(event, *args, **kwargs) # None process
                if ret is not None:
                    recept = True
                    retvals += ret
            finally:
                if self.__state is None: # restore original
                    self.__state = org
                    self.__prev_state = prev
        
        self.__event = event
        if self.__state is not None:
            ret = self.call(event, *args, **kwargs) # normal process
            if ret is not None:
                recept = True
                retvals += ret
        
        self.__prev_state = self.__state
        self.__prev_event = event
        if recept:
            return retvals
    
    def call(self, event, *args, **kwargs):
        """Invoke the event handlers.
        
        1. transit the state
        2. try actions after transition
        
        Returns:
            list or None depending on the handler
            
            - process the event (with actions) -> [retvals]
            - process the event (no actions) -> []
            - no event:transaction -> None
        """
        context = self[self.__state]
        if event in context:
            transaction = context[event]
            self.__prev_state = self.__state # save previous state
            self.__state = transaction[0]    # the state transits here
            self.__debcall__(event, *args, **kwargs) # check after transition
            retvals = []
            for act in transaction[1:]:
                ## Save the event before each action (for nested call).
                if self.__matched_pattern is None:
                    self.__event = event
                try:
                    ret = act(*args, **kwargs) # call actions after transition
                    retvals.append(ret)
                except BdbQuit:
                    pass
                except Exception as e:
                    self.dump("- FSM:exception: {!r}".format(e),
                              "   event : {}".format(event),
                              "    from : {}".format(self.__prev_state),
                              "      to : {}".format(self.__state),
                              "  action : {}".format(typename(act)),
                              "    args : {}".format(args),
                              "  kwargs : {}".format(kwargs))
                    traceback.print_exc()
                    if self.debugger:
                        self.debugger(act, *args, **kwargs)
                        self.clear(self.default_state)
                        break
            self.__matched_pattern = None
            return retvals
        elif isinstance(event, str): # matching test using fnmatch
            for pat in context:
                if fnmatch.fnmatchcase(event, pat):
                    self.__matched_pattern = pat
                    return self.call(pat, *args, **kwargs) # recursive call
        
        self.__debcall__(event, *args, **kwargs) # check when no transition
        return None # no event, no action
    
    def __debcall__(self, pattern, *args, **kwargs):
        v = self.debug
        if v and self.__state is not None:
            transaction = self[self.__prev_state].get(pattern) or []
            actions = ', '.join(typename(a, qualp=0) for a in transaction[1:])
            if (v > 0 and self.__prev_state != self.__state
             or v > 1 and self.__prev_event != self.__event
             or v > 2 and actions
             or v > 3):
                self.log("{c} {1} --> {2} {0!r} {a}".format(
                    self.__event, self.__prev_state, self.__state,
                    a = '' if not actions else ('=> ' + actions),
                    c = '*' if self.__prev_state != self.__state else ' '))
        
        elif v > 3: # state is None
            transaction = self[None].get(pattern) or []
            actions = ', '.join(typename(a, qualp=0) for a in transaction[1:])
            if actions or v > 4:
                self.log("  -- None {0!r} {a}".format(
                    self.__event,
                    a = '' if not actions else ('=> ' + actions)))
        
        if v > 7: # max verbose level puts all args
            self.log("\t:", args)
            self.log("\t:", kwargs)
    
    @staticmethod
    def log(*args):
        print(*args, file=sys.__stdout__)
    
    @staticmethod
    def dump(*args):
        print(*args, sep='\n', file=sys.__stderr__)
        f = get_rootpath("deb-dump.log")
        with open(f, 'a') as o:
            print(time.strftime('!!! %Y/%m/%d %H:%M:%S'), file=o)
            print(*args, sep='\n', end='\n', file=o)
            print(traceback.format_exc(), file=o)
    
    @staticmethod
    def duplicate(context):
        """Duplicate the transaction:list in the context.
        
        This method is used for the contexts given to :append and :update
        so that the original transaction (if they are lists) is not removed.
        """
        return {event:transaction[:] for event, transaction in context.items()}
    
    def validate(self, state):
        """Sort and move to end items with key which includes ``*?[]``."""
        context = self[state]
        ast = []
        bra = []
        for event in list(context): #? OrderedDict mutated during iteration
            if re.search(r"\[.+\]", event):
                bra.append((event, context.pop(event))) # event key has '[]'
            elif '*' in event or '?' in event:
                ast.append((event, context.pop(event))) # event key has '*?'
        
        temp = sorted(context.items()) # normal event key
        context.clear()
        context.update(temp)
        context.update(sorted(bra, reverse=1))
        context.update(sorted(ast, reverse=1, key=lambda v:len(v[0])))
    
    def update(self, contexts):
        """Update each context or Add new contexts."""
        for k, v in contexts.items():
            if k in self:
                self[k].update(self.duplicate(v))
            else:
                self[k] = SSM(self.duplicate(v)) # new context
            self.validate(k)
    
    def append(self, contexts):
        """Append new contexts."""
        for k, v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    if event not in self[k]:
                        self[k][event] = transaction[:] # copy the event:transaction
                        continue
                    for act in transaction[1:]:
                        self.bind(event, act, k, transaction[0])
            else:
                self[k] = SSM(self.duplicate(v)) # new context
            self.validate(k)
    
    def remove(self, contexts):
        """Remove old contexts."""
        for k, v in contexts.items():
            if k in self:
                for event, transaction in v.items():
                    if self[k].get(event) == transaction:
                        self[k].pop(event) # remove the event:transaction
                        continue
                    for act in transaction[1:]:
                        self.unbind(event, act, k)
        ## cleanup
        for k, v in list(self.items()): # self mutates during iteration
            if not v:
                del self[k]
    
    def define(self, event, action=None, state=None, state2=None):
        self.unbind(event, None, state)
        return self.bind(event, action, state, state2)
    
    def bind(self, event, action=None, state=None, state2=None):
        """Append a transaction to the context.
        
        equiv. self[state] += {event : [state2, action]}
        
        The transaction is exepcted to be a list (not a tuple).
        If no action, it creates only the transition and returns @decor(binder).
        """
        assert isinstance(event, str)
        warn = self.log
        
        if state not in self:
            warn("- FSM:warning: [{!r}] context newly created.".format(state))
            self[state] = SSM() # new context
        
        context = self[state]
        if state2 is None:
            state2 = state
        
        if event in context:
            if state2 != context[event][0]:
                warn("- FSM:warning: transaction may conflict.\n"
                     "  The state {2!r} and the original state is not the same."
                     "  {0!r} : {1!r} --> {2!r}".format(event, state, state2))
                pass
                context[event][0] = state2 # update transition
        else:
            ## if state2 not in self:
            ##     warn("- FSM:warning: transaction may contradict\n"
            ##          "  The state {2!r} is not found in the contexts."
            ##          "  {0!r} : {1!r} --> {2!r}".format(event, state, state2))
            ##     pass
            context[event] = [state2] # new event:transaction
        
        transaction = context[event]
        if action is None:
            return lambda f: self.bind(event, f, state, state2)
        
        assert callable(action), "{!r} is not callable".format(action)
        if action not in transaction:
            try:
                transaction.append(action)
            except AttributeError:
                warn("- FSM:warning: appending action to context ({!r} : {!r})\n"
                     "  The transaction must be a list, not a tuple".format(state, event))
        return action
    
    def unbind(self, event, action=None, state=None):
        """Remove a transaction from the context.
        
        equiv. self[state] -= {event : [?, action]}
        
        The transaction is exepcted to be a list (not a tuple).
        If no action, it will remove the transaction from the context.
        """
        warn = self.log
        
        if state not in self:
            warn("- FSM:warning: [{!r}] context does not exist.".format(state))
            return
        
        context = self[state]
        if event not in context:
            warn("- FSM:warning: No such transaction ({!r} : {!r})".format(state, event))
            return
        
        transaction = context[event]
        if action is None:
            for act in transaction[1:]:
                self.unbind(event, act, state)
            return True
        
        assert callable(action), "{!r} is not callable".format(action)
        if action in transaction:
            try:
                transaction.remove(action)
                return True
            except AttributeError:
                warn("- FSM:warning: removing action from context ({!r} : {!r})\n"
                     "  The transaction must be a list, not a tuple".format(state, event))
        return False


class TreeList(object):
    """Tree access wrapper of list<item : (key, value)>
    [
        [key, [item,
               item, ...]],
        [key, [item,
               [branch], => [key, [item,
                                   item, ...]],
               ...]],
    ]
    """
    ## A dummy list to avoid RecursionError occurs when
    ## __getattr__ may be called before __init__.
    __items = None
    
    def __init__(self, ls=None):
        self.__items = ls or []
    
    def __call__(self, k):
        return TreeList(self[k])
    
    def __getattr__(self, attr):
        return getattr(self.__items, attr)
    
    def __contains__(self, k):
        return self.getf(self.__items, k)
    
    def __iter__(self):
        return self.__items.__iter__()
    
    def __getitem__(self, k):
        if isinstance(k, str):
            return self.getf(self.__items, k)
        return self.__items.__getitem__(k)
    
    def __setitem__(self, k, v):
        if isinstance(k, str):
            return self.setf(self.__items, k, v)
        return self.__items.__setitem__(k, v)
    
    def __delitem__(self, k):
        if isinstance(k, str):
            return self.delf(self.__items, k)
        return self.__items.__delitem__(k)
    
    def items(self):
        def _items(ls, key=None):
            for item in ls:
                try:
                    k, v = item
                    rootkey = f"{key}/{k}" if key else k
                except Exception:
                    yield key, item
                else:
                    if v and isinstance(v, (list, tuple)):
                        yield from _items(v, rootkey)
                    else:
                        yield rootkey, v
        yield from _items(self)
    
    def _find_item(self, ls, key):
        for x in ls:
            if isinstance(x, (tuple, list)) and x and x[0] == key:
                if len(x) < 2:
                    raise ValueError("No value for key={!r}".format(key))
                return x
    
    def getf(self, ls, key):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.getf(la, b)
            return None
        li = self._find_item(ls, key)
        if li is not None:
            return li[-1]
    
    def setf(self, ls, key, value):
        if '/' in key:
            a, b = key.split('/', 1)
            la = self.getf(ls, a)
            if la is not None:
                return self.setf(la, b, value)
            p, key = key.rsplit('/', 1)
            return self.setf(ls, p, [[key, value]]) # >>> ls[p].append([key, value])
        try:
            li = self._find_item(ls, key)
            if li is not None:
                try:
                    li[-1] = value # assign value to item (ls must be a list)
                except TypeError:
                    li[-1][:] = value # assign value to items:list
            else:
                ls.append([key, value]) # append to items:list
        except (ValueError, TypeError, AttributeError) as e:
            print("- TreeList:warning {!r}: key={!r}".format(e, key))
    
    def delf(self, ls, key):
        if '/' in key:
            p, key = key.rsplit('/', 1)
            ls = self.getf(ls, p)
        ls.remove(next(x for x in ls if x and x[0] == key))


def funcall(f, *args, doc=None, alias=None, **kwargs):
    """Decorator of event handler
    
    Check if the event argument can be omitted
    and required arguments are given by args and kwargs.
    
    Returns:
        lambda: Decorated function f as `alias<doc>`
        
        >>> Act1 = lambda *v,**kw: f(*(v+args), **(kwargs|kw))
        >>> Act2 = lambda *v,**kw: f(*args, **(kwargs|kw))
        
        Act1 that accepts event arguments if there are any 
        remaining arguments that must be explicitly specified in f.
        Otherwise, Act2 that ignores event arguments.
    """
    assert callable(f)
    assert isinstance(doc, (str, type(None)))
    assert isinstance(alias, (str, type(None)))
    
    @wraps(f)
    def _Act(*v, **kw):
        kwargs.update(kw)
        return f(*(v + args), **kwargs) # function with event args
    
    @wraps(f)
    def _Act2(*v, **kw):
        kwargs.update(kw)
        return f(*args, **kwargs) # function with no explicit args
    
    action = _Act
    
    def _explicit_args(argv, defaults):
        """The rest of argv that must be given explicitly in f."""
        N = len(argv)
        j = len(defaults)
        i = len(args)
        return set(argv[i:N-j]) - set(kwargs)
    
    if not inspect.isbuiltin(f):
        sig = inspect.signature(f)
        argv = []
        defaults = []
        varargs = None
        varkwargs = None
        for k, v in sig.parameters.items():
            if v.kind <= 1: # POSITIONAL_ONLY, POSITIONAL_OR_KEYWORD
                argv.append(k)
                if v.default != v.empty:
                    defaults.append(v.default)
            elif v.kind == 2: # VAR_POSITIONAL (*args)
                varargs = k
            elif v.kind == 4: # VAR_KEYWORD (**kwargs)
                varkwargs = k
        if varargs:
            action = _Act
        elif not _explicit_args(argv, defaults):
            action = _Act2
    else:
        ## Builtin functions don't have an argspec that we can get.
        ## Try alalyzing the doc:str to get argspec info.
        ## 
        ## Wx buitl-in method doc is written in the following style:
        ## ```name(argspec) -> retval
        ## 
        ## ...(details)...
        ## ```
        docs = [ln for ln in inspect.getdoc(f).splitlines() if ln]
        m = re.search(r"(\w+)\((.*)\)", docs[0])
        if m:
            name, argspec = m.groups()
            argv = [x for x in argspec.strip().split(',') if x]
            defaults = re.findall(r"\w+\s*=(\w+)", argspec)
            if not _explicit_args(argv, defaults):
                action = _Act2
                if len(docs) > 1:
                    action.__doc__ = '\n'.join(docs[1:])
    
    if alias:
        action.__name__ = str(alias)
    if doc:
        action.__doc__ = doc
    return action
