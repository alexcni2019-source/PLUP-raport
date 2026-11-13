import unittest,tempfile,json,sqlite3
from pathlib import Path
from unittest.mock import patch
from server import app,data_admin
class AdminTests(unittest.TestCase):
 def test_backup_restore_merge_and_stale_preview(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(app,'DB_PATH',Path(folder)/'db.sqlite3'):
   conn=app.database()
   row={**dict.fromkeys(app.PLAN_FIELDS,''),'material':'AL','client':'SBT','product':'1X240'}
   payload=json.dumps({'mode':'plan','date':'2026-10-14','week':'W42','incoming':'','rows':[row]})
   conn.execute('INSERT INTO reports VALUES (?,?,?,?,?)',('first','plan','2026-10-14','now',payload));conn.commit()
   backup=data_admin.snapshot(conn);data_admin.validate(backup,app.validate_report);review=data_admin.preview(conn,backup)
   self.assertEqual(review['duplicates'],1)
   result=data_admin.restore(conn,backup,'merge',review['expected'],app.DB_PATH);self.assertEqual(result['added'],0)
   self.assertTrue(list((Path(folder)/'backups').glob('*.sqlite3')))
   conn.execute('DELETE FROM reports');conn.commit()
   with self.assertRaises(ValueError):data_admin.restore(conn,backup,'restore',review['expected'],app.DB_PATH)
   self.assertEqual(conn.execute('SELECT count(*) FROM reports').fetchone()[0],0)
   review=data_admin.preview(conn,backup);data_admin.restore(conn,backup,'restore',review['expected'],app.DB_PATH)
   self.assertEqual(conn.execute('SELECT count(*) FROM reports').fetchone()[0],1)
   self.assertTrue(data_admin.sqlite_bytes(conn).startswith(b'SQLite format 3'))
   self.assertTrue(data_admin.csv_bytes(conn).startswith(b'PK'))
   backup['tables']['reports'][0]['payload']='{}'
   with self.assertRaises(ValueError):data_admin.validate(backup,app.validate_report)
   conn.close()
