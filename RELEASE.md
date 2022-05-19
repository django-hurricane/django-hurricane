# Releasing a new version of Hurricane

- accept all relevant pull requests/code changes into `main` branch
- ensure all actions ran successfully
- push a tag with the new version, currently we use [bump2version](https://github.com/c4urself/bump2version)
- hit "Draft a new release" on [GitHubs release page](https://github.com/django-hurricane/django-hurricane/releases)
- choose the new tag, set the tag version as the release title, auto-generate release notes and publish the release
- this triggers an action to publish the release to [pypi](https://pypi.org/project/django-hurricane/)
- update "Now available" link of [website](https://github.com/django-hurricane/django-hurricane.github.io/blob/main/index.md)