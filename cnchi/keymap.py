#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  keymap.py
#
#  Copyright © 2013-2015 Antergos
#
#  This file is part of Cnchi.
#
#  Cnchi is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  Cnchi is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Cnchi; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

from gi.repository import Gtk, GLib

import os
import logging
import subprocess

import misc.misc as misc
import misc.keyboard_names as keyboard_names
import misc.keyboard_widget as keyboard_widget

from gtkbasebox import GtkBaseBox


class Keymap(GtkBaseBox):
    def __init__(self, params, prev_page="timezone", next_page="desktop"):
        super().__init__(self, params, "keymap", prev_page, next_page)

        self.prepare_called = False

        self.keyboard_test_entry = self.ui.get_object("keyboard_test_entry")
        self.keyboard_widget = self.ui.get_object("keyboard_widget")

        self.keyboard_layout = { 'code': None, 'description': None }
        self.keyboard_variant  = { 'code': None, 'description': None }

        base_xml_path = os.path.join(self.settings.get('data'), "base.xml")
        self.kbd_names = keyboard_names.KeyboardNames(base_xml_path)

        self.init_keymap_treeview()

    def init_keymap_treeview(self):
        self.keymap_treeview = self.ui.get_object("keymap_treeview")
        self.keymap_treeview.set_model(Gtk.TreeStore(str))
        column = Gtk.TreeViewColumn("Layouts")
        self.keymap_treeview.append_column(column)
        cell = Gtk.CellRendererText()
        column.pack_start(cell, False)
        column.add_attribute(cell, "text", 0)

    def clear(self):
        """ Clears treeview model """
        tree_store = self.keymap_treeview.get_model()
        if tree_store:
            tree_store.clear()

        self.keyboard_layout = { 'code': None, 'description': None }
        self.keyboard_variant  = { 'code': None, 'description': None }

    def translate_ui(self):
        """ Translates all ui elements """
        self.header.set_subtitle(_("Select Your Keyboard Layout"))

        lbl = self.ui.get_object("label_layouts")
        if lbl:
            lbl.set_markup(
                _("Choose your keyboard layout and variant (if applies).\n"
                "For instance, the default Slovak variant is qwertz, but you\n"
                "can manually specify qwerty, etc.\n\n"
                "You can use the entry below the keyboard to test your\n"
                "layout selection."))

    def prepare(self, direction):
        self.translate_ui()

        if self.keyboard_layout['code'] is None:
            country_code =  self.settings.get("country_code")
            self.clear()

            self.populate_keymap_treeview()
            self.forward_button.set_sensitive(False)

            self.keyboard_layout['code'] = country_code
            description = self.kbd_names.get_layout_description(country_code)
            if description:
                self.keyboard_layout['description'] = description

                # specific variant cases
                country_name = self.settings.get("country_name")
                language_name = self.settings.get("language_name")
                language_code = self.settings.get("language_code")
                if country_name == "Spain" and language_name == "Catalan":
                    self.keyboard_variant['code'] = "cat"
                    self.keyboard_variant['description'] = self.kbd_names.get_variant_description(country_code, "cat")
                elif country_name == "Canada" and language_name == "English":
                    self.keyboard_variant['code'] = "eng"
                    self.keyboard_variant['description'] = self.kbd_names.get_variant_description(country_code, "eng")

                self.select_in_treeview(
                    self.keymap_treeview,
                    self.keyboard_layout['description'],
                    self.keyboard_variant['description'])
            else:
                logging.debug(
                    _("Can't match a keymap for country code '%s'"),
                    country_code)
                self.keyboard_layout = { 'code': None, 'description': None }
                self.keyboard_variant  = { 'code': None, 'description': None }

        self.prepare_called = True
        self.show_all()

    def populate_keymap_treeview(self):
        # Clear our model
        tree_store = self.keymap_treeview.get_model()
        tree_store.clear()

        # Block signal
        self.keymap_treeview.handler_block_by_func(self.on_keymap_cursor_changed)

        # Populate keymap treeview
        layouts = self.kbd_names.get_layouts()
        for layout_name in layouts:
            layout = layouts[layout_name]
            parent_iter = tree_store.insert_before(None, None)
            tree_store.set_value(parent_iter, 0, str(layout))
            for variant_name in layout.variants:
                variant = layout.variants[variant_name]
                child_iter = tree_store.insert_before(parent_iter, None)
                tree_store.set_value(child_iter, 0, str(variant))

        # Unblock signal
        self.keymap_treeview.handler_unblock_by_func(self.on_keymap_cursor_changed)

    def select_in_treeview(self, treeview, value0, value1=None):
        """ Simulates the selection of a value in the treeview """
        tree_model = treeview.get_model()
        tree_iter = tree_model.get_iter(0)
        found = False
        path = None

        while tree_iter and not found:
            if tree_model[tree_iter][0] == value0:
                path = tree_model.get_path(tree_iter)
                treeview.expand_row(path, False)
                found = True
            else:
                tree_iter = tree_model.iter_next(tree_iter)

        if not found:
            logging.warning(_("Can't find value '%s' in treeview"), value0)
            return

        if value1 and tree_iter and tree_model.iter_has_child(tree_iter):
            found = False
            tree_iter = tree_model.get_iter(path)
            child_iter = tree_model.iter_children(tree_iter)
            while child_iter and not found:
                if str(tree_model[child_iter][0]) == str(value1):
                    path = tree_model.get_path(child_iter)
                    found = True
                else:
                    child_iter = tree_model.iter_next(child_iter)
            if not found:
                logging.warning(_("Can't find value '%s' in treeview"), value1)

        if path:
            treeview.set_cursor(path)
            GLib.idle_add(self.scroll_to_cell, treeview, path)

    @staticmethod
    def scroll_to_cell(treeview, path):
        treeview.scroll_to_cell(path)
        return False

    def get_selected_in_treeview(self, treeview):
        """ Gets selected value in treeview """
        layout = None
        variant = None
        tree_model = treeview.get_model()
        selected = treeview.get_selection()
        if selected:
            (ls, iterator) = selected.get_selected()
            if iterator:
                layout = ls.get_value(iterator, 0)
                iter_parent = tree_model.iter_parent(iterator)
                if iter_parent:
                    # A variant was selected
                    variant = layout
                    layout = tree_model[iter_parent][0]

        return (layout, variant)

    def on_keymap_cursor_changed(self, widget):
        """ Called when selection changes """
        self.forward_button.set_sensitive(True)
        self.store_values()
        self.set_keyboard_widget_keymap()

    def store_values(self):
        """ Store selected values """

        self.keyboard_layout  = { 'code': None, 'description': None }
        self.keyboard_variant  = { 'code': None, 'description': None }

        # Read selected value from treeview
        (layout_description, variant_description) = self.get_selected_in_treeview(self.keymap_treeview)

        if not layout_description:
            return

        layout_name = self.kbd_names.get_layout_name_by_description(layout_description)

        if not layout_name:
            logging.warning(_("Unknown layout description %s"), layout_description)
            return

        self.keyboard_layout['code'] = layout_name
        self.keyboard_layout['description'] = layout_description

        if variant_description:
            variant_name = self.kbd_names.get_variant_name_by_description(variant_description)
            if variant_name:
                self.keyboard_variant['code'] = variant_name
                self.keyboard_variant['description'] = variant_description
            else:
                logging.warning(_("Unknown variant description %s"), variant_description)

        # This fixes issue 75: Won't pick/load the keyboard layout after selecting one (sticks to qwerty)
        if not self.testing and self.prepare_called:
            self.settings.set("keyboard_layout", self.keyboard_layout['code'])
            self.settings.set("keyboard_variant", self.keyboard_variant['code'])

            if self.keyboard_variant['code'] is None:
                txt = _("Set keyboard to layout name '{0}' ({1})").format(
                    self.keyboard_layout['description'],
                    self.keyboard_layout['code'])
            else:
                txt = _("Set keyboard to layout name '{0}' ({1}) and variant name '{2}' ({3})").format(
                    self.keyboard_layout['description'],
                    self.keyboard_layout['code'],
                    self.keyboard_variant['description'],
                    self.keyboard_variant['code'])
            logging.debug(txt)
            self.set_keymap()
        return True

    def set_keymap(self):
        """ Uses selected keymap """
        if self.keyboard_layout['code']:
            cmd = ['setxkbmap', '-layout', self.keyboard_layout['code']]

            if self.keyboard_variant['code']:
                cmd.extend(["-variant", self.keyboard_variant['code']])

            try:
                subprocess.check_call(cmd)
            except subprocess.CalledProcessError as process_error:
                logging.warning(process_error)

    def set_keyboard_widget_keymap(self):
        """ Pass current keyboard layout to the keyboard widget. """
        self.keyboard_widget.set_layout(self.keyboard_layout['code'])
        self.keyboard_widget.set_variant(self.keyboard_variant['code'])
        self.keyboard_widget.show_all()

# When testing, no _() is available
try:
    _("")
except NameError as err:
    def _(message):
        return message

if __name__ == '__main__':
    from test_screen import _, run

    run('Keymap')
