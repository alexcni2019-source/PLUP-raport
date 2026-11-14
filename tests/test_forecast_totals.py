from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from PIL import ImageDraw

from server import app
from server.corporate import forecast_image, plan_image
from server.forecast_totals import aligned_tonnage, tonnage_column
from server.forecast_order import source_rows


def forecast_fixture():
    headings = ['', 'PRODUS', 'KM', 'TONE', 'CLIENT', 'STADIU', 'Prioritate']
    rows = [
        headings,
        ['AL:', 'CABLU A', '4', '1,9', 'Client A', 'SCH 2', 'URGENT'],
        ['', 'CABLU B', '5,5', '5,2', 'Client B', 'SCH 1', 'normal'],
        ['', 'TOTAL AL', '19 TONE', '', '', '', ''],
        ['CU:', 'CABLU C', '22', '0,25', 'Client C', '', 'normal'],
        ['', 'TOTAL CU', '22', '0,25', '', '', ''],
        ['', 'TOTAL AL + CU', '9.55 TONE', '', '', '', ''],
    ]
    records = [{'row': i, 'material': 'CU' if i == 4 else 'AL'} for i in (1, 2, 4)]
    columns = {'material': 0, 'product': 1, 'km': 2, 'tons': 3, 'client': 4, 'status': 5, 'priority': 6}
    table = {'version': 1, 'header': 0, 'date': '2026-11-13', 'rows': rows,
             'columns': columns, 'records': records}
    details = [
        {'material': rec['material'], 'measure': '', 'notes': '',
         **{key: rows[rec['row']][columns[key]] for key in ('product','km','tons','client','status','priority')}}
        for rec in records
    ]
    return {'mode': 'forecast', 'date': table['date'], 'rows': details, 'sourceTable': table}


class ForecastTotalsTests(TestCase):
    def test_legacy_subtotals_match_details_and_do_not_change_input(self):
        raw = forecast_fixture()
        before = deepcopy(raw)
        table = raw['sourceTable']
        rows = aligned_tonnage(source_rows(table), table, tonnage_column(table, table['rows'][0]))
        self.assertEqual(rows[3][2:4], ['', '7,1'])
        self.assertEqual(rows[5][2:4], ['22', '0,25'])
        self.assertEqual(rows[6][2:4], ['', '7,35'])
        self.assertEqual(raw, before)

    def test_missing_totals_are_added_with_grand_total_last_and_blank_tons_preserved(self):
        table = forecast_fixture()['sourceTable']
        table['rows'].pop()
        table['rows'][1][3] = ''
        table['rows'][2][3] = ''
        table['rows'][3] = ['', 'TOTAL AL']
        rows = aligned_tonnage(table['rows'], table, 3)
        self.assertEqual(rows[3], ['', 'TOTAL AL', '', ''])
        self.assertEqual(rows[-1], ['', 'TOTAL AL + CU', '', '0,25'])
        self.assertEqual(rows[-2][1], 'TOTAL CU')

    def test_forecast_amounts_share_one_column_and_png_tables_have_no_vertical_lines(self):
        original_text = ImageDraw.ImageDraw.text
        original_line = ImageDraw.ImageDraw.line
        captions, vertical = [], []

        def text(draw, xy, value, *args, **kwargs):
            if value in {'1,9', '5,2', '7,1', '0,25', '7,35'}:
                anchor = kwargs.get('anchor')
                width = draw.textlength(value, font=kwargs['font'])
                captions.append((value, xy[0] if anchor == 'mm' else xy[0] + width / 2))
            return original_text(draw, xy, value, *args, **kwargs)

        def line(draw, xy, *args, **kwargs):
            if len(xy) == 4 and xy[0] == xy[2] and abs(xy[1] - xy[3]) >= 30:
                vertical.append(tuple(xy))
            return original_line(draw, xy, *args, **kwargs)

        raw = forecast_fixture()
        plan = {'mode': 'plan', 'date': raw['date'], 'week': 'W47', 'incoming': '',
                'rows': [{**dict.fromkeys(app.PLAN_FIELDS, ''), 'material':'AL', 'product':'CABLU TEST'}]}
        with patch.object(ImageDraw.ImageDraw, 'text', text), patch.object(ImageDraw.ImageDraw, 'line', line):
            for theme in ('light', 'dark'):
                for show_status in (True, False):
                    captions.clear()
                    forecast_image(app.process_forecast(raw), theme, show_status, 'table')
                    self.assertEqual(set(value for value, _ in captions), {'1,9','5,2','7,1','0,25','7,35'})
                    self.assertLess(max(x for _, x in captions) - min(x for _, x in captions), 0.1)
                captions.clear()
                forecast_image(app.process_forecast({k:v for k,v in raw.items() if k != 'sourceTable'}), theme, True, 'table')
                self.assertEqual(set(value for value, _ in captions), {'1,9','5,2','7,1','0,25','7,35'})
                self.assertLess(max(x for _, x in captions) - min(x for _, x in captions), 0.1)
                plan_image(app.process_plan(plan), theme, section='table')
        self.assertEqual(vertical, [])
