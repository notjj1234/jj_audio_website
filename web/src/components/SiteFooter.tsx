import { Link } from "react-router-dom";
import { LEGAL_PLACEHOLDERS } from "../legal/placeholders";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <p className="site-footer-biz">
        <strong>{LEGAL_PLACEHOLDERS.legalName}</strong>
        <span aria-hidden="true"> · </span>
        <a href={`mailto:${LEGAL_PLACEHOLDERS.contactEmail}`}>
          {LEGAL_PLACEHOLDERS.contactEmail}
        </a>
        <span aria-hidden="true"> · </span>
        {LEGAL_PLACEHOLDERS.jurisdiction}
      </p>
      <p className="site-footer-links">
        <Link to="/legal/privacy">Privacy</Link>
        <Link to="/legal/terms">Terms</Link>
        <Link to="/legal/refund">Refunds</Link>
        <Link to="/legal/cookies">Cookies</Link>
        <Link to="/legal/notices">Notices</Link>
        <Link to="/settings">Delete my data</Link>
      </p>
      <p className="hint">Demo product. No paid fees in this demo.</p>
    </footer>
  );
}
