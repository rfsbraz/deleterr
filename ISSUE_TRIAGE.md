# Issue Triage and Labeling Plan

This document provides a comprehensive triage analysis of all open issues in the repository.

## Summary

- **Total Issues Analyzed**: 24
- **Bugs**: 2
- **Enhancements**: 21
- **Documentation**: 1

## Triage Details

### Bugs (2 issues)

| Issue | Title | Labels |
|-------|-------|--------|
| [#139](https://github.com/rfsbraz/deleterr/issues/139) | Issue deploying with Portainer. | bug |
| [#30](https://github.com/rfsbraz/deleterr/issues/30) | Library Tag Exclusion not working | bug |

### Enhancements (21 issues)

| Issue | Title | Labels |
|-------|-------|--------|
| [#116](https://github.com/rfsbraz/deleterr/issues/116) | Support for iMDB Lists | enhancement |
| [#115](https://github.com/rfsbraz/deleterr/issues/115) | Support for Radarr tags | enhancement |
| [#103](https://github.com/rfsbraz/deleterr/issues/103) | Add list exclusion support to Sonarr | enhancement |
| [#93](https://github.com/rfsbraz/deleterr/issues/93) | Streaming Platform Exclusion | enhancement |
| [#90](https://github.com/rfsbraz/deleterr/issues/90) | deprecate interactive mode | enhancement |
| [#64](https://github.com/rfsbraz/deleterr/issues/64) | ability to exclude shows that the current season hasnt ended yet and then delete whole season after x days | enhancement |
| [#60](https://github.com/rfsbraz/deleterr/issues/60) | Don't delete media if it is in a any of the users watchlist | enhancement |
| [#58](https://github.com/rfsbraz/deleterr/issues/58) | Ability to exclude shows that have not ended | enhancement |
| [#43](https://github.com/rfsbraz/deleterr/issues/43) | Add to Unraid Community Apps | enhancement |
| [#42](https://github.com/rfsbraz/deleterr/issues/42) | Archive, instead of delete? | enhancement |
| [#27](https://github.com/rfsbraz/deleterr/issues/27) | Trakt.tv Favorites List not being excluded | enhancement |
| [#23](https://github.com/rfsbraz/deleterr/issues/23) | Support matching based on resolution/bitrate/codec | enhancement |
| [#20](https://github.com/rfsbraz/deleterr/issues/20) | Add Jellyseerr support | enhancement |
| [#19](https://github.com/rfsbraz/deleterr/issues/19) | Add Jellyfin support | enhancement |
| [#18](https://github.com/rfsbraz/deleterr/issues/18) | Add support for inclusion/exclusion modes | enhancement |
| [#15](https://github.com/rfsbraz/deleterr/issues/15) | Add support for Ombi | enhancement |
| [#14](https://github.com/rfsbraz/deleterr/issues/14) | More control over how shows are removed | enhancement |
| [#13](https://github.com/rfsbraz/deleterr/issues/13) | Support moving shows to an intermediate storage | enhancement |
| [#12](https://github.com/rfsbraz/deleterr/issues/12) | Leaving Plex soon notification support | enhancement |
| [#7](https://github.com/rfsbraz/deleterr/issues/7) | Add support for free space threshold setting | enhancement |
| [#6](https://github.com/rfsbraz/deleterr/issues/6) | Add Overseerr support | enhancement |

### Documentation (1 issue)

| Issue | Title | Labels |
|-------|-------|--------|
| [#91](https://github.com/rfsbraz/deleterr/issues/91) | Setup webpage with basic guides and templates | documentation |

## How to Apply Labels

### Option 1: Run the Automated Script

```bash
./apply-issue-labels.sh
```

This will automatically apply all labels to the issues using the GitHub CLI.

### Option 2: Manual Application via GitHub CLI

```bash
gh issue edit 139 --add-label "bug"
gh issue edit 116 --add-label "enhancement"
gh issue edit 115 --add-label "enhancement"
gh issue edit 103 --add-label "enhancement"
gh issue edit 93 --add-label "enhancement"
gh issue edit 91 --add-label "documentation"
gh issue edit 90 --add-label "enhancement"
gh issue edit 64 --add-label "enhancement"
gh issue edit 60 --add-label "enhancement"
gh issue edit 58 --add-label "enhancement"
gh issue edit 43 --add-label "enhancement"
gh issue edit 30 --add-label "bug"
gh issue edit 27 --add-label "enhancement"
gh issue edit 23 --add-label "enhancement"
gh issue edit 20 --add-label "enhancement"
gh issue edit 19 --add-label "enhancement"
gh issue edit 18 --add-label "enhancement"
gh issue edit 15 --add-label "enhancement"
gh issue edit 14 --add-label "enhancement"
gh issue edit 13 --add-label "enhancement"
gh issue edit 12 --add-label "enhancement"
gh issue edit 7 --add-label "enhancement"
gh issue edit 6 --add-label "enhancement"
```

## Triage Methodology

Issues were triaged based on the following criteria:

1. **Bug**: Issues reporting something that isn't working as intended (e.g., "not working", "issue", "error")
2. **Enhancement**: Feature requests and improvements (e.g., "support for", "add", "ability to")
3. **Documentation**: Issues related to guides, templates, or documentation

Note: Issue #42 already had the "enhancement" label applied, so it was not included in the labeling script.
