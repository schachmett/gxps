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
from gxps.io import get_element_rsfs
from gxps.spectrum import Peak


LOG = logging.getLogger(__name__)


class ViewManager():
    """Helper class for instantiating all the GUI manager classes."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, app, state, data):
        self.bus = app.bus
        self.data = data
        self.state = state
        self.get_widget = app.get_widget

        self._window = self._instantiate_window()
        self._plot = self._instantiate_plot()
        self._spectra_panel = self._instantiate_spectra_panel()
        self._peaks_panel = self._instantiate_peaks_panel()
        self._edit_dialog = self._instantiate_edit_dialog()

        vlines = self.get_widget("canvas_objects")
        vlines.set_bus(self.bus)

    def _instantiate_window(self):
        """Make a window manager."""
        window = Window(self.get_widget, self.state, self.data)
        signals = ("changed-project", )
        for signal in signals:
            self.bus.subscribe(window.update_titlebar, signal)
        return window

    def _instantiate_plot(self):
        """Make a Plot manager."""
        plot = Plot(self.get_widget, self.state, self.data)
        signals = ("changed-active", "changed-rsf", "changed-spectrum",
                   "changed-fit", "changed-peak")
        for signal in signals:
            self.bus.subscribe(plot.update, signal, priority=10)
        return plot

    def _instantiate_spectra_panel(self):
        """Make a SpectraPanelManager."""
        spectra_panel = SpectraPanel(self.get_widget, self.state, self.data)
        signals = (
            "changed-spectrum",
            "changed-spectrum-meta",
            "changed-spectra",
            "changed-active"
        )
        for signal in signals:
            self.bus.subscribe(spectra_panel.update_data, signal)
        self.bus.subscribe(spectra_panel.update_filter, "changed-tv")
        self.bus.subscribe(spectra_panel.update_controls, "changed-spectrum")
        self.bus.subscribe(spectra_panel.update_controls, "changed-active")
        return spectra_panel

    def _instantiate_peaks_panel(self):
        """Make a PeakPanelManager."""
        peaks_panel = PeakPanel(self.get_widget, self.state, self.data)
        signals = (
            "changed-peak",
            "changed-peak-meta",
            "changed-fit",
            "changed-active"
        )
        for signal in signals:
            self.bus.subscribe(peaks_panel.update_data, signal)
            self.bus.subscribe(peaks_panel.update_controls, signal)
        return peaks_panel

    def _instantiate_edit_dialog(self):
        """Make a EditDialogManager."""
        edit_dialog = EditDialog(self.get_widget, self.state, self.data)
        self.bus.subscribe(edit_dialog.update, "changed-editing-spectra")
        return edit_dialog


class View:
    """Meta class for objects that contain the main functions of the
    application as methods.
    """
    def __init__(self, get_widget, state, data):
        self.get_widget = get_widget
        self.state = state
        self.data = data


class Window(View):
    """Manages all things that regard the behavior and appearance of the
    main window.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        statusbar = self.get_widget("statusbar")
        self._statusbar_id = statusbar.get_context_id("")

    def update_titlebar(self, _event):
        """Updates the title bar to show the current project."""
        fname = self.state.current_project
        isaltered = self.state.project_isaltered
        win = self.get_widget("main_window")
        if fname:
            if isaltered:
                fname += "*"
            win.set_title(u"{} — {}".format(fname, __appname__))
        else:
            win.set_title(__appname__)

    def display(self, event):
        """Updates the statusbar message."""
        message = event.message
        try:
            if event.do_log:
                LOG.info("statusbar: {}".format(message))
        except AttributeError:
            pass
        statusbar = self.get_widget("statusbar")
        message_id = statusbar.push(self._statusbar_id, message)
        def erase_message():
            """Pop message from the statusbar."""
            statusbar.remove(self._statusbar_id, message_id)
            return False
        try:
            GLib.timeout_add_seconds(event.timeout, erase_message)
        except AttributeError:
            pass


class Plot(View):
    """Draws the spectra onto the canvas. Listens to GUIState for what
    exactly to draw.
    """
    # pylint: disable=too-many-instance-attributes
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._canvas = self.get_widget("main_canvas")
        self._ax = self._canvas.ax

    def update(self, event, keepaxes=True):
        """Updates plot by redrawing the whole thing. Relies on
        GUIState for information on what to plot. Designed as a
        callback function for when the plot should change.
        """
        if event.signal == "changed-spectrum":
            if not set(event.source) & set(self.state.active_spectra):
                return
            for attr in event.properties["attr"]:
                if attr in ("normalization_type", "normalization_divisor"):
                    keepaxes = False
        if event.signal == "changed-active":
            keepaxes = False
        # Save axis limits if needed, wipe the canvas and prepare for new
        # centering axis limits.
        if keepaxes:
            self._canvas.store_xylims()
        self._ax.cla()
        self._canvas.reset_xy_centerlims()
        self._plot_spectra()
        self._plot_peaks()
        self._plot_rsf()
        # Either restore axis limits or center plot.
        if keepaxes:
            self._canvas.restore_xylims()
        else:
            self._canvas.center_view()
        self._canvas.draw_idle()
        navbar = self.get_widget("plot_toolbar")
        navbar.disable_tools()

    def _plot_spectra(self):
        colors = cycle(COLORS["Plotting"]["spectra"].split(","))
        vlines = self.get_widget("canvas_objects")
        vlines.clear()
        for spectrum in self.state.active_spectra:
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
                linewidget = self._ax.axvline(bound, 0, 1, **line)
                vlines.add_line(linewidget, spectrum)
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

    def _plot_peaks(self):
        inactive_color = COLORS["Plotting"]["peak"]
        active_color = COLORS["Plotting"]["peak-active"]
        sum_color = COLORS["Plotting"]["peak-sum"]
        for spectrum in self.state.active_spectra:
            for peak in spectrum.peaks:
                line = {}
                if peak in self.state.active_peaks:
                    line = {
                        "color": active_color,
                        "linewidth": 1,
                        "linestyle": "--",
                        "alpha": 0.2
                    }
                    self._ax.fill_between(
                        spectrum.energy,
                        spectrum.background + peak.intensity,
                        spectrum.background,
                        **line
                    )
                else:
                    line = {
                        "color": inactive_color,
                        "linewidth": 1,
                        "linestyle": "--",
                    }
                self._ax.plot(
                    spectrum.energy,
                    spectrum.background + peak.intensity,
                    **line
                )
            line = {
                "color": sum_color,
                "linewidth": 1,
                "linestyle": "--",
            }
            self._ax.plot(
                spectrum.energy,
                spectrum.background + spectrum.fit,
                **line
            )

    def _plot_rsf(self):
        element_colors = cycle(COLORS["Plotting"]["rsf-vlines"].split(","))
        max_rsf = 1e-9
        orbitals = []
        for element in self.state.rsf_elements:
            color = next(element_colors).strip()
            element = get_element_rsfs(element, self.state.photon_source)
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


class SpectraPanel(View):
    """Manages representation of the spectra inside a treeview. Data
    is pulled from the SpectrumContainer and user changeable representation
    attributes are fetched from GUIState.
    Also manages the widgets for manipulating spectra in the same panel.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tvmenu = self.get_widget("spectrum_view_context_menu")
        treeview = self.get_widget("spectrum_view")
        tvmenu.attach_to_widget(treeview, None)
        norm_combo = self.get_widget("normalization_combo")
        renderer = norm_combo.get_cells()[0]
        renderer.set_property("width-chars", 10)
        self._make_columns()
        self._setup_filter()

    def update_filter(self, event):
        """Updates the filtering with filter parameters from GUIState.
        To be used as callback function.
        """
        if event.signal == "changed-tv":
            if "filter" not in event.properties["attr"]:
                return
        treemodelfilter = self.get_widget("spectrum_filter_treestore")
        treemodelfilter.refilter()

    def update_data(self, event):
        """Updates TreeModel with data from the SpectrumContainer.
        To be used as callback function.
        """
        if event.signal == "changed-active":
            if "spectra" not in event.properties["attr"]:
                return
        selected_spectra = self.state.selected_spectra
        # update model
        treestore = self.get_widget("spectrum_treestore")
        treestore.clear()
        for spectrum in self.data.spectra:
            row = [
                str(spectrum.get_meta(attr))
                for attr in list(self.state.titles["spectrum_view"].keys())
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
        if event.signal == "changed-active":
            if "spectra" not in event.properties["attr"]:
                return
        active_spectra = self.state.active_spectra
        cal_spinbutton = self.get_widget("calibration_spinbutton")
        cal_caution = self.get_widget("cal_caution_image")
        norm_combo = self.get_widget("normalization_combo")
        norm_entry = self.get_widget("normalization_entry")
        norm_caution = self.get_widget("norm_caution_image")
        if not active_spectra:
            norm_combo.set_active(-1)
            norm_caution.set_visible(False)
            cal_spinbutton.set_value(0.0)
            cal_caution.set_visible(False)
            norm_entry.set_text("")
            norm_entry.set_sensitive(False)
        else:
            norm_types = [s.normalization_type for s in active_spectra]
            if len(set(norm_types)) > 1:
                norm_combo.set_active(-1)
                norm_caution.set_visible(True)
                norm_entry.set_sensitive(False)
            else:
                normid = self.state.titles["norm_type_ids"][norm_types[0]]
                norm_combo.set_active(int(normid))
                # this circumvents signal emission instead
                # of this: norm.set_active_id(normid)
                norm_caution.set_visible(False)
                if norm_types[0] == "manual":
                    norm_entry.set_sensitive(True)
                else:
                    norm_entry.set_sensitive(False)
            norm_divs = [s.normalization_divisor for s in active_spectra]
            if len(set(norm_divs)) > 1:
                norm_entry.set_text("")
            else:
                norm_entry.set_text("{:.5f}".format(1 / norm_divs[0]))
            cals = [s.energy_calibration for s in active_spectra]
            if len(set(cals)) > 1:
                cal_spinbutton.set_text("")
                cal_caution.set_visible(True)
            else:
                cal_spinbutton.set_value(cals[0])
                cal_caution.set_visible(False)

    def _set_selection(self, spectra):
        """Selects rows representing spectra."""
        selection = self.get_widget("spectrum_selection")
        treemodelsort = self.get_widget("spectrum_sort_treestore")
        selection.unselect_all()
        for row in treemodelsort:
            if row[0] in spectra:
                selection.select_iter(row.iter)

    def _make_columns(self):
        treeview = self.get_widget("spectrum_view")
        highlight_bg = COLORS["Treeview"]["tv-highlight-bg"]
        lowlight_bg = treeview.style_get_property("even-row-color")
        def render_isplotted(_col, renderer, model, iter_, *_data):
            """Renders the cell light blue if this spectrum is plotted."""
            # render function for making plotted spectra bold and light blue
            spectrum = model.get_value(iter_, 0)
            if spectrum in self.state.active_spectra:
                renderer.set_property("cell-background", highlight_bg)
                renderer.set_property("weight", Pango.Weight.BOLD)
            else:
                renderer.set_property("cell-background", lowlight_bg)
                renderer.set_property("weight", Pango.Weight.NORMAL)
        # the other columns are simple, just apply the render_isplotted func
        for attr in self.state.spectra_tv_columns:
            renderer = Gtk.CellRendererText(xalign=0)
            title = self.state.titles["spectrum_view"][attr]
            # skip first column, it is "spectrum"
            idx = list(self.state.titles["spectrum_view"].keys()).index(attr)
            column = Gtk.TreeViewColumn(title, renderer, text=idx + 1)
            column.set_cell_data_func(renderer, render_isplotted)
            column.set_sort_column_id(idx + 1)
            column.set_resizable(True)
            column.set_reorderable(True)
            treeview.append_column(column)

    def _setup_filter(self):
        # filling the combobox that determines self.tv_filter[0]
        filtercombo = self.get_widget("spectrum_view_search_combo")
        treemodelfilter = self.get_widget("spectrum_filter_treestore")
        for i, meta_attr in enumerate(self.state.spectra_tv_columns):
            title = self.state.titles["spectrum_view"][meta_attr]
            filtercombo.append_text(title)
            if meta_attr == self.state.spectra_tv_filter[0]:
                filtercombo.set_active(i)
        # this function looks into self.tv_filter and executes the regex
        # matching, returning True if the row should be visible
        def filter_func(treemodel, iter_, *_data):
            """Returns True only for rows whose values for the attr
            from self.tv_filter matches the regex from self.tv_filter."""
            meta_attr, search_term = self.state.spectra_tv_filter
            if not meta_attr or not search_term:
                return True
            regex = re.compile(r".*{}.*".format(search_term), re.IGNORECASE)
            # skip first column, it is "spectrum"
            col_index = self.state.spectra_tv_columns.index(meta_attr) + 1
            return re.match(regex, treemodel.get(iter_, col_index)[0])
        treemodelfilter.set_visible_func(filter_func)


class PeakPanel(View):
    """Manages representation of the peaks inside a treeview. Data
    is pulled from the SpectrumContainer and user changeable representation
    attributes are fetched from GUIState.
    TODO: Manage the peak manipulation, e.g. manage constraints
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        shape_combo = self.get_widget("new_peak_model_combo")
        shape_combo.remove_all()
        model_combo = self.get_widget("peak_model_combo")
        model_combo.remove_all()
        for shape in Peak.shapes:
            shape_combo.append_text(shape)
            model_combo.append_text(shape)
        shape_combo.set_active(0)
        self._make_columns()

    def update_data(self, _event):
        """Updates TreeModel with data from the SpectrumContainer.
        To be used as callback function.
        """
        active_peaks = self.state.active_peaks
        # update model
        treestore = self.get_widget("peak_treestore")
        treestore.clear()
        for spectrum in self.state.active_spectra:
            for peak in spectrum.peaks:
                row = [
                    self.format_peak_attr(peak, attr)
                    for attr in list(self.state.titles["peak_view"].keys())
                ]
                treestore.append(parent=None, row=[peak] + row)
        # reset selected spectra
        self._set_selection(active_peaks)

    def update_controls(self, event):
        """Updates the entries representing peak parameters."""
        # pylint: disable=too-many-branches
        active_peaks = self.state.active_peaks
        if event.signal in ("changed-peak", "changed-peak-meta"):
            if not set(event.source) & set(active_peaks):
                return
        if event.signal == "changed-fit":
            if not set(event.source) & set(self.state.active_spectra):
                return

        model_combo = self.get_widget("peak_model_combo")
        entries = {
            "label": self.get_widget("peak_name_entry"),
            "position": self.get_widget("peak_position_entry"),
            "area": self.get_widget("peak_area_entry"),
            "fwhm": self.get_widget("peak_fwhm_entry"),
            "alpha": self.get_widget("peak_alpha_entry"),
            "beta": self.get_widget("peak_beta_entry"),
            "gamma": self.get_widget("peak_gamma_entry"),
            "real_area": self.get_widget("peak_realarea_entry"),
            "real_fwhm": self.get_widget("peak_realfwhm_entry")
        }
        labels = {
            "alpha": self.get_widget("peak_alpha_label"),
            "beta": self.get_widget("peak_beta_label"),
            "gamma": self.get_widget("peak_gamma_label")
        }

        if len(active_peaks) != 1:
            model_combo.set_active(-1)
            model_combo.set_sensitive(False)
            for entry in entries.values():
                entry.set_text("")
                entry.set_sensitive(False)
            for label in labels.values():
                label.set_text("")
            return

        peak = active_peaks[0]
        names = {
            "alpha": peak.alpha_name,
            "beta": peak.beta_name,
            "gamma": peak.gamma_name
        }

        entries["real_area"].set_text("{:.2f}".format(peak.get_area()))
        entries["real_fwhm"].set_text("{:.2f}".format(peak.get_fwhm()))
        entries["label"].set_sensitive(True)
        entries["label"].set_text(peak.label)
        for par in ("position", "area", "fwhm"):
            entries[par].set_sensitive(True)
            entries[par].set_text(self.format_peak_constraints(peak, par))
        for par in ("alpha", "beta", "gamma"):
            if names[par]:
                entries[par].set_sensitive(True)
                entries[par].set_text(self.format_peak_constraints(peak, par))
                labels[par].set_text(names[par])
            else:
                entries[par].set_sensitive(False)
                labels[par].set_text("")

        for i, shape in enumerate(Peak.shapes):
            if shape == peak.shape:
                model_combo.set_active(i)
        model_combo.set_sensitive(True)


    def format_peak_attr(self, peak, attr):
        """Returns a string representing the peak's distinct attribute."""
        if attr in ("position", "fwhm", "area", "alpha", "beta"):
            constraints = peak.get_constraints(attr)
            if constraints["value"] is None:
                return ""
            cstring = ""
            if constraints["expr"]:
                cstring += " = {}".format(constraints["expr"])
            elif not constraints["vary"]:
                cstring += " fixed"
            else:
                if constraints["min"] not in (float("-inf"), 0):
                    cstring += " &gt; {} ".format(constraints["min"])
                if constraints["max"] != (float("inf")):
                    cstring += " &lt; {}".format(constraints["max"])
            formatted = (
                "{:.2f}<span color='#999999' font_size='xx-small'> {}</span>"
                "".format(constraints["value"], cstring))
        if attr == "name":
            if len(self.state.active_spectra) >= 2:
                formatted = (
                    "{}<span color='#aaaaaa' font_size='x-small'> ({})</span>"
                    "".format(peak.name, peak.spectrum.name))
            else:
                formatted = str(peak.name)
        if attr in ("label", "shape"):
            formatted = getattr(peak, attr)
        return formatted

    @staticmethod
    def format_peak_constraints(peak, attr):
        """Returns a string representing the peak's attribute's constraints.
        """
        constraints = peak.get_constraints(attr)
        if constraints["value"] is None:
            return ""
        cstring = ""
        if constraints["expr"]:
            cstring += str(constraints["expr"])
        elif not constraints["vary"]:
            cstring += "{}".format(constraints["value"])
        else:
            if constraints["min"] not in (float("-inf"), 0):
                cstring += "> {} ".format(constraints["min"])
            if constraints["max"] != (float("inf")):
                cstring += "< {}".format(constraints["max"])
        return cstring

    def _set_selection(self, peaks):
        """Selects rows representing spectra."""
        selection = self.get_widget("peak_selection")
        treemodelsort = self.get_widget("peak_sort_treestore")
        selection.unselect_all()
        for row in treemodelsort:
            if row[0] in peaks:
                selection.select_iter(row.iter)

    def _make_columns(self):
        treeview = self.get_widget("peak_view")
        highlight_bg = COLORS["Treeview"]["tv-highlight-bg"]
        lowlight_bg = treeview.style_get_property("even-row-color")
        def render_constraints(_col, renderer, model, iter_, idx):
            """Renders the cell light blue if this peak is active."""
            # render function for making plotted spectra bold and light blue
            peak = model.get_value(iter_, 0)
            value = model.get_value(iter_, idx + 1)
            if peak in self.state.active_peaks:
                renderer.set_property("cell-background", highlight_bg)
                renderer.set_property("weight", Pango.Weight.BOLD)
            else:
                renderer.set_property("cell-background", lowlight_bg)
                renderer.set_property("weight", Pango.Weight.NORMAL)
            renderer.set_property("markup", value)
        # the other columns are simple, just apply the render_isplotted func
        for attr in self.state.peak_tv_columns:
            renderer = Gtk.CellRendererText(xalign=0)
            title = self.state.titles["peak_view"][attr]
            idx = list(self.state.titles["peak_view"].keys()).index(attr)
            # skip first column, it is "peak"
            column = Gtk.TreeViewColumn(title, renderer, text=idx + 1)
            column.set_cell_data_func(renderer, render_constraints, idx)
            column.set_sort_column_id(idx + 1)
            column.set_resizable(True)
            column.set_reorderable(True)
            treeview.append_column(column)


class EditDialog(View):
    """Manages the dialog for editing spectra."""
    _exclusion_key = " (mult.)"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dialog = self.get_widget("edit_spectrum_dialog")
        self._dialog.exclusion_key = self._exclusion_key

    def update(self, *_args):
        """Updates the dialog to represent the spectra to be edited."""
        spectra = self.state.editing_spectra
        self._dialog.flush()
        def get_value_string(attr, separator=" | "):
            """Returns string to go inside the value fields."""
            if not spectra:
                return ""
            if len(spectra) == 1:
                return str(spectra[0].get_meta(attr))
            values = [str(spectrum.get_meta(attr)) for spectrum in spectra]
            valueset = set(values)
            if len(valueset) > 1:
                valuestring = separator.join(valueset) + self._exclusion_key
            else:
                valuestring = values[0]
            return valuestring

        for attr, title in self.state.titles["static_specinfo"].items():
            try:
                valstring = get_value_string(attr, separator="\n")
            except AttributeError:
                valstring = "NO VALUE SET"
            self._dialog.add_non_editable_row(title, valstring)
        for attr, title in self.state.titles["editing_dialog"].items():
            try:
                valstring = get_value_string(attr, separator="\n")
            except AttributeError:
                valstring = "NO VALUE SET"
            self._dialog.add_editor_row(attr, title, valstring)
