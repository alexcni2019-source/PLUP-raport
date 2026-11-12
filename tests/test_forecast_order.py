import copy
import unittest
from unittest.mock import patch
from PIL import ImageDraw
from server import app
from server.corporate import forecast_image
from server.forecast_order import products, source_rows


def fixture():
    table = {
        'version': 1, 'header': 1, 'date': '2026-11-12',
        'columns': {'product': 1, 'tons': 2, 'order': 3, 'priority': 4},
        'rows': [['PREVIZ 12.11.2026'], ['', 'PRODUS', 'TONE', 'Ordine de execuție', 'Prioritate', 'Suplimentar'],
                 ['AL:', 'PRODUS CINCI', '1', '5', 'normal', 'NOTĂ CINCI'],
                 ['', 'PRODUS ZECE', '2', '10', 'normal', 'NOTĂ ZECE'],
                 ['', 'PRODUS DOI', '3', '2', 'urgent', 'NOTĂ DOI'],
                 ['', 'PRODUS UNU', '4', '1', 'urgent', 'NOTĂ UNU'],
                 ['', 'TOTAL AL', '10'],
                 ['CU:', 'PRODUS PATRU', '5', '4', 'urgent', 'NOTĂ PATRU'],
                 ['', 'PRODUS TREI', '6', '3', 'normal', 'NOTĂ TREI'],
                 ['', 'TOTAL CU', '11'], ['', 'TOTAL AL + CU', '21']],
        'records': [{'row': ri, 'material': 'AL' if ri < 6 else 'CU'} for ri in (2, 3, 4, 5, 7, 8)]
    }
    rows = [{**dict.fromkeys(app.FORECAST_FIELDS, ''), 'material': rec['material'],
             'product': table['rows'][rec['row']][1], 'tons': table['rows'][rec['row']][2],
             'order': table['rows'][rec['row']][3], 'priority': table['rows'][rec['row']][4]}
            for rec in table['records']]
    return {'mode': 'forecast', 'date': '2026-11-12', 'rows': rows, 'sourceTable': table}


class ForecastOrderTests(unittest.TestCase):
    def test_numeric_order_and_legacy_stability(self):
        rows = [{'order': '10'}, {'order': '2'}, {'order': '1'}]
        self.assertEqual([r['order'] for r in products(rows)], ['1', '2', '10'])
        legacy = [{'product': 'B'}, {'product': 'A'}]
        self.assertEqual(products(legacy), legacy)

    def test_source_sort_preserves_groups_subtotals_notes_and_input(self):
        raw = fixture(); before = copy.deepcopy(raw)
        output = source_rows(raw['sourceTable'])
        self.assertEqual([output[i][3] for i in (2, 3, 4, 5)], ['1', '2', '5', '10'])
        self.assertEqual([output[i][3] for i in (7, 8)], ['3', '4'])
        self.assertEqual(output[2][0], 'AL:'); self.assertEqual(output[7][0], 'CU:')
        self.assertEqual(output[4][0], ''); self.assertEqual(output[8][0], '')
        for ri in (0, 1, 6, 9, 10):
            self.assertEqual(output[ri], before['sourceTable']['rows'][ri])
        self.assertEqual(output[2][5], 'NOTĂ UNU')
        self.assertEqual(output[4][5], 'NOTĂ CINCI')
        self.assertEqual(raw, before)

    def test_explicit_material_column_and_legacy_unmapped_order_header(self):
        table = fixture()['sourceTable']; table['columns']['material'] = 0
        del table['columns']['order']
        output = source_rows(table)
        self.assertEqual(output[2][1], 'PRODUS UNU')
        self.assertEqual(output[7][1], 'PRODUS TREI')
        table['rows'][1][3] = 'Coloană necunoscută'
        self.assertEqual(source_rows(table), table['rows'])

    def test_source_and_standard_pngs_in_both_themes(self):
        expected = ['PRODUS UNU', 'PRODUS DOI', 'PRODUS CINCI', 'PRODUS ZECE', 'PRODUS TREI', 'PRODUS PATRU']
        original = ImageDraw.ImageDraw.text
        for source in (True, False):
            for theme in ('light', 'dark'):
                for show_status in (True, False):
                    raw = fixture()
                    if not source:
                        del raw['sourceTable']
                    before = copy.deepcopy(raw)
                    seen = []
                    def capture(draw, xy, value, *args, **kwargs):
                        if value in expected:
                            seen.append(value)
                        return original(draw, xy, value, *args, **kwargs)
                    with patch.object(ImageDraw.ImageDraw, 'text', capture):
                        png = forecast_image(app.process_forecast(raw), theme, show_status, 'table')
                    self.assertTrue(png.startswith(b'\x89PNG'))
                    self.assertEqual(seen, expected, (source, theme, show_status))
                    self.assertEqual(raw, before)

    def test_no_execution_order_does_not_reorder_source(self):
        table = fixture()['sourceTable']
        for rec in table['records']:
            table['rows'][rec['row']][3] = ''
        self.assertEqual(source_rows(table), table['rows'])

    def test_unmapped_client_text_is_not_moved_as_a_section_label(self):
        table = fixture()['sourceTable']
        table['rows'][1][0] = 'CLIENT'
        table['rows'][2][0] = 'AL'
        table['rows'][7][0] = 'CU'
        output = source_rows(table)
        self.assertEqual(output[2][0], '')
        self.assertEqual(output[4][0], 'AL')
        self.assertEqual(output[7][0], '')
        self.assertEqual(output[8][0], 'CU')


if __name__ == '__main__':
    unittest.main()
