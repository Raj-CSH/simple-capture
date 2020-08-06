"""Contains :func:`simple_capture.config.cli.command_line_interface` click group for commands."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['command_line_interface',
           'click_command_from_command']

import functools
import logging

import click

from simple_capture.config import commands
from simple_capture import utils


@click.group(name='simple_capture')
@click.option('--use-file/--no-file', default=True, help='Use a file for logging.')
@click.option('--debug/--no-debug', default=False, help='Turn debug mode on.')
def command_line_interface(use_file, debug):
    """Command line interface in the form of a click command group."""
    if use_file:
        if commands.generate_paths() == commands.PathEnum.DIR:
            click.secho('Unable to find log file! Missing directories!', fg='red', bold=True)
            log_file = None
        else:
            log_file = commands.config_file_path_dict()[commands.PathEnum.DIR].joinpath('.log')
    else:
        log_file = None
    if debug:
        utils.init_log(logging.DEBUG, log_file)
        return
    utils.init_log(logging.INFO, log_file)
    

def click_command_from_command(command):
    """Automatically generate click commands from :class:`simple_capture.config.commands.Command`
    subclasses.

    Args:
        command (type): :class:`simple_capture.config.commands.Command` subclass. 
    """
    @functools.wraps(command.__call__)
    def call_method_proxy(*args, **kwargs):
        return command.__call__(*args, **kwargs)
    for parameter in reversed(command.parameters):
        parameter_attr_dict = commands.parameter_attribute_dict()[type(parameter)]
        parameter_type_dict = commands.parameter_type_dict()[type(parameter)]
        args = [getattr(parameter, attr_name) for attr_name in parameter_attr_dict.positional]
        for starred in parameter_attr_dict.star:
            args.extend(getattr(parameter, starred))
        kwargs = {arg_name : getattr(parameter, attr_name) for arg_name, attr_name in
                  parameter_attr_dict.keyword.items()}
        for double_starred in parameter_attr_dict.double_star:
            kwargs.update(getattr(parameter, double_starred))
        call_method_proxy = parameter_type_dict(*args, **kwargs)(call_method_proxy)
    return command_line_interface.command(name=command.command_name, help=command.help())(call_method_proxy)

for command in commands.Command.retrieve_registry().values():
    click_command_from_command(command())
