"""Core functionality for figma2css."""

def extract_tokens(figma_data: dict) -> dict:
    """Extract design tokens from Figma data.

    Args:
        figma_data: The raw Figma file data as a dictionary.

    Returns:
        A dictionary of extracted tokens with 'colors' and optionally 'spacing' keys.
    """
    colors = {}
    seen_colors = set()
    color_index = 1

    spacing = {}
    seen_spacing = set()
    spacing_index = 1

    def _convert_rgb_to_hex(color_dict: dict) -> str:
        r = color_dict.get('r', 0)
        g = color_dict.get('g', 0)
        b = color_dict.get('b', 0)
        # Clamp and convert to 0-255
        r = max(0, min(1, r))
        g = max(0, min(1, g))
        b = max(0, min(1, b))
        return f'#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}'

    def _process_node(node: dict):
        nonlocal color_index, spacing_index
        # Process fills on this node
        fills = node.get('fills', [])
        for fill in fills:
            if fill.get('type') == 'SOLID':
                color = fill.get('color')
                if color:
                    hex_color = _convert_rgb_to_hex(color)
                    if hex_color not in seen_colors:
                        seen_colors.add(hex_color)
                        token_name = f'--color-{color_index}'
                        colors[token_name] = hex_color
                        color_index += 1
        # Process layout grids on this node
        grids = node.get('layoutGrids', [])
        for grid in grids:
            gutter_size = grid.get('gutterSize')
            if gutter_size is not None and gutter_size != 0:
                # Avoid duplicate spacing values
                if gutter_size not in seen_spacing:
                    seen_spacing.add(gutter_size)
                    # Figma reports gutterSize in pixels, so the token needs a
                    # unit -- a bare number is not a valid CSS length.
                    if isinstance(gutter_size, float) and gutter_size.is_integer():
                        token_value = f'{int(gutter_size)}px'
                    else:
                        token_value = f'{gutter_size}px'
                    token_name = f'--spacing-{spacing_index}'
                    spacing[token_name] = token_value
                    spacing_index += 1
        # Recurse into children
        children = node.get('children', [])
        for child in children:
            _process_node(child)

    document = figma_data.get('document')
    if document:
        _process_node(document)

    result = {}
    if colors:
        result['colors'] = colors
    if spacing:
        result['spacing'] = spacing
    return result


def tokens_to_css(tokens: dict) -> str:
    """Format tokens as CSS custom properties in :root.

    Args:
        tokens: A dictionary of tokens, e.g., {'colors': {'primary': '#fff'}}.
            A key that already looks like a custom property (starts with ``--``),
            as produced by :func:`extract_tokens`, is used verbatim rather than
            being prefixed again.

    Returns:
        A string containing :root { --key: value; ... }.
    """
    lines = []
    for category, subdict in tokens.items():
        for key, value in subdict.items():
            # Keys from extract_tokens are already full custom-property names.
            if key.startswith("--"):
                css_property = key
            else:
                css_property = f"--{category}-{key}"
            lines.append(f"{css_property}: {value};")
    if lines:
        return f":root {{ {' '.join(lines)} }}"
    return ":root {}"