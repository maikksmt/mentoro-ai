# 🧾 Changelog

All notable changes to **MentoroAI** will be documented in this file.   
This project follows the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format  
and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

#### (New changes are placed here as the beta phase progresses.)

---

## [1.0.0-beta-3] – 2025-11-23

### Added

- rebuild Tools pages (list and detail)
- missing reversion usage for editorial workflow in usecases app
- Google Analytics
- Cookie Banner

### Changed

- Final step for user account management Dashboard and user registration.
- minor UI updates
- Update Tool Data model

### Fixed

- missing translation for badges

---

## [1.0.0-beta-2] – 2025-11-18

### Added

- minor UI updates
- add impress information

### Changed

- remove jsdeliver CDN for htmx, instead self hosted.

### Fixed

- bugfixes for Comparison Category select dropdown
    - every category were shown twice due to translation query issue
    - the category value causing a server error due to wrong query handling.
    - limit selectable categories to only available categories in available comparisons.
- bugfixes for wrong url links
- editorial fix where last published live version was not shown when article is set back to review.
- fix for missing compression and versioning of static files

---

## [1.0.0-beta-1] – 2025-11-13

### Added

- First public **Beta release** of the MentoroAI platform.
- Complete **multilingual content framework** (German/English) using *django-parler*.
- Core applications:
    - **Catalog** – Overview of AI tools with detailed tool pages.
    - **Glossary** – AI terminology database with categories.
    - **Guides** – Structured, multi-section learning guides.
    - **Prompts** – Curated prompt library with categories.
    - **Usecases** – AI use cases with filtering, categories, and tool assignments.
    - **Compare** – Tool comparison system.
- **i18n language switcher** with smart slug translation and fallbacks.
- **Django Admin enhancements**: translation tabs, inline editing, improved list and detail views.
- **Editorial system**: State machine with Roles and Rules for Editorial Workflow.
- **Tailwind CSS + DaisyUI theme** with dark/light mode.
- **Responsive frontend layout** with optimized cards, lists, and detail pages.
- **PostgreSQL integration** for development and production.
- **Newsletter system**: Allow to subscribe und unsubscribe with email.

### Changed

n.a

### Fixed

n.a.

---

## Versioning Notes

This project follows **Semantic Versioning 2.0.0**:

- **MAJOR**: incompatible API changes.
- **MINOR**: new features without breaking changes.
- **PATCH**: bug fixes.

Current version: **1.0.0-beta-1**.  
Breaking changes may still occur before the stable 1.0 release.
---

**Author:** Maik Kusmat  
**Repository:** [github.com/maikksmt/mentoro-ai](https://github.com/maikksmt/mentoro-ai)
