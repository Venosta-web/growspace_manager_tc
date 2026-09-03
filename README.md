# Growspace Manager TC

[![Lint](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/lint.yaml/badge.svg)](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/lint.yaml)
[![Tests](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/tests.yaml/badge.svg)](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/tests.yaml)
[![codecov](https://codecov.io/gh/Venosta-web/growspace_manager_tc/graph/badge.svg)](https://codecov.io/gh/Venosta-web/growspace_manager_tc)

Optional tissue-culture companion integration for
[Growspace Manager](../growspace_manager): tracks cultures and their regular
maintenance actions, stores culture medium recipes, and links the plant
phenotypes that perform best on each recipe.

The integration installs and sets up today; the features are still being
built. Decisions are recorded in [`docs/adr/`](docs/adr/) and the vocabulary in
[`CONTEXT.md`](CONTEXT.md).

Phenotype identity is owned by Growspace Manager: this integration references it
and does not run without it. Setup refuses with an explanation if Growspace
Manager is not installed and configured first.
