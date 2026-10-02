from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MedView educational workstation")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser", action="store_true", help="Reserved for launcher integrations"
    )
    args = parser.parse_args()
    uvicorn.run("medview.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
