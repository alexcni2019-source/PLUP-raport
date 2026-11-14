"""Shared export formatting and forecast priority markers."""
import re

NUMBER = re.compile(r'[-+−]?\d+(?:[.,]\d+)?(?:\s*(?:t|tone|km|%))?', re.I)


def numeric(value):
    return NUMBER.fullmatch(str(value).strip()) is not None


def urgent(value):
    return str(value or '').strip().casefold() == 'urgent'


def priority_dot(draw, center, value, palette, radius):
    x, y = center
    color = palette['priority_urgent'] if urgent(value) else palette['priority_normal']
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
