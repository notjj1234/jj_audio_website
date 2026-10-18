import { Link, useParams } from "react-router-dom";
import { LEGAL_DOCS, LEGAL_NAV, type LegalDocId } from "../legal/documents";
import { renderMarkdown } from "../legal/renderMarkdown";

function isDocId(value: string | undefined): value is LegalDocId {
  return Boolean(value && value in LEGAL_DOCS);
}

export function LegalPage() {
  const { docId } = useParams();
  const id: LegalDocId = isDocId(docId) ? docId : "privacy";
  const doc = LEGAL_DOCS[id];

  return (
    <div className="legal-page">
      <p className="legal-draft-banner">
        Demo software policies — not lawyer-reviewed. Questions:{" "}
        <a href="mailto:orallojohnjames@gmail.com">orallojohnjames@gmail.com</a>
      </p>
      <nav className="legal-nav" aria-label="Legal documents">
        {LEGAL_NAV.map((item) => (
          <Link
            key={item.id}
            to={`/legal/${item.id}`}
            className={item.id === id ? "active" : undefined}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <article className="legal-article">{renderMarkdown(doc.markdown)}</article>
    </div>
  );
}
