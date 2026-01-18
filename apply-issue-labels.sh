#!/bin/bash

# Script to apply labels to all triaged issues
# Requires GitHub CLI (gh) to be installed and authenticated

set -e

echo "Applying labels to triaged issues..."
echo

# Bugs
echo "Labeling bugs..."
gh issue edit 139 --add-label "bug" && echo "✓ #139: Issue deploying with Portainer." || echo "✗ Failed to label #139"
gh issue edit 30 --add-label "bug" && echo "✓ #30: Library Tag Exclusion not working" || echo "✗ Failed to label #30"

echo
echo "Labeling enhancements..."

# Enhancements
gh issue edit 116 --add-label "enhancement" && echo "✓ #116: Support for iMDB Lists" || echo "✗ Failed to label #116"
gh issue edit 115 --add-label "enhancement" && echo "✓ #115: Support for Radarr tags" || echo "✗ Failed to label #115"
gh issue edit 103 --add-label "enhancement" && echo "✓ #103: Add list exclusion support to Sonarr" || echo "✗ Failed to label #103"
gh issue edit 93 --add-label "enhancement" && echo "✓ #93: Streaming Platform Exclusion" || echo "✗ Failed to label #93"
gh issue edit 90 --add-label "enhancement" && echo "✓ #90: deprecate interactive mode" || echo "✗ Failed to label #90"
gh issue edit 64 --add-label "enhancement" && echo "✓ #64: ability to exclude shows that the current season hasnt ended yet..." || echo "✗ Failed to label #64"
gh issue edit 60 --add-label "enhancement" && echo "✓ #60: Don't delete media if it is in a any of the users watchlist" || echo "✗ Failed to label #60"
gh issue edit 58 --add-label "enhancement" && echo "✓ #58: Ability to exclude shows that have not ended" || echo "✗ Failed to label #58"
gh issue edit 43 --add-label "enhancement" && echo "✓ #43: Add to Unraid Community Apps" || echo "✗ Failed to label #43"
gh issue edit 27 --add-label "enhancement" && echo "✓ #27: Trakt.tv Favorites List not being excluded" || echo "✗ Failed to label #27"
gh issue edit 23 --add-label "enhancement" && echo "✓ #23: Support matching based on resolution/bitrate/codec" || echo "✗ Failed to label #23"
gh issue edit 20 --add-label "enhancement" && echo "✓ #20: Add Jellyseerr support" || echo "✗ Failed to label #20"
gh issue edit 19 --add-label "enhancement" && echo "✓ #19: Add Jellyfin support" || echo "✗ Failed to label #19"
gh issue edit 18 --add-label "enhancement" && echo "✓ #18: Add support for inclusion/exclusion modes" || echo "✗ Failed to label #18"
gh issue edit 15 --add-label "enhancement" && echo "✓ #15: Add support for Ombi" || echo "✗ Failed to label #15"
gh issue edit 14 --add-label "enhancement" && echo "✓ #14: More control over how shows are removed" || echo "✗ Failed to label #14"
gh issue edit 13 --add-label "enhancement" && echo "✓ #13: Support moving shows to an intermediate storage" || echo "✗ Failed to label #13"
gh issue edit 12 --add-label "enhancement" && echo "✓ #12: Leaving Plex soon notification support" || echo "✗ Failed to label #12"
gh issue edit 7 --add-label "enhancement" && echo "✓ #7: Add support for free space threshold setting" || echo "✗ Failed to label #7"
gh issue edit 6 --add-label "enhancement" && echo "✓ #6: Add Overseerr support" || echo "✗ Failed to label #6"

echo
echo "Labeling documentation..."

# Documentation
gh issue edit 91 --add-label "documentation" && echo "✓ #91: Setup webpage with basic guides and templates" || echo "✗ Failed to label #91"

echo
echo "Labeling complete!"
echo
echo "Summary:"
echo "- Bugs: 2 issues"
echo "- Enhancements: 21 issues"
echo "- Documentation: 1 issue"
echo "- Total: 24 issues labeled"
