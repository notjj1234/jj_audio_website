# Privacy policy

**Last updated:** 17 October 2026  
**Operator / data controller:** Orallo John James Dalton Alvarez (individual), Japan  
**Contact:** orallojohnjames@gmail.com  

This policy describes how Audio Tools handles information when you use the hosted website or the desktop app. It is written for a free, unfinished demo. It is not legal advice and has not been reviewed by a lawyer.

## What Audio Tools is

- **Website:** FastAPI API + React app. You may sign in with an account or use an anonymous demo session when demo mode is enabled.
- **Desktop:** Streamlit app that runs on your computer. Audio processing stays on the device; the desktop app does not create a cloud account by default.

## Information we process

### Website

| Data | Purpose | Storage |
|------|---------|---------|
| Account email and password hash | Authentication | Database |
| Anonymous session label (`anon-…@session.demo`) | Demo identity | Database |
| Uploaded audio files | Isolation / Tab PDF jobs | Object storage (local disk or S3/MinIO) |
| Job settings, status, and error messages | Run and display jobs | Database |
| Job outputs (stems, PDF, MIDI, etc.) | Download results | Object storage |
| Refresh cookie `att_refresh` (HttpOnly) | Keep you signed in | Browser cookie (`/v1/auth`) |
| Access token | API calls | Browser `sessionStorage` (not a cookie) |
| Server logs | Operations and debugging | Host logs |

### Desktop

| Data | Purpose | Storage |
|------|---------|---------|
| Audio you select and separation outputs | Local processing | App data directory (`AUDIO_TOOLS_DATA_DIR` or default under the install) |
| UI preferences (theme, Lite/Pro) | Convenience | Local files |
| YouTube URLs you paste (optional) | Local download when that feature is used | Processed on your machine |

Desktop does not set the website auth cookie.

## Legal bases (where that language applies)

For a personal demo operated from Japan, we process the above information as needed to provide the features you request (account, jobs, downloads) and to keep the service secure and working. If you later require a different legal framing for a commercial launch, update this section with counsel.

## Cookies and similar tech

See the [Cookie policy](./cookies.md). Today we use essential auth storage only. No advertising or analytics cookies ship in this demo.

## How we share information

We do not sell personal data. We do not run ad networks in this demo. Hosting, database, or object-storage providers you (or the operator) configure may process data as infrastructure processors — see [Third-party SDKs](./THIRD_PARTY_SDKS.md). We may disclose information if required by law or to protect the service from abuse.

## Retention

- **Website:** kept until you delete your account/data, or the operator wipes the demo environment.
- **Desktop:** kept until you clear local run data in Settings or remove the data directory / uninstall.

## Your choices and requests

- **Website — access / deletion:** Settings → Delete my account & data, or email orallojohnjames@gmail.com.
- **Desktop — local files:** Settings → Clear local run data, or delete the data directory shown there.
- **Corrections / questions:** orallojohnjames@gmail.com.

We aim to respond to privacy emails in a reasonable time; there is no guaranteed SLA.

## Children

This demo is aimed at people evaluating audio tools, not at children as a primary audience. We do not knowingly solicit children’s data. If you think a child’s data was submitted, email orallojohnjames@gmail.com and we will delete it when we can identify it.

## International use

The operator is based in Japan. If you use the hosted demo from elsewhere, your information may be processed in the regions where the demo host and storage are deployed. Do not upload data you are not allowed to transfer.

## Security

We use ordinary measures for a small demo (hashed passwords, HttpOnly refresh cookie, access tokens). No method is perfect. Report suspected vulnerabilities to orallojohnjames@gmail.com as described in `SECURITY.md` — do not open a public issue for security reports.

## Changes

We may update this policy as the product changes. The “Last updated” date will change when we do. Continued use after a material update means you accept the revised policy for future use.

## Contact

Orallo John James Dalton Alvarez · orallojohnjames@gmail.com · Japan
