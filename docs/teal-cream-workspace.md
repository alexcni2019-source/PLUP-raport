# PLUP · Teal & Cream

The approved combination of Teal Signal, Cream & Citrus and Emerald Focus is the
application's single visual system. Source Sans 3, warm surfaces, teal navigation,
citrus selection, readable material groups and subtle depth replace the previous
corporate presentation. Light and dark appearances share the same structure.

## Implementation

`frontend/src/App.tsx` composes a real React interface with shadcn/Radix controls
and Lucide icons. It moves the existing working module views into a React host;
`bridge.ts` reads the existing controllers and delegates real save/export actions.
This incremental integration retains Excel/image import review, exact source cells,
drafts, history IDs, plan and forecast analysis, stock editing and undo.

`frontend/src/live.css` contains the approved tokens and responsive refinements.
Legacy theme tokens are mapped to the same palette, including dark appearance.
Plan and forecast retain their desktop tables and become product cards on mobile.
Pointer highlights require a fine pointer; reduced motion removes movement.
Dialogs and the mobile navigation support Escape, focus containment and return.

The bundled UI is committed in `web/modern/` because the production container runs
Python without Node. To reproduce the bundle:

```sh
npm --prefix frontend ci
npm run build:ui
```

The existing Python service serves the bundle and self-hosted Source Sans 3 fonts.
OFL license texts are included with both browser and report font files. HTML gets
a fresh style nonce for Radix's injected stylesheets. The CSP continues to require
self-hosted scripts and contains no unsafe-inline or unsafe-eval allowance.

`server/signature_render.py` renders the daily and three-day production reports
from the existing validated Decimal results, including AL/CU, backlog, waste,
processed quantities and full wrapped operational notes. Three-day reports retain
each day and Sunday operational indicators. The detailed plan/forecast/source-table
renderers retain their existing content and use the matching font and palette.

## Design review

Used the official [Impeccable skill](https://github.com/pbakaus/impeccable), version
4.8.2, source commit `b4bff1626c344067788c2679f048a20057c7cc5a`, engine 0.1.22.
Read its Operate, polish and craft-floor guidance, ran project context and one manual
detector pass, and inspected the actual running application. The local skill is
gitignored; no detector hooks were installed.

The static detector reported 42 findings against the fallback HTML and inherited
styles: small text, contrast, padding, a hidden eyebrow and old decorative effects.
It does not execute the React mount or account for the final stylesheet cascade.
Runtime checks and visual inspection were therefore used to assess the active UI.
They identified and corrected inherited dark-theme token precedence, material-label
contrast, search-icon spacing and download-button contrast. The approved metric
hierarchy and subtle pointer response are intentional design requirements.

## Validation

- Independent `npm ci`, TypeScript checking and production Vite build pass.
- All 86 Python tests pass, including material separation, import/source fidelity,
  client/stage calculations, forecast status visibility, history and private identity.
- Extended identity regression checks verify protected modern assets and fonts,
  fresh per-response style nonces, matching CSP and correct response byte lengths.
- Chromium with an isolated SQLite database: 28 browser checks cover real saves,
  failed-save retention, stable history IDs, invalid-input retention, daily/three-day
  exports, plan/forecast filtering, review confirmation, expanded fields, imported
  source cells, mobile navigation, dialog keyboard focus and reduced motion.
- All six modes fit 320, 390, 768, 1024 and 1440px widths in light and dark appearance.
- Separate Excel flows verify the same client/product under AL 12t and CU 5t remains
  separated through compute, plan stock/remaining edits, save and PNG generation.
  An unlabelled import requires an explicit material selection.
- Twelve runtime contrast checks of headings, actions, material labels and featured
  metrics exceed 4.5:1 across both themes. Actual light/dark PNG downloads succeed.
- No unexpected browser console errors. The intentional simulated save failure is
  asserted separately. Browser emulation does not substitute for physical devices.

No production database migration, identity-provider change or variable change is
part of this release. Deploy the existing private service from the tested commit.
