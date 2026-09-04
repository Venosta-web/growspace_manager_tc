# The TC ⇄ card WebSocket contract

This repository owns the `growspace_manager_tc/` WebSocket namespace. The
Lovelace card consumes it from a lazy chunk (ADR-0003), so a change here is one
feature across both repositories, backend side first:

```
TC handler → TC test → contract fixture → card zod schema → card chunk + test
```

The recorded payloads live in `tests/fixtures/contract/` and are fetched from
this repository's `main` by the card's contract-fixture workflow. They are
generated, never hand-edited:

```bash
../../.venv/bin/pytest tests/contract/ --regenerate-contract-fixture
```

## Presence detection

Home Assistant gives a Lovelace card no way to ask whether a custom integration
is installed, so the card asks this namespace instead.

| the card sees     | what it means                                | what it does          |
| ----------------- | -------------------------------------------- | --------------------- |
| a result          | TC is installed and an entry is loaded       | render the TC surface |
| `unknown_command` | TC is not installed                          | render nothing        |
| `not_loaded`      | TC is installed, but its entry is not loaded | render nothing        |
| anything else     | unreachable, or a shape the card cannot read | render nothing        |

The namespace is registered from `async_setup_entry`, so it does not exist
before an entry loads. It is never unregistered — Home Assistant has no such
call — which is why `not_loaded` exists: a removed integration keeps answering,
and has to say so itself.

## `growspace_manager_tc/get_manifest`

Takes no parameters. Returns:

| field                 | type            | meaning                                          |
| --------------------- | --------------- | ------------------------------------------------ |
| `contract_version`    | int             | the shape of this namespace; `1` today           |
| `integration_version` | string          | the installed release, from `manifest.json`      |
| `features`            | string[]        | the features this installation can serve         |
| `collections`         | `{string: int}` | how many records each persisted collection holds |

`contract_version` and `features` are the two gates the card uses, and they
answer different questions. The version says which wire shape it reached; a
feature says a surface is actually there to call. Gate a surface on `features`,
never on `integration_version` — an installed release is not the claim that a
feature works.

`collections` is empty on a fresh install and gains a key per collection as the
V1 model tickets land, so the card can distinguish "nothing set up yet" from
"set up and empty" without fetching the records themselves.
