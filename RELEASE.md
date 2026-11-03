# Releasing a New Version of Hurricane

1. **Verify Checks & Build:**
   - Ensure all CI tests, linters, and type checks pass on `main`.
   - Update `version` in `pyproject.toml`.
   - Run `uv lock` to update `uv.lock`.
   - Verify distribution artifacts build cleanly:
     ```bash
     uv build
     ```

2. **Commit & Tag:**
   - Commit changes and tag the release:
     ```bash
     git add pyproject.toml uv.lock
     git commit -m "chore: bump version to 2.0.0"
     git tag 2.0.0
     git push origin main --tags
     ```

3. **Publish GitHub Release:**
   - Go to [GitHub Releases](https://github.com/django-hurricane/django-hurricane/releases) and click **"Draft a new release"**.
   - Choose the tag (e.g. `2.0.0`), set the title to `2.0.0`, add some content, and click **"Publish release"**.

4. **Automated Continuous Deployment (`.github/workflows/cd.yml`):**
   - Publishing the GitHub release triggers the CD workflow.
   - The workflow uses `uv build` to compile the wheel and sdist.
   - Publishes the package to PyPI via Trusted Publishing.
   - Signs distribution packages with Sigstore and attaches the signed artifacts to the GitHub release.
