"""Modified GTK3+ widgets for inclusion in the glade catalog."""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation

import logging

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, Pango
import numpy as np
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg
from matplotlib.backends.backend_gtk3 import NavigationToolbar2GTK3
from matplotlib.figure import Figure

from gxps import (
    COLORS, CONFIG,
    __appname__, __version__, __authors__, __website__
    )
from gxps.state import State
from gxps.canvas_tools import (
    PeakSelector, SpanSelector, PointSelector,
    DraggableVLine
    )


LOG = logging.getLogger(__name__)



class GXPSAppWindow(Gtk.ApplicationWindow):
    """Main window of GXPS.
    """
    __gtype_name__ = "GXPSAppWindow"
    def __init__(self):
        LOG.info("Instantiating window")
        super().__init__()

    def startup(self, app):
        """Position the window correctly."""
        self.set_application(app)
        xpos, ypos = CONFIG["Window"]["xpos"], CONFIG["Window"]["ypos"]
        xsize, ysize = CONFIG["Window"]["xsize"], CONFIG["Window"]["ysize"]
        if xpos and ypos:
            self.move(int(xpos), int(ypos))
        if xsize and ysize:
            self.set_default_size(int(xsize), int(ysize))
        self.set_wmclass(__appname__, __appname__)
        super().show_all()


class GXPSCanvas(FigureCanvasGTK3Agg):
    """Canvas for drawing the spectra.
    """
    # pylint: disable=invalid-name
    __gtype_name__ = "GXPSCanvas"
    def __init__(self):
        figure = Figure()
        super().__init__(figure)
        self.ax = self.figure.add_axes([-0.005, 0.05, 1.01, 1.005])
        self.ax.set_facecolor(COLORS["Canvas"]["canvas-facecolor"])
        self.figure.patch.set_facecolor(COLORS["Canvas"]["canvas-facecolor"])
        self._xy_buffer = [0, 1, 0, 1]
        self._xy_center = [np.inf, -np.inf, np.inf, -np.inf]
        self._set_ticks()

    def store_xylims(self):
        """Stores axis limits in self._xy_buffer.
        """
        xmin, xmax = min(self.ax.get_xlim()), max(self.ax.get_xlim())
        ymin, ymax = min(self.ax.get_ylim()), max(self.ax.get_ylim())
        self._xy_buffer = [xmin, xmax, ymin, ymax]

    def restore_xylims(self):
        """Sets the axis limits to the ones stored in self._xy_buffer.
        """
        if not np.all(np.isfinite(self._xy_buffer)):
            self._xy_buffer = [0, 1, 0, 1]
        xmin, xmax, ymin, ymax = self._xy_buffer
        self.ax.set_xlim(xmax, xmin)
        self.ax.set_ylim(ymin, ymax)
        self._set_ticks()

    def center_view(self):
        """Focuses view on current plot. by setting self._xy_buffer to a
        frame around self._xy_center and then applying those values.
        """
        if np.all(np.isfinite(self._xy_center)):
            xspan = self._xy_center[1] - self._xy_center[0]
            bordered_center = [
                self._xy_center[0] - xspan * 0.02,
                self._xy_center[1] + xspan * 0.02,
                0,
                self._xy_center[3] * 1.1
            ]
            self._xy_buffer = bordered_center
        else:
            self._xy_buffer = [0, 1, 0, 1]
        self.restore_xylims()

    def reset_xy_centerlims(self):
        """Sets self._xy to infinite values again, so it can be incrementally
        updated by update_xy.
        """
        self._xy_center = [np.inf, -np.inf, np.inf, -np.inf]

    def update_xy_centerlims(self, xmin, xmax, ymin, ymax):
        """Updates self._xy where min values are only assumed when they
        are lower than the current min. Analogous for max values.
        """
        self._xy_center = [
            min(self._xy_center[0], xmin),
            max(self._xy_center[1], xmax),
            min(self._xy_center[2], ymin),
            max(self._xy_center[3], ymax)
        ]

    def _set_ticks(self):
        """Configures axes ticks.
        """
        self.ax.spines["bottom"].set_visible(False)
        self.ax.tick_params(
            reset=True,
            axis="both",
            direction="out",
            # pad=-20,
            labelsize="large",
            labelcolor=COLORS["Plotting"]["axisticks"],
            color=COLORS["Plotting"]["axisticks"],
            labelleft=False,
            top=False,
            left=False,
            right=False,
            bottom=False
        )
        if self._xy_center[0] == np.inf:
            self.ax.tick_params(
                which="both",
                bottom=False,
                top=False,
                left=False,
                right=False,
                labelbottom=False
            )


class DraggableVLineContainer(Gtk.DrawingArea):
    """Contains all active and usable draggable vlines. Provides methods
    for adding new ones and connecting them to the bus.
    This object is invisibly added in the same Gtk.Box where the canvas
    is."""
    __gtype_name__ = "GXPSCanvasObjects"

    def __init__(self):
        self.bus = None
        self._lines = []

    def set_bus(self, bus):
        """Set the bus."""
        self.bus = bus

    def add_line(self, line, spectrum):
        """Add a new line and attach the bus to it."""
        if not self.bus:
            raise RuntimeError("DraggableVLineContainer has not bus")
        dline = DraggableVLine(line, spectrum)
        self._lines.append(dline)
        dline.register_queue(self.bus)

    def clear(self):
        """Remove all lines."""
        self._lines.clear()


class GXPSEditSpectrumDialog(Gtk.Dialog):
    """Dialog for editing metadata.
    """
    __gtype_name__ = "GXPSEditSpectrumDialog"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._getters = {}
        # A key that indicates fields which are not read for new values.
        self.exclusion_key = ""

    def flush(self):
        """Removes all children except last, which is the action area."""
        for child in self.get_content_area().get_children()[:-1]:
            self.get_content_area().remove(child)

    def get_values(self):
        """Returns a dictionary containing the new values."""
        values = {}
        for attr, getter in self._getters.items():
            value = getter()
            if self.exclusion_key not in value:
                values[attr] = value
        return values

    def apply(self, *_args):
        """Sends APPLY response."""
        self.emit("response", Gtk.ResponseType.APPLY)

    def add_editor_row(self, attr, labeltext, entrytext):
        """Builds a row for editing an attribute. Returns a method for
        getting the new value.
        """
        box = Gtk.Box(margin_top=5, margin_bottom=5)
        label = Gtk.Label(
            label=labeltext,
            width_chars=25,
            max_width_chars=25,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD,
            justify=Gtk.Justification.CENTER
        )
        entry = Gtk.Entry(text=entrytext, margin_left=10, margin_right=10)
        box.pack_start(label, False, False, 0)
        box.pack_start(entry, True, True, 0)
        box.show_all()
        self.get_content_area().pack_start(box, False, False, 0)
        entry.connect("activate", self.apply)
        self._getters[attr] = entry.get_text

    def add_non_editable_row(self, labeltext, valuetext):
        """Adds a row for attributes associated with the files in editing.
        Gtk.Labels instead of Gtk.Entrys because this cant be changed.
        """
        box = Gtk.Box(margin_top=10, margin_bottom=5)
        label = Gtk.Label(
            label=labeltext,
            width_chars=25,
            max_width_chars=25,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD,
            justify=Gtk.Justification.CENTER
        )
        label2 = Gtk.Label(
            label=valuetext,
            margin_left=10,
            margin_right=10,
            max_width_chars=80,
            wrap=True,
            wrap_mode=Pango.WrapMode.CHAR,
            ellipsize=Pango.EllipsizeMode.START
        )
        box.pack_start(label, False, False, 0)
        box.pack_start(label2, True, True, 0)
        box.show_all()
        self.get_content_area().pack_start(box, False, False, 0)


class GXPSSaveConfirmationDialog(Gtk.Dialog):
    """Dialog that asks if you really want to quit without saving."""
    __gtype_name__ = "GXPSSaveConfirmationDialog"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.accels = Gtk.AccelGroup()
        self.add_accel_group(self.accels)

    def set_accels(self):
        """Sets the accelerators for the buttons."""
        accels = {
            "<Control>s": Gtk.ResponseType.YES,
            "<Control>d": Gtk.ResponseType.NO,
            "<Control>c": Gtk.ResponseType.CANCEL
        }
        for accel, response in accels.items():
            key, mod = Gtk.accelerator_parse(accel)
            button = self.get_widget_for_response(response)
            button.add_accelerator(
                "activate",
                self.accels,
                key,
                mod,
                Gtk.AccelFlags.VISIBLE
            )


class GXPSAboutDialog(Gtk.AboutDialog):
    """Pre-filled about dialog. Uses info from __init__.py variables.
    """
    __gtype_name__ = "GXPSAboutDialog"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_program_name(__appname__)
        self.set_version("Version: {}".format(__version__))
        self.set_authors(__authors__)
        self.set_website(__website__)
        self.set_license_type(Gtk.License.GPL_3_0)
        commentstring = (
            "If you encounter any bugs, mail me or open an "
            "issue on github. Please include a logfile "
            "(access via Help -> View logfile)."
        )
        self.set_comments(commentstring)


class FileFilter(Gtk.FileFilter):
    """Very simple FileFilter for FileChooserDialogs."""
    def __init__(self, name, patterns):
        super().__init__()
        for pattern in patterns:
            self.add_pattern(pattern)
        self.set_name(name)


class GXPSImportDialog(Gtk.FileChooserDialog):
    """File chooser dialog for spectrum importing."""
    __gtype_name__ = "GXPSImportDialog"
    def __init__(self, *_args, **_kwargs):
        super().__init__(
            "Import data...",
            None,
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        self.set_select_multiple(True)
        self.add_filter(FileFilter("all files", ["*.xym", "*txt", "*.xy"]))
        self.add_filter(FileFilter(".xym", ["*.xym"]))
        self.add_filter(FileFilter(".xy", ["*.xy"]))
        self.add_filter(FileFilter(".txt", ["*.txt"]))


class GXPSOpenProjectDialog(Gtk.FileChooserDialog):
    """File chooser dialog for spectrum importing."""
    __gtype_name__ = "GXPSOpenProjectDialog"
    def __init__(self, *_args, **_kwargs):
        super().__init__(
            "Open project...",
            None,
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        self.add_filter(FileFilter(".gxps", ["*.gxps"]))


class GXPSMergeProjectDialog(Gtk.FileChooserDialog):
    """File chooser dialog for spectrum importing."""
    __gtype_name__ = "GXPSMergeProjectDialog"
    def __init__(self, *_args, **_kwargs):
        super().__init__(
            "Merge project...",
            None,
            Gtk.FileChooserAction.OPEN,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Open", Gtk.ResponseType.OK),
        )
        self.add_filter(FileFilter(".gxps", ["*.gxps"]))


class GXPSSaveProjectDialog(Gtk.FileChooserDialog):
    """File chooser dialog for spectrum importing."""
    __gtype_name__ = "GXPSSaveProjectDialog"
    def __init__(self, *_args, **_kwargs):
        super().__init__(
            "Save project...",
            None,
            Gtk.FileChooserAction.SAVE,
            ("_Cancel", Gtk.ResponseType.CANCEL, "_Save", Gtk.ResponseType.OK),
        )
        self.add_filter(FileFilter(".gxps", ["*.gxps"]))
        self.set_do_overwrite_confirmation(True)


class GXPSPeakTreeStore(Gtk.TreeStore):
    """Treestore with peak information.
    """
    __gtype_name__ = "GXPSPeakTreeStore"
    def __init__(self, *_args, **_kwargs):
        titles = State.titles["peak_view"]
        # the first column is "is_actve"
        types = [object] + [str] * len(titles)
        super().__init__(*types)


class GXPSSpectrumTreeStore(Gtk.TreeStore):
    """Treestore with spectrum information.
    """
    __gtype_name__ = "GXPSSpectrumTreeStore"
    def __init__(self, *_args, **_kwargs):
        titles = State.titles["spectrum_view"]
        # the first column is "is_actve"
        types = [object] + [str] * len(titles)
        super().__init__(*types)


class Cursors():
    """Simple namespace for cursor reference.
    """
    # pylint: disable=too-few-public-methods
    HAND, POINTER, SELECT_REGION, MOVE, WAIT, DRAG, DELETE = list(range(7))


class GXPSPlotToolbar(NavigationToolbar2GTK3, Gtk.Toolbar):
    """Matplotlib-like toolbar with a few nice extra tools.
    """
    # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=super-init-not-called
    __gtype_name__ = "GXPSPlotToolbar"
    def __init__(self, *args, **kwargs):
        Gtk.Toolbar.__init__(self, *args, **kwargs)
        self.cursors = Cursors()
        self.cursord = {
            self.cursors.MOVE: Gdk.Cursor.new(Gdk.CursorType.FLEUR),
            self.cursors.HAND: Gdk.Cursor.new(Gdk.CursorType.HAND2),
            self.cursors.POINTER: Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR),
            self.cursors.SELECT_REGION: Gdk.Cursor.new(Gdk.CursorType.TCROSS),
            self.cursors.WAIT: Gdk.Cursor.new(Gdk.CursorType.WATCH),
            self.cursors.DRAG: Gdk.Cursor.new(
                Gdk.CursorType.SB_H_DOUBLE_ARROW),
            self.cursors.DELETE: Gdk.Cursor.new(Gdk.CursorType.X_CURSOR)
        }
        self._centerlims = [np.inf, -np.inf, np.inf, -np.inf]

    def startup(self, builder):
        """Call the real super __init__ after the canvas is known and give
        it to this function.
        """
        # pylint: disable=attribute-defined-outside-init
        self.message = builder.get_object("mpl_message_label")
        self.mode_label = self.message
        self.xy_label = builder.get_object("mpl_coord_label")
        canvas = builder.get_object("main_canvas")
        super().__init__(canvas, None)

        self.span_selector = SpanSelector(
            self.canvas.figure.get_axes()[0],
            lambda *args: None,
            "horizontal",
            minspan=0.2,
            span_stays=False,
            useblit=True
        )
        self.span_selector.active = False
        self.peak_selector = PeakSelector(
            self.canvas.figure.get_axes()[0],
            lambda *args: None,
            peak_stays=False,
            useblit=True
        )
        self.peak_selector.active = False
        self.point_selector = PointSelector(
            self.canvas.figure.get_axes()[0],
            lambda *args: None,
        )
        self.point_selector.active = False

    def _init_toolbar(self):
        """Normally, this would create the buttons and connect them to
        the tools, but now GtkBuilder does the job and the connections
        are done in the Gtk.Application. This function is automatically
        called during NavigationToolbar.__init__
        """

    def set_history_buttons(self):
        """Same as above, this prevents the use of self._gtk_ids."""

    def disable_tools(self):
        """Release widgetlock and disconnect all signals associated with
        native matplotlib toolbar tools.
        """
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)

        self._active = None
        self.mode = ""
        self.release_all_tools()
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(self._active)
        self.set_message(self.mode)

    def get_point(self, callback, onmove_callback=None):
        """Gets a x, y point on the canvas and then calls
        callback(x0, y0, x, y) where x0, y0 are the coords when pressing
        the mouse and x, y are the coords when releasing.
        """
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ""
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ""

        mode = callback.__doc__

        self.release_all_tools()
        if self._active == mode:
            self._active = None
            self.mode = ""
            self.point_selector.active = False
            self.set_message(self.mode)
            return

        self._active = mode
        self.mode = mode
        self.canvas.widgetlock(self.point_selector)
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(None)
        self.set_message(self.mode)

        def on_selected(x0, y0, x, y):
            """Callback caller."""
            self._active = None
            self.mode = ""
            self.point_selector.active = False
            self.release_all_tools()
            self.set_message(self.mode)
            self._set_cursor(event=None)
            callback(x0, y0, x, y)

        self.point_selector.onselect = on_selected
        self.point_selector.onmove_callback = onmove_callback
        self.point_selector.active = True

    def get_span(self, callback, **kwargs):
        """Gets a span and then calls callback(min, max). Also takes care
        of widgetlock and such.
        """
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ""
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ""

        mode = callback.__doc__

        self.release_all_tools()
        if self._active == mode:
            self._active = None
            self.mode = ""
            self.span_selector.active = False
            self.set_message(self.mode)
            return

        self._active = mode
        self.mode = mode
        self.canvas.widgetlock(self.span_selector)
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(None)
        self.set_message(self.mode)

        def on_selected(emin, emax):
            """Callback caller."""
            self._active = None
            self.mode = ""
            self.span_selector.active = False
            self.release_all_tools()
            self.set_message(self.mode)
            self._set_cursor(event=None)
            callback(emin, emax)
        rectprops = {
            "alpha": 1,
            "fill": False,
            "edgecolor": "black",
            "linewidth": 1,
            "linestyle": "-"
        }
        rectprops.update(kwargs)
        self.span_selector.set_rectprops(rectprops)
        self.span_selector.onselect = on_selected
        self.span_selector.active = True

    def get_wedge(self, callback, **kwargs):
        """Gets a wegde and then calls callback(center, height, fwhm).
        Also takes care of widgetlock and such.
        """
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ""
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ""

        mode = callback.__doc__

        self.release_all_tools()
        if self._active == mode:
            self._active = None
            self.mode = ""
            self.peak_selector.active = False
            self.set_message(self.mode)
            return

        self._active = mode
        self.mode = mode
        self.canvas.widgetlock(self.peak_selector)
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(None)
        self.set_message(self.mode)

        def on_selected(center, height, angle):
            """Callback caller."""
            self._active = None
            self.mode = ""
            self.peak_selector.active = False
            self.release_all_tools()
            self.set_message(self.mode)
            self._set_cursor(event=None)
            callback(center, height, angle)
        wedgeprops = {
            "alpha": 0.5,
            "fill": True,
            "edgecolor": "black",
            "linewidth": 1,
            "linestyle": "-"
        }
        if "limits" in kwargs:
            self.peak_selector.set_limits(kwargs.pop("limits"))
        else:
            self.peak_selector.set_limits((-np.inf, np.inf))
        wedgeprops.update(kwargs)
        self.peak_selector.set_wedgeprops(wedgeprops)
        self.peak_selector.onselect = on_selected
        self.peak_selector.active = True

    def pan(self, *_ignore):
        """Activate the pan/zoom tool. pan with left button, zoom with right
        OVERWRITE because of widgetlock release.
        """
        # set the pointer icon and button press funcs to the
        # appropriate callbacks
        if self._active == 'PAN':
            self._active = None
        else:
            self._active = 'PAN'
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ''
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ''
        self.release_all_tools()        # changed here
        if self._active:
            self._idPress = self.canvas.mpl_connect(
                'button_press_event', self.press_pan)
            self._idRelease = self.canvas.mpl_connect(
                'button_release_event', self.release_pan)
            self.mode = 'Pan / Zoom'
            self.canvas.widgetlock(self)
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(self._active)
        self.set_message(self.mode)

    def zoom(self, *args):
        """Activate zoom to rect mode.
        OVERWRITE because of widgetlock release.
        """
        if self._active == 'ZOOM':
            self._active = None
        else:
            self._active = 'ZOOM'
        if self._idPress is not None:
            self._idPress = self.canvas.mpl_disconnect(self._idPress)
            self.mode = ''
        if self._idRelease is not None:
            self._idRelease = self.canvas.mpl_disconnect(self._idRelease)
            self.mode = ''
        self.release_all_tools()        # changed here
        if self._active:
            self._idPress = self.canvas.mpl_connect(
                'button_press_event', self.press_zoom)
            self._idRelease = self.canvas.mpl_connect(
                'button_release_event', self.release_zoom)
            self.mode = 'Zoom Rectangle'
            self.canvas.widgetlock(self)
        for ax in self.canvas.figure.get_axes():
            ax.set_navigate_mode(self._active)
        self.set_message(self.mode)

    def draw_rubberband(self, event, x0, y0, x1, y1):
        # pylint: disable=too-many-arguments
        """adapted from
        http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/189744
        """
        self.ctx = self.canvas.get_property("window").cairo_create()
        self.canvas.draw()
        height = self.canvas.figure.bbox.height
        y1 = height - y1
        y0 = height - y0
        w = abs(x1 - x0)
        h = abs(y1 - y0)
        rect = [int(val) for val in (min(x0, x1), min(y0, y1), w, h)]
        self.ctx.new_path()
        self.ctx.set_line_width(0.5)
        self.ctx.rectangle(rect[0], rect[1], rect[2], rect[3])
        self.ctx.set_source_rgb(0.95, 0.95, 0.95)   # this is the change
        self.ctx.stroke()

    def center(self):
        """Centers view and disables navbar tools.
        """
        self.disable_tools()
        self.canvas.center_view()
        self.canvas.draw_idle()

    def release_all_tools(self):
        """Release all tools used in this class from self.canvas.widgetlock
        because the locks have different owners.
        """
        try:
            self.canvas.widgetlock.release(self)
        except ValueError:
            try:
                self.canvas.widgetlock.release(self.span_selector)
            except ValueError:
                try:
                    self.canvas.widgetlock.release(self.peak_selector)
                except ValueError:
                    self.canvas.widgetlock.release(self.point_selector)

    def mouse_move(self, event):
        self._set_cursor(event)
        if event.inaxes and event.inaxes.get_navigate():
            try:
                s = event.inaxes.format_coord(event.xdata, event.ydata)
                self.xy_label.set_markup("<tt>{}</tt>".format(s))
            except (ValueError, OverflowError):
                pass
        if self.mode:
            self.mode_label.set_text("{}".format(self.mode))

    def set_cursor(self, cursor):
        self.canvas.get_property("window").set_cursor(self.cursord[cursor])
        Gtk.main_iteration()

    def _set_cursor(self, event):
        if not event or not event.inaxes or not self._active:
            if self._lastCursor != self.cursors.POINTER:
                self.set_cursor(self.cursors.POINTER)
                self._lastCursor = self.cursors.POINTER
        else:
            if (self._active == 'ZOOM'
                    and self._lastCursor != self.cursors.SELECT_REGION):
                self.set_cursor(self.cursors.SELECT_REGION)
                self._lastCursor = self.cursors.SELECT_REGION
            elif (self._active == 'PAN' and
                  self._lastCursor != self.cursors.MOVE):
                self.set_cursor(self.cursors.MOVE)
                self._lastCursor = self.cursors.MOVE
            elif (self._active == 'Add region' and
                  self._lastCursor != self.cursors.DRAG):
                self.set_cursor(self.cursors.DRAG)
                self._lastCursor = self.cursors.DRAG
            elif (self._active == 'Remove region' and
                  self._lastCursor != self.cursors.DELETE):
                self.set_cursor(self.cursors.DELETE)
                self._lastCursor = self.cursors.DELETE
            elif self._active == "Add peak":
                lims = self.peak_selector.limits
                if lims[0] < event.xdata < lims[1]:
                    if self._lastCursor != self.cursors.SELECT_REGION:
                        self.set_cursor(self.cursors.SELECT_REGION)
                        self._lastCursor = self.cursors.SELECT_REGION
                else:
                    if self._lastCursor != self.cursors.POINTER:
                        self.set_cursor(self.cursors.POINTER)
                        self._lastCursor = self.cursors.POINTER
