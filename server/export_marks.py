"""Shared export colors and the forecast urgency badge."""
import re
from server.render import font

NUMBER = re.compile(r'[-+−]?\d+(?:[.,]\d+)?(?:\s*(?:t|tone|km|%))?', re.I)


def numeric(value):
    return NUMBER.fullmatch(str(value).strip()) is not None


def urgent(value):
    return str(value or '').strip().casefold() == 'urgent'


def warning(draw, center, palette, size):
    x, y = center
    radius = max(7, round(size * .45))
    draw.polygon([(x, y - radius), (x + radius, y + radius), (x - radius, y + radius)], fill=palette['alert'])
    draw.line((x, y - radius // 3, x, y + radius // 3), fill=palette['alert_bg'], width=max(1, radius // 4))
    dot = max(1, radius // 9)
    draw.ellipse((x - dot, y + radius // 2, x + dot, y + radius // 2 + 2 * dot), fill=palette['alert_bg'])


def urgent_width(draw, size):
    return draw.textlength('URGENT', font=font(size, True)) + 2 * max(7, round(size * .45)) + 36


def urgent_badge(draw, center, palette, size=24):
    x, y = center
    width = urgent_width(draw, size)
    radius = max(7, round(size * .45))
    left = x - width / 2
    draw.rounded_rectangle((left, y - size * .72, x + width / 2, y + size * .72),
                           radius=8, fill=palette['alert_bg'])
    warning(draw, (left + 12 + radius, y), palette, size)
    draw.text((left + 21 + radius * 2, y), 'URGENT', font=font(size, True), fill=palette['alert'], anchor='lm')
