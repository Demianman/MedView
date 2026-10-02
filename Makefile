.PHONY: setup build test run verify demo
setup:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'
build:
	.venv/bin/cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	.venv/bin/cmake --build build
test: build
	.venv/bin/ctest --test-dir build --output-on-failure
	.venv/bin/pytest
verify: test
	.venv/bin/ruff check .
	.venv/bin/mypy src/medview
demo:
	.venv/bin/python -m medview.demo
run:
	.venv/bin/medview
