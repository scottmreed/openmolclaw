"""Rendering tests."""
import pytest

from openmolclaw.chemistry.render import RenderError, molecule_svg_dimensions, render_molecule_svg


def test_render_returns_svg_with_dimensions():
    svg = render_molecule_svg("CCO", width=320, height=240)
    assert "<svg" in svg
    assert molecule_svg_dimensions(svg) == (320, 240)


def test_render_bad_smiles_raises():
    with pytest.raises(RenderError):
        render_molecule_svg("not-a-molecule!!")
