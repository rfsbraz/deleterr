# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| edge    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via email to: rfsbraz@proton.me

When reporting a vulnerability, please include:

- Type of vulnerability (e.g., authentication bypass, injection, information disclosure)
- Full paths of source file(s) related to the vulnerability
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Potential impact of the vulnerability

## What to Expect

- **Initial Response**: We will acknowledge receipt of your vulnerability report within 48 hours.
- **Status Updates**: We will provide updates on the progress of addressing the vulnerability at least every 7 days.
- **Resolution**: Once the vulnerability is confirmed, we will work on a fix and coordinate disclosure with you.

## Security Best Practices for Users

When using Deleterr, please follow these security best practices:

1. **Protect your configuration file**: Your `settings.yaml` contains API keys for Plex, Radarr, Sonarr, and Tautulli. Ensure this file is not accessible to unauthorized users.

2. **Use environment variables**: Consider using environment variables for sensitive configuration values instead of hardcoding them in configuration files.

3. **Network security**: If running Deleterr in a networked environment, ensure your media server APIs are not exposed to the public internet without proper authentication.

4. **Keep updated**: Always use the latest version of Deleterr to ensure you have the most recent security patches.

5. **Review dry-run first**: Always test with `dry_run: true` before allowing Deleterr to make actual changes to your media library.

## Scope

This security policy applies to the Deleterr project maintained at https://github.com/rfsbraz/deleterr.

Third-party dependencies have their own security policies. Please report vulnerabilities in dependencies to their respective maintainers.
