# Contributing to SustainTrace

Use Python 3.12 for parser work. Run `python bootstrap.py --skip-models` for a lightweight
developer installation, then run `python -m pytest` and `python -m ruff check .` before opening a
pull request. Frontend source changes additionally require `npm run lint`, `npm run build`, and
`npm run build:static` in `workbench-ui/`.

Never commit credentials, downloaded issuer PDFs, model weights, or machine-local parser paths.
New trusted facts must preserve source SHA256, page and evidence coordinates, pass the promotion
gate, and remain distinguishable from candidates and simulated references.
