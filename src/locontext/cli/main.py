from __future__ import annotations

import click

from .. import __version__


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)
@click.version_option(__version__, "--version", message="%(version)s")
def main() -> None:
    """Local-first docs context engine."""
    return


if __name__ == "__main__":
    main()
