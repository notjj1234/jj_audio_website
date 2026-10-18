# Compliance checklist (C01–C20)

Demo baseline for Audio Tools (website + desktop). Not a lawyer sign-off.

| ID | Item | Status | Notes |
|----|------|--------|-------|
| C01 | Privacy policy | Done | `docs/legal/privacy.md` + in-app Legal pages |
| C02 | Terms of service | Done | `docs/legal/terms.md` |
| C03 | Refund policy | N/A-demo | `docs/legal/refund.md` — no paid product |
| C04 | Cookie policy | Done | `docs/legal/cookies.md` |
| C05 | Cookie consent banner | Done | Website acknowledgment banner |
| C06 | Check form consents | Done | Login: Terms/Privacy + age, unchecked by default |
| C07 | No unnecessary data | Done | Inventory in privacy.md; no new PII fields added |
| C08 | Audit third-party SDKs | Done | `docs/legal/THIRD_PARTY_SDKS.md` |
| C09 | Remove dark patterns | Done | No pre-ticked marketing; consent unchecked |
| C10 | Remove hidden fees | N/A-demo | Refund page: no fees |
| C11 | Remove fake reviews | N/A-demo | None present; do not add |
| C12 | Remove unsupported claims | Done | Softened login/demo copy; Tab PDF remains labeled demo |
| C13 | Accessibility alt text | Done | Brand/decorative handling; legal links labeled |
| C14 | Fix color contrast | Done | Stronger focus + footer/link contrast in touched CSS |
| C15 | Keyboard navigation | Done | Skip link + visible `:focus-visible` |
| C16 | Add business details | Done | Footer/Settings: Orallo John James Dalton Alvarez · Japan (no mailing address yet) |
| C17 | Age consent | N/A-demo | Operator declined a minimum-age gate; privacy has a light children note only |
| C18 | Unsubscribe in emails | Future | No marketing/transactional email sender yet |
| C19 | License fonts/images | Done | `docs/legal/NOTICES.md` (Satoshi ITF) |
| C20 | Data deletion request | Done | `DELETE /v1/auth/me` + Settings UI; Desktop clear local runs |

**Operator details filled:** Orallo John James Dalton Alvarez · orallojohnjames@gmail.com · Japan. Mailing address omitted. Age gate omitted. Policies expanded with standard demo boilerplate (2026-10-17). Still not a lawyer sign-off.
