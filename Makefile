# Makefile for MentoroAI
# -----------------------------------
# Usage:
#	see MentoroAI Makefile Cheatsheet

# ---------- i18n ----------
MANAGE ?= python manage.py
I18N_LANGS ?= de en
I18N_JS_EXT ?= js,jsx,ts,tsx

IGNORE := \
    -i "venv/**" \
    -i ".venv/**" \
    -i "node_modules/**" \
    -i "htmlcov/**" \
    -i "coverage/**" \
    -i "**/site-packages/**" \
    -i "**/*.html.py" \
    -i "**/*.txt.py" \
    -i "requirements*.txt"

.PHONY: makemessages makemessages-html makemessages-js compilemessages i18n-clean

makemessages: makemessages-html makemessages-js
	@echo "### makemessages (html + js) completed successfully."

# --- HTML / Templates (Domain: django) ---
makemessages-html:
	@for lang in $(I18N_LANGS); do \
		echo "### Extracting template strings for $$lang (domain=django)..."; \
		$(MANAGE) makemessages -l $$lang $(IGNORE); \
	done

# --- JavaScript / TypeScript (Domain: djangojs) ---
makemessages-js:
	@for lang in $(I18N_LANGS); do \
		echo "### Extracting JS strings for $$lang (domain=djangojs)..."; \
		$(MANAGE) makemessages -d djangojs -l $$lang \
			--extension=$(I18N_JS_EXT) \
			$(IGNORE); \
	done

compilemessages:
	$(MANAGE) compilemessages

i18n-clean:
	find locale -name "*.mo" -delete

# -----------------------------------
# Utility & Project Commands (MentoroAI)
# -----------------------------------

PY        ?= python
COVER     ?= coverage
NPM       ?= npm
MANAGE    ?= $(PY) manage.py

.PHONY: \
  check check-deploy showmigrations runserver \
  makemigrations migrate createsuperuser shell \
  test test-app pytest cov-html \
  lint format \
  collectstatic build-frontend \
  pip-compile pip-sync \
  pip-audit bandit security \
  predeploy

# --- Django Checks ---
check:
	$(MANAGE) check

check-deploy:
	$(MANAGE) check --deploy

showmigrations:
	$(MANAGE) showmigrations

# --- Dev Server ---
runserver:
	$(MANAGE) runserver 0.0.0.0:8000

# --- DB & Migrations ---
makemigrations:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

createsuperuser:
	$(MANAGE) createsuperuser

shell:
	$(MANAGE) shell

# --- Tests & Coverage ---
# Nutzt explizit .coveragerc und die Django-Settings mentoroai.settings
test:
	$(COVER) erase
	$(COVER) run --rcfile=.coveragerc -m django test --settings=mentoroai.settings -v 2
	$(COVER) combine
	$(COVER) report -m

# Usage: make test-app APP=prompts
test-app:
	@test -n "$(APP)" || (echo "Usage: make test-app APP=<app_label>"; exit 1)
	$(COVER) erase
	$(COVER) run --rcfile=.coveragerc -m django test $(APP) --settings=mentoroai.settings -v 2
	$(COVER) combine
	$(COVER) report -m

pytest:
	$(COVER) erase
	$(COVER) run --rcfile=.coveragerc -m pytest -q
	$(COVER) combine
	$(COVER) report -m

cov-html:
	$(COVER) html --rcfile=.coveragerc
	@echo "HTML report: htmlcov/index.html"

cov-xml:
	$(COVER) xml --rcfile=.coveragerc
	@echo "XML report: coverage.xml"

# --- Lint & Format ---
lint:
	ruff check .

format:
	ruff format .

# --- Staticfiles & Frontend Build ---
collectstatic:
	$(MANAGE) collectstatic --noinput

build-frontend:
	$(NPM) ci
	$(NPM) run build

# --- Dependency Management (pip-tools) ---
pip-compile:
	pip-compile --no-strip-extras --output-file=requirements.txt requirements.in

pip-sync:
	pip-sync requirements.txt

# --- Security ---
pip-audit:
	pip-audit --ignore-vuln [GHSA-4xh5-x5gv-qwph]

bandit:
	bandit -r .

security: pip-audit bandit

# --- Pre-Deployment Pipeline ---
# Order: Write Dependencies & sync -> Quality -> i18n -> DB -> Tests -> Frontend/Statics -> Deploy-Checks -> Security
predeploy: pip-compile pip-sync lint makemessages compilemessages makemigrations migrate test build-frontend collectstatic check-deploy security
	@echo "✅ Pre-deployment checks completed. Ready to deploy."
