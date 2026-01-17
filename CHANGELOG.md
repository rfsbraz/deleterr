# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ARM64 Docker image support for Raspberry Pi and Apple Silicon
- Better show matching with improved title comparison
- Security policy (SECURITY.md) with vulnerability reporting guidelines
- Contributing guidelines (CONTRIBUTING.md)

### Changed
- SSL verification is now configurable via `ssl_verify` setting (defaults to `true`)
- Pinned pytest-mock dependency to 3.14.1 for reproducible builds

### Fixed
- Wrong IDs used for item matching
- Wrong tag argument name in tag filtering
- Failing tests
- Prevent Trakt list retrieval from crashing the application
- Mutable default argument in `get_plex_item()` function
- Build process - install cargo and rust for dependencies

### Security
- SSL verification now enabled by default (was disabled)

## [0.9.0] - Previous Release

For changes prior to this changelog, please see the [GitHub Releases](https://github.com/rfsbraz/deleterr/releases) page.
