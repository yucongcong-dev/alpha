Runtime blacklist artifacts live here.

- `template_blacklist.json`: optional cross-dataset default avoid rules
- `<dataset>/blacklist.json`: dataset-specific learned blacklist entries

These files are runtime strategy assets, not template source files, so they live
beside `templates/` at the project root instead of under `data/`.
