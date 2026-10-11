"""Core functionality for figma2css."""

def extract_tokens(figma_data: dict) -> dict:
    """Extract design tokens from Figma data.

    Args:
        figma_data: The raw Figma file data as a dictionary.

    Returns:
        A dictionary of extracted tokens with a 'colors' key mapping token names to hex colors.
    """
    colors = {}
    seen_colors = set()
    index = 1

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
        nonlocal index
        # Process fills on this node
        fills = node.get('fills', [])
        for fill in fills:
            if fill.get('type') == 'SOLID':
                color = fill.get('color')
                if color:
                    hex_color = _convert_rgb_to_hex(color)
                    if hex_color not in seen_colors:
                        seen_colors.add(hex_color)
                        token_name = f'--color-{index}'
                        colors[token_name] = hex_color
                        index += 1
        # Recurse into children
        children = node.get('children', [])
        for child in children:
            _process_node(child)

    document = figma_data.get('document')
    if document:
        _process_node(document)

    return {'colors': colors} if colors else {}