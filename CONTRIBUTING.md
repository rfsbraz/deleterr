# Contributing to Deleterr

Thank you for your interest in contributing to Deleterr! This document provides guidelines and information for contributors.

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## How to Contribute

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

When creating a bug report, include:

- **Clear title**: Summarize the issue concisely
- **Steps to reproduce**: Detailed steps to reproduce the behavior
- **Expected behavior**: What you expected to happen
- **Actual behavior**: What actually happened
- **Environment**: OS, Python version, Docker version (if applicable)
- **Configuration**: Relevant parts of your `settings.yaml` (with sensitive data removed)
- **Logs**: Relevant log output (with sensitive data removed)

### Suggesting Features

Feature requests are welcome! Please:

1. Check existing issues/discussions for similar requests
2. Clearly describe the feature and its use case
3. Explain why this would benefit other users

### Pull Requests

1. **Fork the repository** and create your branch from `develop`
2. **Follow existing code style** - the project uses consistent patterns
3. **Add tests** if applicable
4. **Update documentation** for any changed functionality
5. **Ensure tests pass** before submitting

## Development Setup

### Prerequisites

- Python 3.9+
- Docker (optional, for containerized development)

### Local Development

1. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/deleterr.git
   cd deleterr
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. Copy the example configuration:
   ```bash
   cp config/settings.yaml.example config/settings.yaml
   ```

5. Run tests:
   ```bash
   pytest
   ```

### Docker Development

```bash
docker build -t deleterr:dev .
docker run -v $(pwd)/config:/config deleterr:dev
```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings for public functions and classes
- Keep functions focused and small

## Testing

- Write tests for new functionality
- Ensure existing tests pass
- Use `pytest` for running tests
- Test with `dry_run: true` before testing actual deletions

## Commit Messages

Use clear, descriptive commit messages:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test additions/changes
- `refactor:` for code refactoring
- `chore:` for maintenance tasks

Example: `feat: Add support for Radarr tags filtering`

## Branch Naming

- `feat/description` for features
- `fix/description` for bug fixes
- `docs/description` for documentation
- `refactor/description` for refactoring

## Review Process

1. All PRs require review before merging
2. Address review feedback promptly
3. Keep PRs focused and reasonably sized
4. Squash commits if requested

## Questions?

Feel free to open a discussion or issue if you have questions about contributing.

Thank you for helping improve Deleterr!
