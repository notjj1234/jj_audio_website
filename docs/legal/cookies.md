# Cookie policy

**Last updated:** 17 October 2026  
**Controller:** Orallo John James Dalton Alvarez · orallojohnjames@gmail.com · Japan  

This policy explains cookies and similar storage used by the **hosted website**. The **desktop** app does not set website cookies. This text is for a free demo and is not legal advice.

## Summary

We use a small set of **essential / functional** storage items so sign-in and preferences work. We do **not** ship advertising or analytics cookies in the current demo (see [Third-party SDKs](./THIRD_PARTY_SDKS.md)).

## What we set

| Name | Type | Essential? | Purpose | Duration |
|------|------|------------|---------|----------|
| `att_refresh` | HttpOnly cookie (`Secure` in production), path `/v1/auth` | Yes | Refresh a signed-in session | Configured `refresh_token_days` |
| `att_access_token` | `sessionStorage` (not a cookie) | Yes (functional) | Short-lived API bearer token | Until the tab/session ends |
| `att_cookie_ack` | `localStorage` | Preference | Remembers you acknowledged the cookie notice | Until you clear site data |
| Theme / UI keys | `localStorage` (when used) | Preference | Appearance | Until cleared |

## Consent

Essential auth storage is required for signed-in and demo-session features. The site banner explains this and records acknowledgment. We do not use “accept all” patterns for ads, because we do not run ads.

Preference storage (acknowledgment, theme) is optional for using core features; clearing it only resets those preferences.

## Managing storage

- Use your browser controls to clear cookies and site data for this origin.  
- Sign out clears the refresh cookie via the logout API.  
- Closing the tab clears `sessionStorage` access tokens.

## Changes

If we add non-essential trackers later, we will update this policy and the banner before enabling them.

## Contact

orallojohnjames@gmail.com
