# key bindings

キー割り当て一覧

    global-map : (0 :default)
     ctl-x-map : 'C-x' ... extention map for the frame
      spec-map : 'C-c' ... spefific map for the editors and the shell
       esc-map : 'escape'


## Inspector

Global bindings: (see also `self.inspector.handler@filling`)

    [ 0 ]
                      f1 : 0, About
                      f3 : 0, OnFindNext
                    S-f3 : 0, OnFindPrev
                     f11 : 0, PopupWindow<'Toggle the ghost'>
                   S-f11 : 0, next_editor
                     f12 : 0, close<'Close the window'>
                   C-f12 : 0, clone
                   S-f12 : 0, clear<'Clear all text in the shell (override) and put new prompt'>
                     C-d : 0, duplicate<'Duplicate an expression at the caret-line'>
                     C-f : 0, OnFindText
                     M-c : 0, OnFilterSetStyling
                     M-f : 0, OnFilterSetStyling, OnFilterText
                     M-q : 0, close<'Close the window'>
                  M-left : 0, other_window<'Focus moves to other window'>
                 M-right : 0, other_window<'Focus moves to other window'>
                Xbutton1 : 0, other_editor<'Focus moves to other editor'>
                Xbutton2 : 0, other_editor<'Focus moves to other editor'>
    [ 'C-x' ]
                     C-h : 0, popup<'Show History'>
                       h : 0, popup<'Show Help window'>
                       j : 0, popup<'Show scratch window'>
                       l : 0, popup<'Show Log window'>


## Nautilus

Modes:

     -- : [0] global-map
    TAB : [1] history-comp-mode
    M-. : [2] word-comp-mode
    M-/ : [3] apropos-comp-mode
    M-, : [4] text-comp-mode
    M-m : [5] module-comp-mode

Global bindings: (see also `self.shell.handler@filling`)

    [ 0 ]
                       . : 2, OnEnterDot<'Called when dot(.)'>
                   C-S-f : 0, set_mark
                     C-a : 0, beggining_of_command_line
                     C-c : 'C-c', prefix_command_hook
                     C-e : 0, end_of_command_line
                     C-h : 0, call_autocomp<'Call Autocomp to show a tooltip of args.'>
                     C-j : 0, call_tooltip<'Call ToolTip of the selected word or command line'>
                     C-k : 0, kill_line
                     C-l : 0, <lambda><'recenter'>
                   C-S-l : 0, <lambda><'recenter-bottom'>
                     M-, : 4, call_text_autocomp<'Called when text-comp mode'>
                     M-. : 2, call_word_autocomp<'Called when word-comp mode'>
                     M-/ : 3, call_apropos_autocomp<'Called when apropos mode'>
                   M-S-, : 0, goto<'beginning-of-buffer'>
                   M-S-. : 0, goto<'end-of-buffer'>
                     M-a : 0, back_to_indentation
                     M-e : 0, end_of_line
                     M-h : 0, call_ghost
                     M-j : 0, call_tooltip2<'Call ToolTip of the selected word or repr'>
                     M-m : 5, call_module_autocomp<'Called when module-comp mode'>
                     M-n : 1, call_history_comp<'Called when history-comp mode'>
                     M-p : 1, call_history_comp<'Called when history-comp mode'>
                     M-w : 0, copy_region
                    M-up : 0, goto_previous_mark
                  M-down : 0, goto_next_mark
                  C-M-up : 0, <lambda><'scroll-up'>
                C-M-down : 0, <lambda><'scroll-down'>
                  C-S-up : 0, LineUpExtend<'LineUpExtend()'>
                C-S-down : 0, LineDownExtend<'LineDownExtend()'>
                  C-left : 0, WordLeft<'WordLeft()'>
                 C-right : 0, WordRightEnd<'WordRightEnd()'>
                C-S-left : 0, selection_backward_word_or_paren
               C-S-right : 0, selection_forward_word_or_paren
             C-backspace : 0, skip
             S-backspace : 0, backward_kill_line
                   enter : 0, OnEnter<'Called when enter'>
                 C-enter : 0, wx.py.shell:insertLineBreak<'Insert a new line break.'>
                 S-enter : 0, OnEnter<'Called when enter'>
                  escape : -1, OnEscape<'Called when escape'>
                      f9 : 0, <lambda><'toggle-fold-type'>
                  insert : 0, <lambda><'toggle-over'>
                   space : 0, OnSpace<'Called when space'>
                 C-space : 0, set_mark
                 S-space : 0, skip
                     tab : 1, call_history_comp<'Called when history-comp mode'>
                   C-tab : 0, insert_space_like_tab<'タブの気持ちになって半角スペースを前向きに入力する'>
                 C-S-tab : 0, delete_backward_space_like_tab<'シフト+タブの気持ちになって半角スペースを後ろ向きに消す'>
    [ 'C-c' ]
                     C-c : 0, goto_matched_paren<'goto matched paren'>
                       j : 0, evaln

