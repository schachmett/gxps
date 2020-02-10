"""Classes managing single representation parts of the app."""
# pylint: disable=wrong-import-position
# pylint: disable=logging-format-interpolation
# pylint: disable=too-few-public-methods

import logging
import re
from itertools import cycle

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango, GLib

from gxps import __appname__, COLORS
from gxps.utility import Event
from gxps.io import get_element_rsfs


LOG = logging.getLogger(__name__)


class ViewManager():
    """Helper class for instantiating all the GUI manager classes."""
    def __init__(self, app, gui, spectra):
        self.complement_builder(app.builder)
        self.window_vbehaviour = WindowBehaviour(app, gui, spectra)
        self.plot_vmanager = PlotManager(app, gui, spectra)
        self.spectrum_vmanager = SpectrumPanelManager(app, gui, spectra)
        self.edit_vmanager = EditDialogManager(app, gui, spectra)

    @staticmethod
    def complement_builder(builder):
        """Do trivial GTK stuff that the builder can not do."""
        # Save confirmation dialog
        save_conf_dialog = builder.get_object("save_confirmation_dialog")
        save_conf_dialog.set_accels()
        # Plot navigation toolbar
        navbar = builder.get_object("plot_toolbar")
        navbar.startup(builder)
        # RSF dialog
        rsf_dialog = builder.get_object("rsf_dialog")
        rsf_entry = builder.get_object("rsf_entry")
        def apply_rsf(*_args):
            """Let the dialog send APPLY response."""
            rsf_dialog.emit("response", Gtk.ResponseType.APPLY)
        rsf_entry.connect("activate", apply_rsf)



class WindowBehaviour():
    """Manages all things that regard the behavior and appearance of the
    main window.
    """
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra
        self._win = self._app.builder.get_object("main_window")
        statusbar = self._app.builder.get_object("statusbar")
        self._statusbar_id = statusbar.get_context_id("")
        self._gui.connect("changed-project", self.update_titlebar)

    def update_titlebar(self, _event):
        """Updates the title bar to show the current project."""
        fname = self._gui.current_project
        isaltered = self._gui.project_isaltered
        if fname:
            if isaltered:
                fname += "*"
            self._win.set_title(u"{} — {}".format(fname, __appname__))
        else:
            self._win.set_title(__appname__)

    def display(self, event):
        """Updates the statusbar message."""
        message = event.message
        try:
            if event.do_log:
                LOG.info("statusbar: {}".format(message))
        except AttributeError:
            pass
        statusbar = self._app.builder.get_object("statusbar")
        message_id = statusbar.push(self._statusbar_id, message)
        def erase_message():
            """Pop message from the statusbar."""
            statusbar.remove(self._statusbar_id, message_id)
            return False
        try:
            GLib.timeout_add_seconds(event.timeout, erase_message)
        except AttributeError:
            pass


class PlotManager():
    """Draws the spectra onto the canvas. Listens to GUIState for what
    exactly to draw.
    """
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra
        # Set the canvas up
        self._canvas = self._app.builder.get_object("main_canvas")
        self._figure = self._canvas.figure
        self._ax = self._canvas.ax
        self._navbar = self._app.builder.get_object("plot_toolbar")
        # Connect to changes of the states
        self._gui.connect("changed-active", self.update, keepaxes=False)
        self._gui.connect("changed-rsf", self.update)
        self._spectra.connect("changed-spectrum", self.update)

    def update(self, event, keepaxes=True):
        """Updates plot by redrawing the whole thing. Relies on
        GUIState for information on what to plot. Designed as a
        callback function for when the plot should change.
        """
        if event.signal == "changed-spectrum":
            if event.source not in self._gui.active_spectra:
                return
            if event.attr in ("normalization_type", "normalization_divisor"):
                keepaxes = False
        # Save axis limits if needed, wipe the canvas and prepare for new
        # centering axis limits.
        if keepaxes:
            self._canvas.store_xylims()
        self._ax.cla()
        self._canvas.reset_xy_centerlims()
        self._plot_spectra()
        self._plot_rsf()
        # Either restore axis limits or center plot.
        if keepaxes:
            self._canvas.restore_xylims()
        else:
            self._canvas.center_view()
        self._canvas.draw_idle()
        self._navbar.disable_tools()

    def _plot_spectra(self):
        colors = cycle(COLORS["Plotting"]["spectra"].split(","))
        for spectrum in self._gui.active_spectra:
            color = next(colors).strip()
            line = {
                "color": color,
                "linewidth": 1,
                "linestyle": "-",
                "alpha": 1
            }
            self._ax.plot(spectrum.energy, spectrum.intensity, **line)
            line = {
                "color": COLORS["Plotting"]["region-vlines"],
                "linewidth": 2,
                "linestyle": "--",
                "alpha": 1
            }
            for bound in spectrum.background_bounds:
                self._ax.axvline(bound, 0, 1, **line)
            line = {
                "color": COLORS["Plotting"]["region-background"],
                "linewidth": 1,
                "linestyle": "--"
            }
            if any(spectrum.background):
                self._ax.plot(spectrum.energy, spectrum.background, **line)

            self._canvas.update_xy_centerlims(
                min(spectrum.energy),
                max(spectrum.energy),
                min(spectrum.intensity),
                max(spectrum.intensity)
            )

    def _plot_rsf(self):
        element_colors = cycle(COLORS["Plotting"]["rsf-vlines"].split(","))
        max_rsf = 1e-9
        orbitals = []
        for element in self._gui.rsf_elements:
            color = next(element_colors).strip()
            element = get_element_rsfs(element, self._gui.photon_source)
            for orbital in element:
                max_rsf = max(orbital["RSF"], max_rsf)
                orbital["color"] = color
            orbitals.extend(element)
        for orbital in orbitals:
            if orbital["RSF"] == 0:
                orbital["RSF"] = max_rsf * 0.5
            self._ax.axvline(
                orbital["BE"],
                0,
                orbital["RSF"] / max_rsf * 0.8,
                color=orbital["color"],
                lw=2
            )
            self._ax.annotate(
                "{} {}".format(orbital["Element"], orbital["Orbital"]),
                xy=(orbital["BE"], orbital["RSF"] / max_rsf * 0.8 + 0.08),
                color=COLORS["Plotting"]["rsf-annotation"],
                xycoords=("data", "figure fraction"),
                ha="center",
                va="bottom"
            )


class SpectrumPanelManager():
    """Manages representation of the spectra inside a treeview. Data
    is pulled from the SpectrumContainer and user changeable representation
    attributes are fetched from GUIState.
    Also manages the widgets for manipulating spectra in the same panel.
    """
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra

        tvmenu = self._app.builder.get_object("spectrum_view_context_menu")
        treeview = self._app.builder.get_object("spectrum_view")
        tvmenu.attach_to_widget(treeview, None)
        norm_combo = self._app.builder.get_object("normalization_combo")
        renderer = norm_combo.get_cells()[0]
        renderer.set_property("width-chars", 10)

        self._make_columns()
        self._setup_filter()
        self.update_controls(Event())

        self._spectra.connect("changed-spectrum", self.update_data)
        self._spectra.connect("changed-metadata", self.update_data)
        self._spectra.connect("changed-spectra", self.update_data)
        self._gui.connect("changed-active", self.update_data)
        self._gui.connect("changed-tv", self.update_filter)
        self._spectra.connect("changed-spectrum", self.update_controls)
        self._gui.connect("changed-active", self.update_controls)

    def update_filter(self, event):
        """Updates the filtering with filter parameters from GUIState.
        To be used as callback function.
        """
        if event.signal == "changed-tv" and event.attr != "filter":
            return
        treemodelfilter = self._app.builder.get_object(
            "spectrum_filter_treestore")
        treemodelfilter.refilter()

    def update_data(self, event):
        """Updates TreeModel with data from the SpectrumContainer.
        To be used as callback function.
        """
        if event.signal == "changed-active" and event.attr != "spectra":
            return
        selected_spectra = self._gui.selected_spectra
        # update model
        treestore = self._app.builder.get_object("spectrum_treestore")
        treestore.clear()
        for spectrum in self._spectra.spectra:
            row = [
                str(spectrum.meta.get(meta_attr))
                for meta_attr in self._gui.spectra_tv_columns
            ]
            treestore.append(parent=None, row=[spectrum] + row)
        # reset selected spectra
        self._set_selection(selected_spectra)

    def update_controls(self, event):
        """Updates the widgets for spectrum manipulation.
        Be careful: Changing a spinbutton value does not equate changing
        the adjustment value. Pay attention to what signals should be emitted,
        for example the updating of the value representation should not
        update the value itself again.
        """
        if event.signal == "changed-active" and event.attr != "spectra":
            return
        active_spectra = self._gui.active_spectra
        cal_spinbutton = self._app.builder.get_object("calibration_spinbutton")
        cal_caution = self._app.builder.get_object("cal_caution_image")
        norm_combo = self._app.builder.get_object("normalization_combo")
        norm_entry = self._app.builder.get_object("normalization_entry")
        norm_caution = self._app.builder.get_object("norm_caution_image")
        if not active_spectra:
            norm_combo.set_active_id(None)
            norm_caution.set_visible(False)
            cal_spinbutton.set_value(0.0)
            cal_caution.set_visible(False)
            norm_entry.set_text("")
            norm_entry.set_sensitive(False)
        else:
            norm_types = [s.normalization_type for s in active_spectra]
            if len(set(norm_types)) > 1:
                norm_combo.set_active_id(None)
                norm_caution.set_visible(True)
                norm_entry.set_sensitive(False)
            else:
                normid = self._gui.titles["norm_type_ids"][norm_types[0]]
                norm_combo.set_active_id(normid)
                norm_caution.set_visible(False)
                if norm_types[0] == "manual":
                    norm_entry.set_sensitive(True)
                else:
                    norm_entry.set_sensitive(False)
            norm_divs = [s.normalization_divisor for s in active_spectra]
            if len(set(norm_divs)) > 1:
                norm_entry.set_text("")
            else:
                norm_entry.set_text("{:.2f}".format(norm_divs[0]))
            cals = [s.energy_calibration for s in active_spectra]
            if len(set(cals)) > 1:
                cal_spinbutton.set_text("")
                cal_caution.set_visible(True)
            else:
                cal_spinbutton.set_value(cals[0])
                cal_caution.set_visible(False)
                # TODO make manual normalization work correctly!

    def _set_selection(self, spectra):
        """Selects rows representing spectra."""
        selection = self._app.builder.get_object("spectrum_selection")
        treemodelsort = self._app.builder.get_object("spectrum_sort_treestore")
        selection.unselect_all()
        for row in treemodelsort:
            if row[0] in spectra:
                selection.select_iter(row.iter)

    def _make_columns(self):
        # render function for making plotted spectra bold and light blue
        treeview = self._app.builder.get_object("spectrum_view")
        highlight_bg = COLORS["Treeview"]["tv-highlight-bg"]
        lowlight_bg = treeview.style_get_property("even-row-color")
        def render_isplotted(_col, renderer, model, iter_, *_data):
            """Renders the cell light blue if this spectrum is plotted."""
            spectrum = model.get_value(iter_, 0)
            if spectrum in self._gui.active_spectra:
            # if model.get_value(iter_, 1):
                renderer.set_property("cell-background", highlight_bg)
                renderer.set_property("weight", Pango.Weight.BOLD)
            else:
                renderer.set_property("cell-background", lowlight_bg)
                renderer.set_property("weight", Pango.Weight.NORMAL)
        # the other columns are simple, just apply the render_isplotted func
        for i, meta_attr in enumerate(self._gui.spectra_tv_columns):
            renderer = Gtk.CellRendererText(xalign=0)
            title = self._gui.titles["spectrum_view"][meta_attr]
            # skip first two columns, they are "is_actve" and "spectrum"
            column = Gtk.TreeViewColumn(title, renderer, text=i + 1)
            column.set_cell_data_func(renderer, render_isplotted)
            column.set_sort_column_id(i + 1)
            column.set_resizable(True)
            column.set_reorderable(True)
            treeview.append_column(column)

    def _setup_filter(self):
        # filling the combobox that determines self.tv_filter[0]
        filtercombo = self._app.builder.get_object(
            "spectrum_view_search_combo")
        treemodelfilter = self._app.builder.get_object(
            "spectrum_filter_treestore")
        for i, meta_attr in enumerate(self._gui.spectra_tv_columns):
            title = self._gui.titles["spectrum_view"][meta_attr]
            filtercombo.append_text(title)
            if meta_attr == self._gui.spectra_tv_filter[0]:
                filtercombo.set_active(i)
        # this function looks into self.tv_filter and executes the regex
        # matching, returning True if the row should be visible
        def filter_func(treemodel, iter_, *_data):
            """Returns True only for rows whose values for the attr
            from self.tv_filter matches the regex from self.tv_filter."""
            meta_attr, search_term = self._gui.spectra_tv_filter
            if not meta_attr or not search_term:
                return True
            regex = re.compile(r".*{}.*".format(search_term), re.IGNORECASE)
            # skip first two columns, they are "is_actve" and "spectrum"
            col_index = self._gui.spectra_tv_columns.index(meta_attr) + 1
            return re.match(regex, treemodel.get(iter_, col_index)[0])
        treemodelfilter.set_visible_func(filter_func)


class EditDialogManager():
    """Manages the dialog for editing spectra."""
    _exclusion_key = " (mult.)"
    def __init__(self, app, gui, spectra):
        self._app = app
        self._gui = gui
        self._spectra = spectra
        self._dialog = self._app.builder.get_object("edit_spectrum_dialog")
        self._dialog.exclusion_key = self._exclusion_key
        self._gui.connect("changed-editing-spectra", self.update_dialog)

    def update_dialog(self, *_args):
        """Updates the dialog to represent the spectra to be edited."""
        spectra = self._gui.editing_spectra
        self._dialog.flush()
        def get_value_string(attr, separator=" | "):
            """Returns string to go inside the value fields."""
            if not spectra:
                return ""
            if len(spectra) == 1:
                return str(spectra[0].meta.get(attr))
            values = [str(spectrum.meta.get(attr)) for spectrum in spectra]
            valueset = set(values)
            if len(valueset) > 1:
                valuestring = separator.join(valueset) + self._exclusion_key
            else:
                valuestring = values[0]
            return valuestring

        for attr, title in self._gui.titles["static_specinfo"].items():
            valstring = get_value_string(attr, separator="\n")
            valstring = valstring.replace("None", "NO VALUE SET")
            self._dialog.add_non_editable_row(title, valstring)
        for attr, title in self._gui.titles["editing_dialog"].items():
            valstring = get_value_string(attr)
            valstring = valstring.replace("None", "NO VALUE SET")
            self._dialog.add_editor_row(attr, title, valstring)
