import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { COOKIE_ACK_KEY } from "../legal/placeholders";

export function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    try {
      setVisible(localStorage.getItem(COOKIE_ACK_KEY) !== "1");
    } catch {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  function acknowledge() {
    try {
      localStorage.setItem(COOKIE_ACK_KEY, "1");
    } catch {
      /* private mode */
    }
    setVisible(false);
  }

  return (
    <div className="cookie-banner" role="dialog" aria-label="Cookie notice">
      <p>
        We use an <strong>essential</strong> HttpOnly refresh cookie (
        <code>att_refresh</code>) for sign-in, plus a short-lived access token in{" "}
        <code>sessionStorage</code>. No advertising cookies in this demo.{" "}
        <Link to="/legal/cookies">Cookie policy</Link>
      </p>
      <button type="button" onClick={acknowledge}>
        OK
      </button>
    </div>
  );
}
