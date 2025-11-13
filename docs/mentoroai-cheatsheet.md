# MentoroAI – Befehls-Cheatsheet (aktualisiert)

Kurzreferenz für häufige Projekt-Kommandos (Django 5.2, Python 3.12, Tailwind/DaisyUI).

---

## i18n (Übersetzungen)

- `make makemessages` – Extrahiert Übersetzungsstrings für `de` und `en`.
- `make compilemessages` – Kompiliert `.po` zu `.mo`.

**Raw**

```bash
django-admin makemessages -l de -l en --ignore venv --ignore node_modules --no-wrap
django-admin compilemessages
```

---

## Django Checks

- `make check` – Allgemeine Projekt-Checks.
- `make check-deploy` – Produktionsrelevante Checks.
- `make showmigrations` – Übersicht der Migrationsstände.

**Raw**

```bash
python manage.py check
python manage.py check --deploy
python manage.py showmigrations
```

---

## Datenbank & Migrations

- `make makemigrations` – Neue Migrationen erstellen.
- `make migrate` – Migrationen anwenden.
- `make createsuperuser` – Admin-User erzeugen.
- `make shell` – Django-Python-Shell.

**Raw**

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py shell
```

---

## Tests & Coverage

- `make test` – Alle Django-Tests mit Coverage (mit `.coveragerc` & Settings).
- `make test-app APP=<app>` – Tests für eine App.
- `make pytest` – Tests mit pytest (falls eingerichtet).
- `make cov-html` – Coverage-HTML-Report erstellen.
- `make cov-xml` – XML-Report nach `coverage.xml`.

**Raw**

```bash
coverage erase
coverage run --rcfile=.coveragerc -m django test --settings=mentoroai.settings -v 2
coverage report -m
coverage html --rcfile=.coveragerc
coverage xml  --rcfile=.coveragerc
```

---

## Lint & Format

- `make lint` – Lint mit Ruff.
- `make format` – Formatierung mit Ruff.

**Raw**

```bash
ruff check .
ruff format .
```

---

## Staticfiles & Frontend

- `make collectstatic` – Statische Dateien einsammeln.
- `make build-frontend` – Frontend-Abhängigkeiten installieren & Build erzeugen.

**Raw**

```bash
python manage.py collectstatic --noinput
npm ci && npm run build
```

---

## Dependency Management (pip-tools)

- `make pip-compile` – Kompiliert `requirements.in` → `requirements.txt` (mit Upgrade).
- `make pip-sync` – Synchronisiert venv exakt zu `requirements.txt`.

**Raw**

```bash
pip-compile requirements.in --output-file=requirements.txt --upgrade
pip-sync requirements.txt
```

---

## Security

- `make pip-audit` – Paketabhängigkeiten auf CVEs prüfen.
- `make bandit` – Statische Sicherheitsanalyse.
- `make security` – Beide Security-Checks ausführen.

**Raw**

```bash
pip-audit
bandit -r .
```

---

## Server/Dev

- `make runserver` – Entwicklungsserver starten (0.0.0.0:8000).

**Raw**

```bash
python manage.py runserver 0.0.0.0:8000
```

---

## Pre-Deployment Pipeline (Ein Kommando)

- `make predeploy` – Führt in Reihenfolge aus:
    1. `make pip-compile`
    2. `make pip-sync`
    3. `make lint`
    4. `make makemessages`
    5. `make compilemessages`
    6. `make makemigrations`
    7. `make migrate`
    8. `make test`
    9. `make build-frontend`
    10. `make collectstatic`
    11. `make check-deploy`
    12. `make security`

**Hinweis:** Tools ggf. vorher installieren (`pip-tools`, `ruff`, `coverage`, `pip-audit`, `bandit`, `pytest`).

---

## Variablen & Overrides

Du kannst Tools/Interpreter überschreiben, z. B.:

- `make build-frontend NPM=pnpm`
- `make runserver MANAGE="python manage.py"`
- `make test COVER=coverage`
