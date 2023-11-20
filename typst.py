#!/usr/bin/env python3
# coding=utf-8
#
# Copyright (C) 2023 Jan Winkler
# based on pdflatex.py (C) by 2019 Marc Jeanmougin
#
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
#
"""
Compile typst code directly into and insert svg into document
"""

import os

import inkex
from inkex.base import TempDirMixin
from inkex.command import ProgramRunError, call
from inkex import load_svg, ShapeElement
from inkex.units import convert_unit
from inkex.localization import inkex_gettext as _
from copy import deepcopy


class TypstFormula(TempDirMixin, inkex.GenerateExtension):
    """
    Class for compilation of typst code into svg. Ensures proper setup
    of the generated svg for insertion into Inkscape.
    """

    def add_arguments(self, pars):
        pars.add_argument(
            "--typst_code",
            type=str,
            default=r"$ sum_(k=0)^n k = 1 + ... + n = (n(n+1)) / 2 $",
        )
        pars.add_argument("--font_size", type=int, default=10)
        pars.add_argument("--page", choices=["basic"])

    def generate(self):
        """Generator for a svg group holding the formula"""
        typst_file = os.path.join(self.tempdir, "input.typ")
        svg_file = os.path.join(self.tempdir, "output.svg")

        with open(typst_file, "w") as fhl:
            self.write_typst_code(fhl)

        try:
            call("typst", "compile", typst_file, svg_file)
        except ProgramRunError as err:
            inkex.errormsg(_("An exception occurred during typst compilation: ") + "\n")
            inkex.errormsg(err.stderr.decode("utf8").replace("\r\n", "\n"))
            raise inkex.AbortExtension()

        if not os.path.isfile(svg_file):
            inkex.errormsg(_("No svg has been produced by compilation: ") + "\n")
            inkex.errormsg(_(f"Expected file name was: {svg_file}."))
            raise inkex.AbortExtension()

        with open(svg_file, "r") as fhl:
            svg: inkex.SvgDocumentElement = load_svg(fhl).getroot()
            self.expand_defs(svg)
            scale = convert_unit("1pt", "px") / self.svg.scale
            for child in svg:
                if isinstance(child, ShapeElement):
                    # Scale node correctly and also ensure that it is placed
                    # in the center of the view
                    child.transform = (
                        inkex.Transform(scale=scale)
                        @ inkex.Transform(translate=-child.bounding_box().center)
                        @ child.transform
                    )
                    yield child

    def write_typst_code(self, stream):
        """Takes a formula and wraps it in typst"""
        stream.write(
            f"""#set page(margin: (x: 0pt, y: 0pt))
#set text({self.options.font_size}pt)
{self.options.typst_code}"""
        )
        stream.flush()

    def expand_defs(self, root):
        """Replaces references to glyph definitions by the content of the definition"""
        for child in root:
            if isinstance(child, inkex.Use):
                group = inkex.Group()
                for el in child.href:
                    group.append(deepcopy(el))
                group.transform = inkex.Transform(
                    translate=(float(child.get("x", "0")), float(child.get("y", "0")))
                )
                parent = child.getparent()
                parent.remove(child)
                parent.add(group)
                child = group  # required for recursive def
            self.expand_defs(child)


if __name__ == "__main__":
    TypstFormula().run()
