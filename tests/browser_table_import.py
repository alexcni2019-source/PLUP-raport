"""Browser regression: a staged Excel table must never export the previous plan.

Run with Python Playwright and Chromium available:
    python tests/browser_table_import.py

Starts an isolated loopback HTTP server and temporary SQLite database. No live data.
"""
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['PLUP_AUTH_MODE'] = 'password'
from server import app
from playwright.sync_api import sync_playwright, expect

headers = ['', 'CLIENT', 'PRODUS', 'METAL PLANIFICAT ( TONE )',
           'METAL PREDAT ( TONE )', 'SARMA (TONE)', 'STOC LITA (TONE)',
           'STOC BARA RE /SE (KM)', 'STOC FUNIE (KM)', 'STOC VANE (KM)',
           'STOC CABLAT (KM)', 'STOC M.I. (KM)', 'STOC ARMAT(KM)',
           'STOC M.F. (KM)', 'KM PORNITI', 'KM PREDATI', 'REST DE PREDAT (KM)']
table = [['', '12.11.2026 - PLAN WK 47'], headers,
         ['AL:', 'CLIENT AL', 'PRODUS AL', '4.7', '', '', '', '4.8', '', '', '2.3'],
         ['CU:', 'CLIENT CU', 'PRODUS CU', '2.5', '', '0.4', '1.6']]
text = '\n'.join('\t'.join(row + [''] * (17 - len(row))) for row in table)

with TemporaryDirectory() as temporary:
    app.DB_PATH = Path(temporary) / 'isolated.sqlite3'
    app.PASSWORD = ''
    server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.wait_for_selector('.modern-shell')
            for width in (390, 1440):
                page.set_viewport_size({'width': width, 'height': 1000})
                for mode, suffix in [('weekday', 'report'), ('plan', 'plan'), ('forecast', 'forecast')]:
                    page.evaluate('(mode)=>PLUPDashboard.show(mode)', mode)
                    expect(page.locator('#excel-paste-' + suffix)).to_be_visible()
                    expect(page.locator('[data-read-table=' + suffix + ']')).to_be_visible()
                    assert page.locator('#excel-paste-' + suffix).evaluate('(e)=>!e.closest("details")')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.evaluate("""() => {
              PLUPDashboard.show('plan');
              PLUPPlan.load({mode:'plan',date:'2026-11-12',week:'W46',incoming:'',
                remainingOverrides:{'CU::CLIENT VECHI':'1.4'},remainingTotalOverride:'30.7',
                rows:[{material:'CU',client:'CLIENT VECHI',product:'PRODUS VECHI',
                       planned:'3.99',cable:'9.2'}]},null);
            }""")
            actions = page.locator('.modern-actions')
            generate = actions.get_by_role('button', name='Generează PNG', exact=True)
            save = actions.get_by_role('button', name='Salvează în istoric', exact=True)
            generate.click()
            page.wait_for_selector('#plan-images img')
            assert page.locator('#plan-images a[download]').count() >= 2
            writes = []
            page.on('request', lambda r: writes.append(r.url) if r.method in ('POST', 'PUT')
                    and ('/api/render?' in r.url or '/api/reports' in r.url) else None)

            # Editing the import must immediately withdraw stale PNG downloads.
            page.locator('#excel-paste-plan').fill(text)
            page.wait_for_function("() => PLUPTables.pending('plan')")
            assert page.locator('#plan-images img').count() == 0
            expect(generate).to_be_disabled()
            expect(save).to_be_disabled()
            assert 'Import neaplicat' in page.locator('.modern-save-badge').inner_text()
            page.locator('[data-read-table=plan]').click()
            page.wait_for_selector('[data-apply-table=plan]')
            assert page.locator('[data-map=bar]').input_value() == '7'
            page.evaluate("document.getElementById('image-plan').click()")
            page.evaluate("document.getElementById('save-plan').click()")
            assert not writes, writes
            assert page.evaluate('PLUPPlan.payload().week') == 'W46'

            # A read preview may not be applied after its textarea was modified.
            page.locator('#excel-paste-plan').fill(text + '\n')
            page.locator('[data-apply-table=plan]').click()
            assert 's-a schimbat' in page.locator('#excel-status-plan').inner_text()
            assert page.evaluate('PLUPPlan.payload().week') == 'W46'
            page.locator('[data-read-table=plan]').click()
            page.wait_for_selector('[data-apply-table=plan]')
            page.locator('[data-apply-table=plan]').click()
            page.wait_for_function("() => !PLUPTables.pending('plan')")
            payload = page.evaluate('PLUPPlan.payload()')
            assert payload['week'] == 'W47'
            assert [r['material'] for r in payload['rows']] == ['AL', 'CU']
            assert payload['rows'][1]['cable'] == ''
            assert payload['rows'][0]['bar'] == '4.8'
            assert payload['remainingOverrides'] == {} and payload['remainingTotalOverride'] == ''
            generate.click()
            page.wait_for_selector('#plan-images img')
            page.wait_for_function("() => !document.getElementById('image-plan').disabled")
            with page.expect_response(lambda r: '/api/reports' in r.url and r.request.method == 'POST') as saved:
                save.click()
            assert saved.value.status == 201
            result = page.evaluate("""async () => {
              const r=await PLUPFetch('/api/plan/analysis',{method:'POST',
                headers:{'Content-Type':'application/json'},body:JSON.stringify(PLUPPlan.payload())});
              return await r.json();
            }""")
            cu = result['by_material']['CU']
            assert next(s['current'] for s in cu['stages'] if s['key'] == 'cable') is None
            assert float(cu['ton_stocks']['wire']) == .4
            assert float(cu['ton_stocks']['spool']) == 1.6

            # Cancelling another pending import leaves the applied report intact.
            before = page.evaluate('PLUPPlan.payload()')
            page.locator('#excel-paste-plan').fill(text)
            expect(generate).to_be_disabled()
            page.locator('[data-discard-table=plan]').click()
            assert page.evaluate('PLUPPlan.payload()') == before
            expect(generate).to_be_enabled()
            # Edits to an applied source table also withdraw previously generated PNGs.
            generate.click()
            page.wait_for_selector('#plan-images img')
            page.locator('#source-editor-plan [data-source-row="3"][data-source-col="5"]').fill('0.5')
            assert page.locator('#plan-images img').count() == 0
            # An export already in flight cannot restore old images after a paste.
            held = []
            page.route('**/api/render?*', lambda route: held.append(route))
            generate.click()
            for _ in range(100):
                if held:
                    break
                page.wait_for_timeout(20)
            assert held
            page.locator('#excel-paste-plan').fill(text)
            held[0].continue_()
            page.wait_for_function("() => !document.getElementById('image-plan').disabled")
            assert page.locator('#plan-images img').count() == 0
            page.unroute('**/api/render?*')
            page.locator('[data-discard-table=plan]').click()
            assert not errors, errors
            print(json.dumps({'passed': 'Staged import, stale preview, AL/CU source fidelity, '
                              'PNG/save, cancellation and PNG invalidation', 'errors': errors}))
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
