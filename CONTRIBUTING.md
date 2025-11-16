# Contributing to MentoroAI

Thank you for your interest in contributing to **MentoroAI**.  
This document explains the contribution process, quality standards, and legal framework.

---

## Overview

MentoroAI is a public, open-source Django project.  
Contributions in the form of bug reports, improvements, documentation, or code are welcome.  
Please read this guide before submitting a pull request.

---

## Code of Conduct

We expect respectful and professional communication.  
Discrimination, personal attacks, or abusive language will not be tolerated.  
Constructive criticism is welcome and should include actionable suggestions.

---

## Development Environment

Minimum requirements:

- Python 3.12
- Django 5.x
- Node.js and npm (for frontend builds with TailwindCSS/DaisyUI)
- Git

Setup example:

```bash
git clone https://github.com/maikksmt/mentoro-ai.git
cd mentoroai
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install
python manage.py migrate
python manage.py runserver
```

Frontend development (optional):

```bash
npm run dev
```

---

## Code Quality & Style

- Python: Follow **PEP 8**, include type hints when possible
- Formatting: e.g. **black** and **ruff**
- Tests: Required for all new features and bug fixes
- Security: Never commit secrets or `.env` files
- Accessibility and performance should always be considered for templates and CSS changes

Commit message examples:

```
fix(compare): correct breadcrumbs
feat(starter): enable section editing in admin
```

---

## Branch Strategy & Pull Requests

- Main branches: `main` (stable) and `dev` (active)
- Create feature branches from `dev`: `feature/<short-description>`
- Open pull requests against `dev`
- Describe motivation, changes, and migration steps in PR description
- Link related issues

Review checklist:

- No regressions; all tests must pass
- Clean structure, meaningful commits, proper documentation
- External dependencies must be license-compatible

---

## Editorial Content Contributions

- Use clear, neutral, and precise language
- Always cite external sources and data
- Do not include copyrighted material without permission

---

## License & Contributor Agreement

MentoroAI is licensed under the **GNU General Public License v3 (or later)**.  
By submitting a pull request, you agree that your contribution will be released under GPLv3+.  
Ensure you hold the necessary rights to your work.

More details: see `LICENSE.txt`.

---

## Security Policy

- Report vulnerabilities privately to the maintainer
- Do not include secrets, API keys, or tokens in pull requests

---

## Contact

- Maintainer: Maik Kusmat
- Email: contact@mentoro-ai.com

---

## 🙏 Thank You

Your contribution helps make **MentoroAI** better  
and supports open access to reliable AI knowledge.

> _“Open knowledge for everyone who wants to learn and understand.”_
