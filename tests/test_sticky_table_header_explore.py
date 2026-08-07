from features.sticky_table_header_explore.util import sticky_header_style


def test_sticky_header_style_contains_position_sticky():
    css = sticky_header_style()
    assert "position: sticky" in css
    assert "top: 0" in css
    assert ".dtable thead th" in css
