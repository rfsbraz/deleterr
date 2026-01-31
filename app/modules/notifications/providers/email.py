# encoding: utf-8
"""Email notification provider via SMTP."""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from app import logger
from app.modules.notifications.base import BaseNotificationProvider
from app.modules.notifications.models import DeletedItem, RunResult

# Default template path
DEFAULT_TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "templates" / "leaving_soon.html"


class EmailProvider(BaseNotificationProvider):
    """Email notification provider with SMTP support and HTML templates."""

    @property
    def name(self) -> str:
        return "email"

    @property
    def enabled(self) -> bool:
        return bool(
            self.config.get("smtp_server")
            and self.config.get("from_address")
            and self.config.get("to_addresses")
        )

    def send(self, result: RunResult) -> bool:
        """Send notification email with run results."""
        if not self.enabled:
            return False

        try:
            subject = self.config.get("subject", "Deleterr Run Complete")
            if result.is_dry_run:
                subject = f"[DRY-RUN] {subject}"

            html_content = self._build_run_summary_html(result)
            plain_content = self._build_run_summary_text(result)

            return self._send_email(subject, html_content, plain_content)

        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

    def send_leaving_soon(
        self,
        items: list[DeletedItem],
        template_path: Optional[str] = None,
        subject: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> bool:
        """
        Send leaving soon notification email.

        Args:
            items: List of items scheduled for deletion
            template_path: Optional path to custom HTML template
            subject: Email subject (uses config default if not specified)
            context: Additional template context (e.g., overseerr_url, plex_url)

        Returns:
            True if email was sent successfully, False otherwise.
        """
        if not self.enabled:
            return False

        try:
            email_subject = subject or self.config.get(
                "subject", "Leaving Soon - Content scheduled for removal"
            )

            # Build template context
            template_context = self._build_leaving_soon_context(items, context or {})

            # Render HTML template
            html_content = self._render_leaving_soon_template(template_path, template_context)

            # Build plain text fallback
            plain_content = self._build_leaving_soon_text(items)

            return self._send_email(email_subject, html_content, plain_content)

        except Exception as e:
            logger.error(f"Email leaving soon notification failed: {e}")
            return False

    def test_connection(self) -> bool:
        """Test SMTP connection."""
        if not self.enabled:
            return False

        try:
            smtp = self._create_smtp_connection()
            smtp.quit()
            return True
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create and authenticate SMTP connection."""
        smtp_server = self.config.get("smtp_server")
        smtp_port = self.config.get("smtp_port", 587)
        use_tls = self.config.get("use_tls", True)
        use_ssl = self.config.get("use_ssl", False)
        username = self.config.get("smtp_username")
        password = self.config.get("smtp_password")

        context = ssl.create_default_context()

        if use_ssl:
            # Implicit SSL (typically port 465)
            smtp = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            # Plain or STARTTLS (typically port 587 or 25)
            smtp = smtplib.SMTP(smtp_server, smtp_port)
            if use_tls:
                smtp.starttls(context=context)

        if username and password:
            smtp.login(username, password)

        return smtp

    def _send_email(
        self,
        subject: str,
        html_content: str,
        plain_content: str,
    ) -> bool:
        """Send email with HTML and plain text content."""
        from_address = self.config.get("from_address")
        to_addresses = self.config.get("to_addresses", [])
        timeout = self.config.get("timeout", 30)

        if not to_addresses:
            logger.warning("No email recipients configured")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_address
        msg["To"] = ", ".join(to_addresses)

        # Attach plain text first (lower priority)
        part1 = MIMEText(plain_content, "plain", "utf-8")
        msg.attach(part1)

        # Attach HTML (higher priority)
        part2 = MIMEText(html_content, "html", "utf-8")
        msg.attach(part2)

        try:
            smtp = self._create_smtp_connection()
            smtp.sendmail(from_address, to_addresses, msg.as_string())
            smtp.quit()
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _build_run_summary_html(self, result: RunResult) -> str:
        """Build HTML content for run summary email."""
        title = self.build_title(result)
        summary = self.build_summary(result)

        html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 700px; margin: 0 auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: {'#3498DB' if result.is_dry_run else '#2ECC71'}; color: white; padding: 30px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 30px; }}
        .summary {{ font-size: 18px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 25px; }}
        .section-title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 2px solid #eee; }}
        .item {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        .item:last-child {{ border-bottom: none; }}
        .footer {{ background: #f9f9f9; padding: 20px; text-align: center; font-size: 12px; color: #999; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>
        <div class="content">
            <div class="summary">{summary}</div>
"""

        if result.deleted_movies:
            html += '<div class="section"><div class="section-title">🎬 Deleted Movies</div>'
            for item in result.deleted_movies[:10]:
                html += f'<div class="item">{item.format_title()} - {self.format_size(item.size_bytes)}</div>'
            if len(result.deleted_movies) > 10:
                html += f'<div class="item"><em>...and {len(result.deleted_movies) - 10} more</em></div>'
            html += '</div>'

        if result.deleted_shows:
            html += '<div class="section"><div class="section-title">📺 Deleted TV Shows</div>'
            for item in result.deleted_shows[:10]:
                html += f'<div class="item">{item.format_title()} - {self.format_size(item.size_bytes)}</div>'
            if len(result.deleted_shows) > 10:
                html += f'<div class="item"><em>...and {len(result.deleted_shows) - 10} more</em></div>'
            html += '</div>'

        if result.preview_items:
            html += '<div class="section"><div class="section-title">⏰ Next Scheduled Deletions</div>'
            for item in result.preview_items[:5]:
                html += f'<div class="item">{item.format_title()} - {self.format_size(item.size_bytes)}</div>'
            if len(result.preview_items) > 5:
                html += f'<div class="item"><em>...and {len(result.preview_items) - 5} more</em></div>'
            html += '</div>'

        html += """
        </div>
        <div class="footer">
            Powered by Deleterr
        </div>
    </div>
</body>
</html>"""

        return html

    def _build_run_summary_text(self, result: RunResult) -> str:
        """Build plain text content for run summary email."""
        lines = [self.build_title(result), "", self.build_summary(result), ""]

        if result.deleted_movies:
            lines.append("Deleted Movies:")
            for item in result.deleted_movies[:10]:
                lines.append(f"  - {item.format_title()} ({self.format_size(item.size_bytes)})")
            if len(result.deleted_movies) > 10:
                lines.append(f"  ...and {len(result.deleted_movies) - 10} more")
            lines.append("")

        if result.deleted_shows:
            lines.append("Deleted TV Shows:")
            for item in result.deleted_shows[:10]:
                lines.append(f"  - {item.format_title()} ({self.format_size(item.size_bytes)})")
            if len(result.deleted_shows) > 10:
                lines.append(f"  ...and {len(result.deleted_shows) - 10} more")
            lines.append("")

        if result.preview_items:
            lines.append("Next Scheduled Deletions:")
            for item in result.preview_items[:5]:
                lines.append(f"  - {item.format_title()} ({self.format_size(item.size_bytes)})")
            if len(result.preview_items) > 5:
                lines.append(f"  ...and {len(result.preview_items) - 5} more")

        return "\n".join(lines)

    def _build_leaving_soon_context(
        self,
        items: list[DeletedItem],
        extra_context: dict,
    ) -> dict:
        """Build template context for leaving soon notification."""
        movies = [item for item in items if item.media_type == "movie"]
        shows = [item for item in items if item.media_type == "show"]

        total_size = sum(item.size_bytes for item in items)

        context = {
            "movies": [
                {
                    "title": m.title,
                    "year": m.year,
                    "size": self.format_size(m.size_bytes),
                    "library": m.library_name,
                }
                for m in movies
            ],
            "shows": [
                {
                    "title": s.title,
                    "year": s.year,
                    "size": self.format_size(s.size_bytes),
                    "library": s.library_name,
                }
                for s in shows
            ],
            "total_count": len(items),
            "total_size": self.format_size(total_size),
            "movie_count": len(movies),
            "show_count": len(shows),
        }

        # Merge extra context (e.g., plex_url, overseerr_url)
        context.update(extra_context)

        return context

    def _render_leaving_soon_template(
        self,
        template_path: Optional[str],
        context: dict,
    ) -> str:
        """Render leaving soon HTML template with Jinja2."""
        try:
            from jinja2 import Template
        except ImportError:
            logger.warning("Jinja2 not installed, using plain text fallback")
            return self._build_leaving_soon_html_simple(context)

        # Determine template path
        if template_path:
            path = Path(template_path)
        else:
            path = DEFAULT_TEMPLATE_PATH

        if not path.exists():
            logger.warning(f"Template not found at {path}, using built-in template")
            return self._build_leaving_soon_html_simple(context)

        try:
            template_content = path.read_text(encoding="utf-8")
            template = Template(template_content)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template: {e}")
            return self._build_leaving_soon_html_simple(context)

    def _build_leaving_soon_html_simple(self, context: dict) -> str:
        """Build simple HTML content when Jinja2 is unavailable or template fails."""
        html = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 700px; margin: 0 auto; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .header { background: linear-gradient(135deg, #e74c3c, #c0392b); color: white; padding: 30px; text-align: center; }
        .header h1 { margin: 0; font-size: 28px; }
        .content { padding: 30px; }
        .warning { background: #fff3cd; border: 1px solid #ffc107; border-radius: 6px; padding: 20px; margin-bottom: 25px; }
        .section-title { font-size: 20px; font-weight: bold; color: #333; margin: 25px 0 15px 0; padding-bottom: 10px; border-bottom: 2px solid #e74c3c; }
        .item { padding: 10px; margin-bottom: 10px; background: #f9f9f9; border-radius: 4px; }
        .footer { background: #f9f9f9; padding: 20px; text-align: center; font-size: 12px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⏰ Leaving Soon</h1>
            <p>The following titles are scheduled for removal</p>
        </div>
        <div class="content">
            <div class="warning">
                <strong>⚠️ These titles will be removed soon</strong><br>
                The items below are scheduled for deletion on the next cleanup cycle.
                If you want to keep any of them, watch them before then!
            </div>
"""

        if context.get("movies"):
            html += '<div class="section-title">🎬 Movies</div>'
            for movie in context["movies"]:
                year = f" ({movie['year']})" if movie.get("year") else ""
                html += f'<div class="item">{movie["title"]}{year} - {movie["size"]}</div>'

        if context.get("shows"):
            html += '<div class="section-title">📺 TV Shows</div>'
            for show in context["shows"]:
                year = f" ({show['year']})" if show.get("year") else ""
                html += f'<div class="item">{show["title"]}{year} - {show["size"]}</div>'

        html += f"""
            <div style="margin-top: 20px; color: #666;">
                Total: {context.get('total_count', 0)} items, {context.get('total_size', '0 B')}
            </div>
        </div>
        <div class="footer">
            Powered by Deleterr
        </div>
    </div>
</body>
</html>"""

        return html

    def _build_leaving_soon_text(self, items: list[DeletedItem]) -> str:
        """Build plain text content for leaving soon email."""
        lines = [
            "Leaving Soon - Content scheduled for removal",
            "",
            "The following titles are scheduled for deletion on the next cleanup cycle.",
            "If you want to keep any of them, watch them before then!",
            "",
        ]

        movies = [item for item in items if item.media_type == "movie"]
        shows = [item for item in items if item.media_type == "show"]

        if movies:
            lines.append("Movies:")
            for m in movies:
                lines.append(f"  - {m.format_title()} ({self.format_size(m.size_bytes)})")
            lines.append("")

        if shows:
            lines.append("TV Shows:")
            for s in shows:
                lines.append(f"  - {s.format_title()} ({self.format_size(s.size_bytes)})")
            lines.append("")

        total_size = sum(item.size_bytes for item in items)
        lines.append(f"Total: {len(items)} items, {self.format_size(total_size)}")

        return "\n".join(lines)
