# Omnispindle: test, deploy, release

From the repo root; targets are in the Makefile.

## Test

```sh
make test
```

```sh
make coverage
```

## Run it here

HTTP (FastMCP), the way eaws runs it:

```sh
make run
```

Stdio, for a local MCP client:

```sh
make run-stdio
```

## Deploy to eaws

Runs as PM2 process `Omnispindle-HTTP` in `/home/ubuntu/Omnispindle`. What a
deploy would pull:

```sh
make deploy-dry-run
```

Pull origin/main on eaws and restart:

```sh
make deploy
```

Did it come back?

```sh
timeout 20 ssh eaws "pm2 list | grep -i omnispindle; pm2 logs Omnispindle-HTTP --lines 40 --nostream"
```

`make deploy-force` hard-resets eaws's checkout to origin/main: only when the
server's copy has drifted and you mean to throw that away.

## Release to PyPI

Bump `version` in `pyproject.toml` first (1.0.0 today). The script does the
lot; or by hand:

```sh
./build-and-publish-pypi.sh
```

```sh
python -m build && python -m twine check dist/*
```

TestPyPI first, then the real one:

```sh
python -m twine upload --repository testpypi dist/*
```

```sh
python -m twine upload dist/*
```
