# PETAdvice phone layout correction — 24 October 2026

Scope: existing PETAdvice UI, with iPhone 15 (393 × 852 portrait; 852 × 393 landscape),
smaller phones (320/375 px), a larger phone (430 px) and desktop (1280 px).
The browser available for this run was Chrome. These are responsive viewport checks,
not physical iPhone/Safari, software-keyboard, VoiceOver or full accessibility certification.
All account/pet/check data used for the signed-in checks lived in a disposable local database.

## Findings and changes

- The decorative circle painted over the beta notice. The notice now sits above that decoration.
- The fixed emergency banner overlapped mobile page content and could compete with a software keyboard.
  It now follows content on portrait and short landscape screens; its wording is unchanged.
  Desktop retains the fixed reminder.
- Form text was 13px. Text/date/select/search/account inputs now use 16px, with constrained widths,
  shrinkable grid columns and consistent control heights. Pinch zoom remains enabled.
- Added viewport safe-area coverage and inset spacing, small-viewport minimum height, and consistent
  text scaling across orientation changes. See [WebKit's viewport-unit explanation](https://webkit.org/blog/12445/new-webkit-features-in-safari-15-4/).
- Narrow headers, long pet names, headings, report cards and action buttons now fit without horizontal overflow.
  Removed the fixed 320px minimum body width that overflowed a small viewport with a scrollbar.

## Flow verification

| Step | Screen | Final status | Evidence |
| --- | --- | --- | --- |
| 1 | Home and beta notice | Clear, unobscured; warning does not cover page content | [Before](01-home-before.jpg), [after at same 375px width](03-home-after.jpg), [iPhone 15 size](13-home-iphone15-after.jpg) |
| 2 | Login and signup | Readable 16px inputs, visible actions; local signup completed | [Before](02-login-before.jpg), [after at same width](04-login-after.jpg) |
| 3 | Pet setup | Date/text/select controls contained; local profile created with date and long name | [Pet setup](05-pet-setup-393.jpg) |
| 4 | Symptom choices | Wrapping labels and enabled Continue action fit | [Symptom choices](06-symptoms-393.jpg) |
| 5 | Questions | Long prompts and answer labels fit; answers completed | [Question](07-question-393.jpg) |
| 6 | Urgency report | Long urgency heading, recorded context and report controls fit | [Result](08-result-393.jpg), [320px](result-320.jpg), [landscape](result-852.jpg) |
| 7 | Learn | Search field and expandable entries fit | [Learn](09-learn-393.jpg) |
| 8 | Care | Care text and complete warning fit | [Care](10-care-393.jpg) |
| 9 | Saved history | Local saved check retrieved and reopened | [History](11-history-393.jpg) |
| 10 | Account controls | Password field contained at 16px; controls fit | [Account](12-account-393.jpg) |
| 11 | Desktop regression | Header and report fit; fixed reminder retained | [Desktop](result-1280.jpg) |

Measured viewport results are recorded in [layout-checks.json](layout-checks.json):
no horizontal document overflow at any of the six final test sizes; all measured form
controls were contained and used 16px text. Tap targets retain at least 44px button heights.
Native iPhone focus zoom, date-picker rendering, safe-area values and keyboard behavior still
need an actual iPhone/Safari check; the CSS addresses the known layout conditions without
claiming those hardware checks were performed.

Validation: 14 frontend tests passed; frontend lint and TypeScript/Vite/PWA build passed.
The change is limited to frontend CSS and viewport metadata; no account data, schema,
authentication or clinical rules were changed for this correction.

## Release verification

Production build `dpl_HdSwyqvgVjSsGvzRsb5QZ2eGfJoK`, 42-second build, was staged and
checked before promotion. All referenced frontend assets returned 200, deployed CSS
matched the verified local build byte-for-byte, health/readiness returned 200, and
anonymous account access still returned 401. No environment variables, credentials,
database migrations or deployment protection settings were changed.

An existing browser installation initially rendered the old CSS and viewport metadata
from its PWA cache after promotion ([cached version](14-live-cached-before.jpg)). This
was a cache activation issue, while credential-free HTTP checks already served the new
assets. A fresh browser reload then showed the new CSS, safe-area viewport metadata, unobscured
notice and in-flow warning. Live login inputs measured 16px and remained contained at
393px. Testers should refresh the app, and if it still looks old close all PETAdvice
tabs or the saved app and reopen it; no account data needs to be deleted.

Final live captures: [home](15-live-home-after.jpg), [login](16-live-login-after.jpg).
