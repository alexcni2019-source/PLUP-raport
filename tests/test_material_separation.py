import copy
import json
import unittest
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
from server import app, materials, plan_analysis
from server.forecast_clients import distribution
from server.corporate import forecast_image, plan_image


def payload(mode='plan', labels=True):
    rows=[['', 'Client', 'Produs', 'Tone', 'KM', 'Stoc M.F.']]
    if labels:rows.append(['', 'ALUMINIU (AL)'])
    al=len(rows);rows.append(['','ACELAȘI CLIENT','1X240','12','3','3'])
    rows.append(['TOTAL AL (TONE)','','','12'])
    if labels:rows.append(['', 'CUPRU (CU)'])
    cu=len(rows);rows.append(['','ACELAȘI CLIENT','1X240','5','2','2'])
    rows.append(['TOTAL CU (TONE)','','','5'])
    fields=app.PLAN_FIELDS if mode=='plan' else tuple(k for k in app.FORECAST_FIELDS if k!='material')
    data={'mode':mode,'date':'2026-11-11','rows':[]}
    for material,tons,km in [('AL','12','3'),('AL','5','2')]:
        row={**dict.fromkeys(fields,''),'material':material,'product':'1X240','client':'ACELAȘI CLIENT'}
        row.update({'planned':tons,'handed':'0','mf':km} if mode=='plan' else {'tons':tons,'km':km})
        data['rows'].append(row)
    columns={'client':1,'product':2,'planned' if mode=='plan' else 'tons':3}
    columns.update({'mf':5} if mode=='plan' else {'km':4})
    data['sourceTable']={'version':1,'header':0,'rows':rows,'columns':columns,'records':[{'row':al,'material':'AL'},{'row':cu,'material':'AL'}],'date':data['date']}
    if mode=='plan':data.update(week='W46',incoming='')
    return data


class MaterialSeparationTests(unittest.TestCase):
    def test_offset_section_headings_repair_stale_al_records(self):
        for mode in ['plan','forecast']:
            raw=payload(mode)
            original=copy.deepcopy(raw)
            result=app.validate_report(raw)
            self.assertEqual([r['material'] for r in result['rows']],['AL','CU'])
            self.assertEqual([r['material'] for r in result['sourceTable']['records']],['AL','CU'])
            self.assertEqual(raw,original, 'Reading/rendering must not rewrite archived input')
            key='planned' if mode=='plan' else 'tons'
            self.assertEqual(result['totals']['AL'][key],Decimal('12'))
            self.assertEqual(result['totals']['CU'][key],Decimal('5'))

    def test_material_subtotals_bound_unlabelled_sections(self):
        for mode in ['plan','forecast']:
            raw=payload(mode,False)
            self.assertEqual([r['material'] for r in app.validate_report(raw)['rows']],['AL','CU'])

    def test_missing_material_needs_choice_in_new_import(self):
        table={'header':0,'columns':{'product':0},'rows':[['Produs'],['CUPRU_CLIENT 1X240']], 'records':[{'row':1,'material':'AL'}]}
        self.assertIsNone(materials.classify(table,False)[1])
        self.assertEqual(materials.classify(table)[1],'AL')
        self.assertIsNone(materials.marker('CLIENT CU'))
        self.assertIsNone(materials.marker('CABLU CU 3X240'))

    def test_conflicting_explicit_section_and_subtotal_require_review(self):
        raw=payload()
        raw['sourceTable']['rows'][1]=['','CUPRU (CU)']
        with self.assertRaisesRegex(ValueError,'contrazice'):
            app.process_plan(raw)

    def test_same_client_stages_and_metal_densities_stay_separate(self):
        raw=payload();result=plan_analysis.build(app.process_plan(raw),raw)
        al,cu=result['by_material']['AL'],result['by_material']['CU']
        self.assertEqual(al['clients'][0]['tons'],Decimal('12'))
        self.assertEqual(cu['clients'][0]['tons'],Decimal('5'))
        self.assertEqual(next(r['current'] for r in al['stages'] if r['key']=='mf'),Decimal('3'))
        self.assertEqual(next(r['current'] for r in cu['stages'] if r['key']=='mf'),Decimal('2'))
        self.assertEqual(al['client_flow'][0]['stages'][0]['tons'],Decimal('1.80792'))
        self.assertEqual(cu['client_flow'][0]['stages'][0]['tons'],Decimal('3.97296'))

    def test_scoped_remaining_edit_does_not_change_other_material(self):
        raw=payload();raw['remainingOverrides']={'CU::ACELAȘI CLIENT':'4.2'}
        result=plan_analysis.build(app.process_plan(raw),raw)
        self.assertEqual(result['by_material']['AL']['clients'][0]['tons'],12)
        self.assertEqual(result['by_material']['CU']['clients'][0]['tons'],Decimal('4.2'))
        self.assertEqual(result['remaining_total'],Decimal('16.2'))

    def test_forecast_distributions_keep_shared_client_separate(self):
        forecast=app.process_forecast(payload('forecast'))
        clients,_=distribution(forecast)
        self.assertEqual({r['material']:r['tons'] for r in clients},{'AL':Decimal(12),'CU':Decimal(5)})
        self.assertTrue(all(r['materialPercent']==100 for r in clients))
        self.assertEqual(sum(r['percent'] for r in clients),100)

    def test_export_names_both_metals_in_light_and_dark(self):
        original=ImageDraw.ImageDraw.text
        for theme in ['light','dark']:
            captured=[]
            def capture(draw,xy,value,*args,**kwargs):
                captured.append(str(value));return original(draw,xy,value,*args,**kwargs)
            raw=payload();report=app.process_plan(raw)
            with patch.object(ImageDraw.ImageDraw,'text',capture):
                rendered=plan_image(report,theme,plan_analysis.build(report,raw),'summary')
                forecast_image(app.process_forecast(payload('forecast')),theme,False,'summary')
            self.assertTrue(any('ALUMINIU · AL' in value for value in captured))
            self.assertTrue(any('CUPRU · CU' in value for value in captured))
            self.assertTrue(any('CU · ACELAȘI CLIENT' in value for value in captured))
            self.assertTrue(any('5 t · 100% CU' in value for value in captured))
            self.assertGreater(Image.open(BytesIO(rendered)).height,500)
