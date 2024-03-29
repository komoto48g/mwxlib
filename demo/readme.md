# Demo Script and Gallery


## mwx.FSM

The theory of Finite State Machine (FSM), developed in mid 20th century, is one of the most useful models in system design.
The catalog of techniques that are simplified by FSM is astonishing: text processing, compilers, hardware controls, languages, AI, and much more.
As with most mathematical and physical ideas which are truly fundamental, the concept of FSM is very simple.

The FSM is the most important framework in this library, used for the key/mouse event handlers, inter-object communication, threads, notify, etc.

Check how the mwx.FSM works by running the test code:
[test-script of gate keeper](./test_fsm.py).


## mwx.Frame

The simplest frame, which consists of 
- simple menubar
- simple statusbar
- simple shell


## mwx.Button

- The button is based on <wx.lib.platebtn>
- The panel is based on <wx.lib.scrolledpanel>, and extended to be foldable. (try it!)

[demo_icons](./demo_icons.py)
![screenshot (folded)](./images/demo_buttons(folded).png)
![screenshot (expanded)](./images/demo_buttons(expanded).png)


## mwx.menubar

The mwx.menubar is described as structured list.
Designed as WYSiWYG (see demo).

[demo_menubar](./demo_menubar.py)
![screenshot](./images/demo_menubar.png)


## mwx.controls

The mwx.controls including,
- Knob
    - Param
    - LParam (linear Param)
- Button
- ToggleButton
- TextCtrl (text and button complex)
- Choice (text and combobox complex)

Those wx controls (not only shown above) are laid out by only one method `layout` of mwx.ControlPanel<wx.lib.scrolled.ScrolledPanel> as WYSiWYG (see demo).

[demo_widgets](./demo_widgets.py)
![screenshot](./images/demo_widgets.png)

[demo_gauge](./demo_gauge.py)
![screenshot](./images/demo_gauge.png)

[demo_plot](./demo_plot.py)
![screenshot](./images/demo_plot.png)


## mwx.graphman.Layer

The graphman is a graphic window manager.
- Thread
- Layer (base of Plugins)
- Graph (matplotlib panel)
- Frame
    - two window matplotlib graphic window
    - stack frames
    - layer manager (load/unlodad/edit/inspect)
    - image loader (PIL)
    - index loader
    - session loader

[template](./template.py)
![screenshot](./images/template-layer.png)
