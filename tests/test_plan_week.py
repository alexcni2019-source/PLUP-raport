import unittest
from server import source_table,app
class WeekTests(unittest.TestCase):
 def test_explicit_source_title_wins_over_stale_form(self):
  for title in ['13.10.2026 - PLAN WK 42','plan wk42','PLAN W42','Săptămâna 42']:
   t={'rows':[[title],['PRODUS'],['CABLU W39']],'header':1}
   self.assertEqual(source_table.plan_week(t,'W39'),'W42')
  self.assertEqual(source_table.plan_week({'rows':[['PRODUS'],['CABLU W42']],'header':0},'W39'),'W39')
 def test_ambiguous_invalid_titles_rejected(self):
  for text in ['WK39 WK42','WK54','WK00']:
   with self.assertRaises(ValueError):source_table.plan_week({'rows':[[text],['PRODUS']],'header':1},'W39')
 def test_history_payload_renders_correct_week_without_mutation(self):
  raw={'mode':'plan','date':'2026-10-13','week':'W39','incoming':'','rows':[],'sourceTable':{'version':1,'date':'2026-10-13','header':1,'rows':[['13.10.2026 PLAN WK42'],['PRODUS']],'columns':{'product':0},'records':[]}}
  report=app.process_plan(raw);self.assertEqual(report['week'],'W42');self.assertEqual(raw['week'],'W39')
