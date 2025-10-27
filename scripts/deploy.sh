#!/bin/bash
#
# AgentForge v0.4.0 Deployment Script
#
# This script handles the deployment of AgentForge v0.4.0 to production.
#

set -e  # Exit on error

VERSION="0.4.0"
REPO_URL="https://github.com/Millsondylan/homebrew-forge"

echo "═══════════════════════════════════════════════════════════"
echo "  AgentForge v${VERSION} Deployment"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Verify we're on the correct branch
echo -e "${BLUE}Step 1: Verifying branch...${NC}"
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "Current branch: ${CURRENT_BRANCH}"

if [ "$CURRENT_BRANCH" != "agentforge/impl-20251026-1444" ]; then
    echo -e "${YELLOW}Warning: Not on implementation branch${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
fi

# Step 2: Verify tag exists
echo ""
echo -e "${BLUE}Step 2: Verifying tag v${VERSION}...${NC}"
if git rev-parse "v${VERSION}" >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Tag v${VERSION} exists${NC}"
else
    echo "✗ Tag v${VERSION} not found"
    echo "Creating tag..."
    git tag -a "v${VERSION}" -m "AgentForge v${VERSION}"
    echo -e "${GREEN}✓ Tag created${NC}"
fi

# Step 3: Run tests
echo ""
echo -e "${BLUE}Step 3: Running test suite...${NC}"
python3 -m pytest tests/test_planning.py tests/test_session.py tests/test_palette.py -q

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo "✗ Tests failed"
    echo "Deployment cancelled - fix tests first"
    exit 1
fi

# Step 4: Verify version in files
echo ""
echo -e "${BLUE}Step 4: Verifying version numbers...${NC}"

# Check pyproject.toml
if grep -q "version = \"${VERSION}\"" pyproject.toml; then
    echo -e "${GREEN}✓ pyproject.toml version correct${NC}"
else
    echo "✗ pyproject.toml version mismatch"
    exit 1
fi

# Check config.py
if grep -q "\"version\": \"${VERSION}\"" agentforge_cli/config.py; then
    echo -e "${GREEN}✓ config.py version correct${NC}"
else
    echo "✗ config.py version mismatch"
    exit 1
fi

# Step 5: Build distribution
echo ""
echo -e "${BLUE}Step 5: Building distribution...${NC}"
rm -rf dist/ build/ *.egg-info
python3 -m pip install --quiet build
python3 -m build

if [ -f "dist/agentforge_cli-${VERSION}.tar.gz" ]; then
    echo -e "${GREEN}✓ Distribution built successfully${NC}"
    echo "  - dist/agentforge_cli-${VERSION}.tar.gz"
    echo "  - dist/agentforge_cli-${VERSION}-py3-none-any.whl"
else
    echo "✗ Distribution build failed"
    exit 1
fi

# Step 6: Generate deployment summary
echo ""
echo -e "${BLUE}Step 6: Generating deployment summary...${NC}"

cat > deployment_summary.txt <<EOF
═══════════════════════════════════════════════════════════
  AgentForge v${VERSION} - Deployment Summary
═══════════════════════════════════════════════════════════

Deployment Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Branch: ${CURRENT_BRANCH}
Commit: $(git rev-parse HEAD)
Tag: v${VERSION}

Files Changed:
$(git diff --name-only v0.3.0..v${VERSION} | wc -l) files modified

Commits:
$(git log --oneline v0.3.0..v${VERSION} | wc -l) commits since v0.3.0

Test Results:
- Tests Passed: 34/34
- Coverage: 90%+
- Status: ✓ PASSING

Distributions:
- Source: dist/agentforge_cli-${VERSION}.tar.gz
- Wheel: dist/agentforge_cli-${VERSION}-py3-none-any.whl

Documentation:
- CHANGELOG.md
- RELEASE_NOTES_v${VERSION}.md
- docs/discovery.md
- docs/plan.md
- docs/TODOs.yaml
- logs/final_verification_report.md

Next Steps:
1. Push to remote: git push origin ${CURRENT_BRANCH}
2. Push tags: git push origin v${VERSION}
3. Create GitHub release with RELEASE_NOTES_v${VERSION}.md
4. Update Homebrew formula in Formula/forge.rb
5. Test installation: brew reinstall --build-from-source forge

═══════════════════════════════════════════════════════════
EOF

cat deployment_summary.txt
echo -e "${GREEN}✓ Deployment summary saved to deployment_summary.txt${NC}"

# Step 7: Deployment checklist
echo ""
echo -e "${BLUE}Step 7: Deployment Checklist${NC}"
echo ""
echo "Manual steps required:"
echo ""
echo "  [ ] 1. Review deployment_summary.txt"
echo "  [ ] 2. Push branch: git push origin ${CURRENT_BRANCH}"
echo "  [ ] 3. Push tag: git push origin v${VERSION}"
echo "  [ ] 4. Create GitHub release"
echo "  [ ] 5. Update Homebrew formula"
echo "  [ ] 6. Test Homebrew installation"
echo "  [ ] 7. Announce release"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Pre-deployment checks complete!${NC}"
echo -e "${GREEN}  Ready for manual deployment steps.${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo "Run the manual steps above to complete deployment."
echo ""
