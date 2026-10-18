import privacy from "../../../docs/legal/privacy.md?raw";
import terms from "../../../docs/legal/terms.md?raw";
import refund from "../../../docs/legal/refund.md?raw";
import cookies from "../../../docs/legal/cookies.md?raw";
import notices from "../../../docs/legal/NOTICES.md?raw";
import thirdParty from "../../../docs/legal/THIRD_PARTY_SDKS.md?raw";

export type LegalDocId =
  | "privacy"
  | "terms"
  | "refund"
  | "cookies"
  | "notices"
  | "third-party";

export const LEGAL_DOCS: Record<
  LegalDocId,
  { title: string; markdown: string }
> = {
  privacy: { title: "Privacy policy", markdown: privacy },
  terms: { title: "Terms of service", markdown: terms },
  refund: { title: "Refund policy", markdown: refund },
  cookies: { title: "Cookie policy", markdown: cookies },
  notices: { title: "Notices (fonts & images)", markdown: notices },
  "third-party": { title: "Third-party SDKs", markdown: thirdParty },
};

export const LEGAL_NAV: { id: LegalDocId; label: string }[] = [
  { id: "privacy", label: "Privacy" },
  { id: "terms", label: "Terms" },
  { id: "refund", label: "Refunds" },
  { id: "cookies", label: "Cookies" },
  { id: "notices", label: "Notices" },
  { id: "third-party", label: "Third parties" },
];
