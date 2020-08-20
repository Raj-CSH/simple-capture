"""Command line screen recorder, built using FFmpeg."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = []

import logging
import traceback

import click

from simple_capture.config import cli


def main():
    """Entry point."""
    try:
        cli.command_line_interface() # pylint:disable=no-value-for-parameter
    except Exception: # pylint:disable=broad-except
        click.secho('A fatal exception occured!', fg='red', bold=True)
        logging.info(traceback.format_exc())

if __name__ == '__main__':
    main()
