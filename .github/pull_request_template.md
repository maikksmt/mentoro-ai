# Pull Request – MentoroAI

## Summary
Describe clearly what this PR changes and why it is needed.

## Related Issues
Link any related issues:
- Closes #123
- Fixes #456
- Related to #789

## Type of Change
Select the types that apply:
- [ ] Feature
- [ ] Bugfix
- [ ] Performance improvement
- [ ] Refactor
- [ ] UI/UX update
- [ ] Documentation
- [ ] Content update (guides, prompts, use cases, glossary)
- [ ] Seeds update
- [ ] DevOps / CI
- [ ] Other (please describe)

## Description of Changes
Explain the key changes:
- What was added?
- What was removed?
- What was refactored?
- Any behavior changes?

## Screenshots / UI Changes (If applicable)
If the PR affects the UI, include before/after screenshots.

## How to Test
Explain how reviewers can reproduce and test the change:
- Test environment (local, dev server, Oracle VM)
- Steps to verify functionality
- Edge cases to check
- i18n considerations

Example:
1. Run python manage.py runserver
2. Open /en/catalog/…
3. Switch language and verify…

## Checklist
Please confirm the following:
- [ ] Code follows the project’s conventions
- [ ] No breaking changes for multilingual content
- [ ] All i18n functions behave as expected
- [ ] Slugs and translation groups remain consistent
- [ ] Admin UI still works for translations
- [ ] Seeds updated if required (with stable primary keys)
- [ ] Tests added or updated
- [ ] All tests pass locally
- [ ] CI passes on GitHub Actions
- [ ] Documentation updated where needed
- [ ] No debug prints or commented-out code

## Additional Notes
Add context for reviewers:
- Known limitations
- Follow-up tasks
- Design decisions
- Impact to other parts of the system