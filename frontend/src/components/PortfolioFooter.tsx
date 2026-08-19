const GITHUB_URL = 'https://github.com/starboy1101';
const LINKEDIN_URL = 'https://www.linkedin.com/in/omkar-mahabdi';

function ExternalArrow() {
  return (
    <svg className="external-icon" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M5 11 11 5M6 5h5v5" />
    </svg>
  );
}

export function PortfolioFooter() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="site-footer">
      <div className="footer-surface">
        <div className="footer-main">
          <div className="footer-intro">
            <span className="footer-eyebrow">Built with purpose</span>
            <p className="footer-title">Safe SQL, from a question to an answer.</p>
            <p className="footer-description">
              Model output remains untrusted until it passes the schema-aware SQL safety boundary.
            </p>
          </div>

          <div className="footer-follow">
            <p>Follow for more such projects</p>
            <nav className="portfolio-links" aria-label="Omkar Mahabdi social profiles">
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Omkar Mahabdi on GitHub (opens in a new tab)"
              >
                <span className="social-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <path d="M15 22v-3.9c.04-1-.35-1.96-1.05-2.66 3.5-.39 7.18-1.72 7.18-7.78A6.08 6.08 0 0 0 19.5 3.43 5.65 5.65 0 0 0 19.34.7S18.07.29 15 2.31a14.5 14.5 0 0 0-7 0C4.93.29 3.66.7 3.66.7a5.65 5.65 0 0 0-.16 2.73 6.08 6.08 0 0 0-1.63 4.25c0 6.05 3.68 7.38 7.18 7.78A3.75 3.75 0 0 0 8 18.1V22M8 19c-3 .92-3-1.5-4.2-2" />
                  </svg>
                </span>
                <span>GitHub</span>
                <ExternalArrow />
              </a>
              <a
                href={LINKEDIN_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Omkar Mahabdi on LinkedIn (opens in a new tab)"
              >
                <span className="social-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24">
                    <rect x="3" y="3" width="18" height="18" rx="4" />
                    <path d="M8 10v7M8 7.3v.01M12 17v-7m0 3.1c.7-1.3 4-1.4 4 1.5V17" />
                  </svg>
                </span>
                <span>LinkedIn</span>
                <ExternalArrow />
              </a>
            </nav>
          </div>
        </div>

        <div className="footer-meta">
          <p>&copy; {currentYear} Omkar Mahabdi. All rights reserved.</p>
          <a href="/openapi.json">OpenAPI specification</a>
        </div>
      </div>
    </footer>
  );
}
