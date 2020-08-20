"""Contains :class:`simple_capture.config.commands.Command` base class to define commands, and
predefined commands.
"""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['parameter_attribute_dict',
           'parameter_type_dict',
           'generate_paths',
           'selected_profile',
           'Parameter',
           'KeywordParameter',
           'PositionalParameter',
           'Command',
           'Add',
           'Clear',
           'List',
           'New',
           'Record',
           'Remove',
           'Show']

import abc
import configparser
import dataclasses
import enum
import importlib
import logging
import pathlib
import platform
import shutil
import subprocess
import sys
import traceback
from typing import Any, Callable, Dict, List as ListType

import click

from simple_capture.config import io
from simple_capture.source import (filters, global_options, input_devices, input_streams,
                                   output_devices, output_streams)
from simple_capture import utils


class PathEnum(enum.Enum):
    """Enum to define constants to be used in working with simple_capture file paths, such as when
    using :func:`simple_capture.commands.config.config_file_path_dict`.
    """
    DIR = 'dir'
    CFG = 'cfg'
    PROFILES = 'profile_dir'
    PLUGINS = 'plugin_dir'

def config_file_path_dict():
    """File path constants for simple_capture.

    Returns:
        dict(PathEnum, Path): A dictionary whose keys are values of
            :class:`simple_capture.config.commands.PathEnum` and values are filepaths.
    """
    directory = pathlib.Path('~/.simple_capture').expanduser()
    config = directory.joinpath('.simple_capture')
    profiles = directory.joinpath('profiles')
    plugins = directory.joinpath('plugins')

    return {PathEnum.DIR : directory, PathEnum.CFG : config, PathEnum.PROFILES : profiles,
            PathEnum.PLUGINS : plugins}

def config_backup_dict():
    """File path generation constants for simple_capture.

    Returns:
        dict(PathEnum, callable): A dictionary whose keys are values of
            :class:`simple_capture.config.commands.PathEnum` and values are callables, that
            regenerate simple_capture filepaths from
            :func:`simple_capture.config.commands.config_backup_dict`.
    """
    directory = lambda: config_file_path_dict()[PathEnum.DIR].mkdir()

    def config():
        parser = configparser.ConfigParser()
        parser['Main'] = {'selected_profile' : 'default.cfg'}
        with config_file_path_dict()[PathEnum.CFG].open('w') as config_file:
            parser.write(config_file)

    def profiles():
        config_file_path_dict()[PathEnum.PROFILES].mkdir()
        with config_file_path_dict()[PathEnum.PROFILES].joinpath('default.cfg').open('w'):
            pass

    plugins = lambda: config_file_path_dict()[PathEnum.PLUGINS].mkdir()

    return {PathEnum.DIR : directory, PathEnum.CFG : config, PathEnum.PROFILES : profiles,
            PathEnum.PLUGINS : plugins}

def parameter_attribute_dict():
    """Helper function to create click commands from command classes.

    Returns:
        dict(type, ParameterArgumentNames): Mapping between
            :class:`simple_capture.config.commands.Parameter` subclasses and
            :class:`simple_capture.config.commands.ParameterArgumentNames` instances. Indicates how
            attributes should be unpacked as arguments for click decorators, when constructing
            click commands.
    """
    c_param_arg_names = ParameterArgumentNames(keyword={'prompt' : 'prompt'})

    k_param_arg_names = ParameterArgumentNames(positional=['name_long', 'name_short'],
                                               keyword={argument : argument for argument in
                                                        KeywordParameter.__dataclass_fields__}) # pylint:disable=no-member

    p_param_arg_names = ParameterArgumentNames(positional=['name'],
                                               keyword={argument : argument for argument in
                                                        PositionalParameter.__dataclass_fields__}) # pylint:disable=no-member

    for param_arg_names in k_param_arg_names, p_param_arg_names:
        for positional in param_arg_names.positional:
            del param_arg_names.keyword[positional]

    return {ConfirmationParameter : c_param_arg_names, KeywordParameter : k_param_arg_names,
            PositionalParameter : p_param_arg_names}

def parameter_type_dict():
    """Helper function to create click commands from command classes.

    Returns:
        dict(type, function): Mapping between
            :class:`simple_capture.config.commands.Parameter` subclasses and click decorators.
            Indicates which decorator to use per parameter of a command, when constructing click
            command.
    """
    return {ConfirmationParameter : click.confirmation_option, KeywordParameter : click.option,
            PositionalParameter : click.argument}

@dataclasses.dataclass
class Parameter(metaclass=abc.ABCMeta):
    """Parameter base dataclass. Used to create parameters for commands."""

@dataclasses.dataclass
class ConfirmationParameter(Parameter):
    """Parameter subclass to add a confirmation prompt to a command.

    Args:
        prompt (str): Prompt to display with confirmation option.
    """
    prompt: str

@dataclasses.dataclass
class KeywordParameter(Parameter):
    """Parameter subclass to add a keyword argument or flag to a command.

    Args:
        name_long (str): The first argument for click.option, usually used as the longer name for a
            click option/keyword argument. However, it is just the first positional argument
            provided to the click.option decorator.
        name_short (str): The second argument for click.option, usually used as the shorter name
            for a click option/keyword argument. However, it is just the second positional argument
            provided to the click.option decorator.
        **kwargs: The rest of these arguments correspond directly to click.option arguments and are
            passed as keyword arguments.
    """
    name_long: str
    name_short: str
    type: click.ParamType = None
    callback: Callable = None
    show_default: bool = False
    prompt: bool = False
    confirmation_prompt: bool = False
    hide_input: bool = False
    is_flag: bool = False
    flag_value: Any = None
    multiple: bool = False
    count: bool = False
    hidden: bool = False
    default: Any = None
    expose_value: bool = True
    is_eager: bool = False
    metavar:str = None
    nargs: int = 1
    required: bool = False

@dataclasses.dataclass
class PositionalParameter(Parameter):
    """Parameter subclass to add a positional argument to a command.

    Args:
        name_long (str): The first argument for click.option, used as the name for a
            click (positional) argument.
        **kwargs: The rest of these arguments correspond directly to click.argument arguments and
            are passed as keyword arguments.
    """
    name: str
    type: click.ParamType
    callback: Callable = None
    default: Any = None
    expose_value: bool = True
    is_eager: bool = False
    metavar:str = None
    nargs: int = 1
    required: bool = True

@dataclasses.dataclass(frozen=True)
class ParameterArgumentNames:
    """Dataclass to specify how to unpack the attributes of instances of subclasses of
    :class:`simple_capture.config.commands.Parameter`, when constructing click commands.

    Args:
        star (:obj:`list(list(str))`, optional): A list of attribute names to be unpacked using
            extended call syntax, i.e. '*args'.
        double_star (:obj:`list(dict(str, str))`, optional): A list of attribute names to be
            unpacked using extended call syntax, i.e. '**kwargs'.
        keyword (:obj:`dict(str, str)`, optional): A mapping of attribute names to the
            corresponding click keyword argument name.
        positional (:obj:`list(str)`, optional): A list of attribute names to be unpacked as
            positional arguments.
    """
    star: ListType[str] = dataclasses.field(default_factory=list)
    double_star: ListType[str] = dataclasses.field(default_factory=list)
    keyword: Dict[str, str] = dataclasses.field(default_factory=dict)
    positional: ListType[str] = dataclasses.field(default_factory=list)

class Command(utils.RegistryEnabledObject, metaclass=abc.ABCMeta, spec=utils.FfSpec.NONE):
    """Command base class for simple_capture commands. Subclasses must define a __call__ method,
    and the properties help and parameters.

    Attributes:
        help (str): Help message for command.
        parameters (list(Parameter)): List of :class:`simple_capture.config.commands.Parameter`
            detailing parameters of __call__ method.
    """
    _command_registry = {}

    @property
    @abc.abstractmethod
    def parameters(self):
        """list(Parameter): List of :class:`simple_capture.config.commands.Parameter` detailing
        parameters of __call__ method.
        """

    @abc.abstractmethod
    def __call__(self, **kwargs):
        """Calls command.

        Args:
            **kwargs: Arguments provided to command. See
            :attr:`simple_capture.config.commands.Command.parameters` for a list of arguments that
            are provided.
        """

    def __init_subclass__(cls, command_name, **kwargs):
        super().__init_subclass__(spec=cls._flag, **kwargs)
        cls.command_name = command_name
        logging.info(f'Command {cls} found with name {command_name}!')
        cls.retrieve_registry()[command_name] = cls
        logging.debug(f'Found Commands: {cls.retrieve_registry()}.')

    def __repr__(self):
                return (f'{type(self).__name__}'
                        f'(command_name=\'{self.command_name}\')')

    @classmethod
    def __subclasshook__(cls, subclass):
        return (('__call__' in subclass.__dict__ and hasattr(subclass, 'command_name'))
                or subclass in cls.retrieve_registry())

    @classmethod
    def retrieve_registry(cls):
        return cls._command_registry

class Add(Command, command_name='add'):
    """Adds a member to the selected profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='config_name', metavar='NAME', type=str),
                KeywordParameter(name_long='--type', name_short='-t', required=True,
                                 type=click.Choice(['filter', 'global_options', 'input_stream',
                                                    'input_device', 'output_stream',
                                                    'output_device'])),
                KeywordParameter(name_long='--stream', name_short='-s', default='video',
                                 type=click.Choice(['audio', 'video'])),
                KeywordParameter(name_long='--layer', name_short='-l', default=None,
                                 type=click.IntRange(min=0)),
                KeywordParameter(name_long='--name', name_short='-n', required=True, type=str),
                PositionalParameter(name='keyword_arguments', nargs=-1, type=str, required=False,
                                    metavar='KWARGS')]

    def __call__(self, **kwargs):
        """Adds a member to the selected profile. Preprocesses and delegates to
        :func:`simple_capture.config.io.generate_profile_config_parser`.

        Keyword Args:
            config_name (str): Name of the member in the config.
            type (str): Type of the member.
            stream (str): Stream of the member. Either 'audio' or 'video'. Defaults to 'video'.
            layer (int): Layer of the member. Defaults to the next available layer.
            name (str): Name of the member from the registry.
            keyword_arguments (list(str)): Arguments to be provided to the member.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho(f'Unable to add {kwargs["config_name"]}! Directories missing!', fg='red',
                        bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return

        parameters = io.parameter_type_dict()[kwargs['type']]()
        ffmpeg_arguments = {}
        for kwarg in kwargs['keyword_arguments']:
            split_kwarg = kwarg.split('=', maxsplit=1)
            if len(split_kwarg) != 2:
                click.secho(f'Invalid syntax \'{kwarg}\' for arguments!', fg='red', bold=True)
                return
            ffmpeg_arguments[split_kwarg[0]] = split_kwarg[1]
        for arg, val in ffmpeg_arguments.items():
            if arg not in parameters:
                click.secho(f'Unknown argument {arg}!', fg='red', bold=True)
                return
            if not isinstance(parameters[arg], bool):
                ffmpeg_arguments[arg] = parameters[arg](val)
            else:
                if val.lower() not in ['true', 'yes', 'y', 'false', 'no', 'n']:
                    click.secho(f'Invalid value for argument {arg}, must be a boolean [y/n]!',
                                fg='red')
                    click.secho(f'Replacing {val} with false!', fg='red')
                    ffmpeg_arguments[arg] = 'false'

        profile_name = selected_profile()
        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile_name}.cfg')
        if profile_name is None:
            click.secho(f'Unable to add {kwargs["config_name"]}! Cannot find selected profile!',
                        fg='red', bold=True)
            return

        profile = io.read_config(file_path)
        profile = io.generate_profile_config_parser(kwargs['config_name'], kwargs['stream'],
                                                    kwargs['layer'], kwargs['name'],
                                                    kwargs['type'], profile, **ffmpeg_arguments)
        if profile is None:
            click.secho(f'Unable to add {kwargs["config_name"]}!', fg='red', bold=True)
            return
        io.write_config(file_path, profile)
        click.secho(f'Added {kwargs["config_name"]} to {profile_name}!', fg='green', bold=True)

    @classmethod
    def help(cls):
        return """Add a member to the selected profile.

               CONFIG_NAME: Name of the section of the member to be added.

               TYPE: Type of the member, e.g. input_device.

               STREAM: Stream of the member. On the video stream, the overlay filter is used to
               join layers, whereas on the audio stream, the amix filter is used.

               LAYER: Layer of the member. Members with at higher layers, will be overlayed
               on members at lower layers (if on the video stream). Layers are separated by
               stream. Filters operate via layers.

               NAME: Name of the member from the type registry, e.g. x11grab (type=input_device).

               KEYWORD_ARGUMENTS: Arguments for the member. To be passed as 'KWD=VAL KWD=VAL2 ...'.
               """

class Clear(Command, command_name='clear'):
    """Clears a profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='profile', type=str, metavar='NAME'),
                ConfirmationParameter(prompt='Do you want to continue?')]

    def __call__(self, profile):
        """Clears a profile.

        Args:
            profile (str): Name of profile to clear.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho(f'Unable to clear profile! Directories missing!', fg='red', bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return

        if profile.endswith('.cfg'):
            profile = profile[:-4]

        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
        if not file_path.exists():
            click.secho(f'Profile {profile} does not exist!', fg='red', bold=True)
            return
        with file_path.open('w'):
            click.secho(f'Cleared profile at {file_path}!', fg='green', bold=True)

    @classmethod
    def help(cls):
        return """Clear a profile.

               PROFILE: Name of the profile to be cleared.
               """

class List(Command, command_name='list'):
    """Lists a type."""
    @property
    def parameters(self):
        return [PositionalParameter(name='type_name', metavar='TYPE',
                                    type=click.Choice(['profile', 'filter',
                                                       'input_device', 'input_stream',
                                                       'output_device', 'output_stream']))]

    def __call__(self, type_name):
        """Lists a type.

        Args:
            type_name (str): Name of type to list.
        """
        if type_name == 'profile':
            self._profiles()
        elif type_name == 'input_device' or type_name == 'output_device':
            self._devices(type_name)
        else:
            registry = io.base_type_dict()[type_name].retrieve_registry()
            click.secho(f'\nAvailable {type_name}s:\n', fg='green', bold=True)
            for name in registry:
                click.secho(f'{name}\n', fg='green', bold=True)

    def _profiles(self):
        """Lists profiles."""
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho('Unable to list profiles! Directories missing!', fg='red', bold=True)
            click.secho(f'Error: {result}.')
            return
        profiles = config_file_path_dict()[PathEnum.PROFILES].glob('*.cfg')
        profiles = [str(profile.name)[:-4] for profile in profiles]
        click.secho('\nAvailable profiles:\n', fg='green', bold=True)
        for profile in profiles:
            click.secho(f'{profile}\n', fg='green', bold=True)

    def _devices(self, name):
        """Lists input or output devices.

        Args:
            name (str): Name of type to list.
        """
        process = subprocess.run('ffmpeg -devices'.split(), capture_output=True, encoding='utf-8')
        output = process.stdout

        device_choices = {**input_devices.AudioInputDevice.retrieve_registry(),
                          **input_devices.VideoInputDevice.retrieve_registry(),
                          **output_devices.AudioOutputDevice.retrieve_registry(),
                          **output_devices.VideoOutputDevice.retrieve_registry()}.keys()

        inputs = []
        outputs = []
        for line in output.split('\n'):
            words = line.strip().split()
            if len(words) < 2:
                continue
            specifier = words[0] # 0 = D or DE or E
            dev_name = words[1] # 1 = device name, e.g. x11grab or video4linux2,v4l2
            if 'D' in specifier: # D for demux
                if dev_name in device_choices:
                    inputs.append(dev_name)

            if 'E' in specifier: # E for mux
                if dev_name in device_choices:
                    outputs.append(dev_name)

        def io_devices_printer(io_specifier):
            click.secho(f'\nAvailable {io_specifier}_devices:\n', fg='green', bold=True)
            io_device_dict = {'input' : {'audio' : input_devices.AudioInputDevice,
                                         'video' : input_devices.VideoInputDevice,
                                         'list' : inputs},
                              'output' : {'audio' : output_devices.AudioOutputDevice,
                                          'video' : output_devices.VideoOutputDevice,
                                          'list' : outputs}}

            formatted = {}
            io_dict = io_device_dict[io_specifier]
            for device in io_dict['list']:
                type_str = ''
                for io_base_specifier in 'audio', 'video':
                    if device in io_dict[io_base_specifier].retrieve_registry():
                        if type_str == '':
                            type_str = io_base_specifier
                        else:
                            type_str = f'({type_str}, {io_base_specifier})'
                formatted[device] = type_str or 'NOT_IMPLEMENTED'

            for dev_name, dev_type in formatted.items():
                color = 'green' if dev_type != 'NOT_IMPLEMENTED' else 'red'
                click.secho(f'{dev_name} (type={dev_type})\n', fg=color, bold=True)

        io_devices_printer(name[:-7])

    @classmethod
    def help(cls):
        return """List names from a type registry, or list all profiles.
               If argument is  either input_device or output_device, then devices are only listed
               if they are available on one's platform.

               TYPE_NAME: Name of type to list.
               """

class New(Command, command_name='new'):
    """Creates a new profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='profile', type=str, metavar='NAME')]

    def __call__(self, profile):
        """Creates a new profile.

        Args:
            profile (str): Name of profile to be created.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho(f'Unable to create new profile! Directories missing!', fg='red', bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return

        if profile.endswith('.cfg'):
            profile = profile[:-4]

        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
        if file_path.exists():
            click.secho(f'Profile {profile} already exists!', fg='red', bold=True)
            return
        with file_path.open('w'):
            click.secho(f'Created new profile at {file_path}!', fg='green', bold=True)

    @classmethod
    def help(cls):
        return """Create a new profile.

               NAME: Name of the profile to be created.
               """

class Quickstart(Command, command_name='quickstart'):
    """Starts a capture with a predefined quickstart profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='output', type=str, required=False, default='out.mkv'),
                KeywordParameter(name_long='--regenerate-default', name_short='-d', is_flag=True,
                                 default=False),
                PositionalParameter(name='output_options', type=str, required=False, nargs=-1)]

    def __call__(self, output, regenerate_default, output_options):
        profile = 'quickstart'
        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
        if not file_path.exists():
            click.secho(f'Quickstart profile {profile} does not exist! Regenerating!')
            New()(profile)
            self._regenerate_quickstart(profile, output, output_options)
        if regenerate_default:
            self._regenerate_quickstart(profile, output, output_options)
        click.secho('Starting capture!', fg='green', bold=True)
        logging.info(f'Capture result: {record(profile)}.')

    def _regenerate_darwin(self, output, output_options):
        Add()(config_name='ScreenCapture', type='input_device', name='avfoundation',
              stream='video', layer=0, keyword_arguments=['display=default',
                                                          f'video_size={utils.resolution()}'])
        Add()(config_name='AudioCapture', type='input_device', name='avfoundation', stream='audio',
              layer=0, keyword_arguments=['card=default'])
        Add()(config_name='Output', type='output_stream', name='other-stream', stream='video',
              layer=0, keyword_arguments=[f'filename={output}', *output_options])
    
    def _regenerate_linux(self, output, output_options):
        output_options = [*output_options, 'video_codec=h264_vaapi']
        for option in output_options[:-1]:
            if 'video_codec' in option:
                output_options.pop()
                break

        Add()(config_name='ScreenCapture', type='input_device', name='kmsgrab', stream='video',
              layer=0, keyword_arguments=['display=crtc_id=42'])
        Add()(config_name='HwmapFilter', type='filter', name='other-filter', stream='video',
              layer=1, keyword_arguments=['argument_string=filter_name=hwmap;derive_device=vaapi',
                                          'input_layer_string=0'])
        Add()(config_name='ScaleVaapiFilter', type='filter', name='other-filter', stream='video',
              layer=2, keyword_arguments=['argument_string=filter_name=scale_vaapi;format=nv12',
                                          'input_layer_string=1'])
        Add()(config_name='AudioCapture', type='input_device', name='alsa', stream='audio',
              layer=0, keyword_arguments=['card=hw:0'])
        Add()(config_name='Global', type='global_options', name='_', stream='video', layer=0,
              keyword_arguments=['sudo=true'])
        Add()(config_name='Output', type='output_stream', name='other-stream', stream='video',
              layer=0, keyword_arguments=[f'filename={output}', *output_options])

    def _regenerate_windows(self, output, output_options):
        Add()(config_name='ScreenCapture', type='input_device', name='gdigrab', stream='video',
              layer=0, keyword_arguments=['display=desktop'])
        Add()(config_name='AudioCapture', type='input_device', name='dshow', stream='audio',
              layer=0, keyword_arguments=['card=virtual-audio-capturer'])
        Add()(config_name='Output', type='output_stream', name='other-stream', stream='video',
              layer=0, keyword_arguments=[f'filename={output}', *output_options])

    def _regenerate_quickstart(self, profile, output, output_options):
        Clear()(profile)
        Select()(profile)
        platform_dict = {'Darwin' : self._regenerate_darwin, 'Linux' : self._regenerate_linux,
                         'Windows' : self._regenerate_windows}
        platform_dict.get(platform.system(), 'Linux')(output, output_options)

    @classmethod
    def help(cls):
        return """Starts a capture with a predefined quickstart profile.

               OUTPUT: Output filename.

               REGENERATE_DEFAULT: If set, resets the quickstart profile.

               OUTPUT_OPTIONS: Options for output. To be passed as 'KWD=VAL KWD=VAL2 ...'.
               """

class Record(Command, command_name='record'):
    """Starts a capture with the selected profile."""
    @property
    def parameters(self):
        return []

    def __call__(self):
        """Starts a capture with the selected profile."""
        profile = selected_profile()
        if profile is None:
            click.secho('Unable to start capture! Cannot determine selected profile!', fg='red',
                        bold=True)
            return
        logging.info(f'Capture result: {record(profile)}.')

    @classmethod
    def help(cls):
        return """Start a capture using the selected profile."""

class Remove(Command, command_name='remove'):
    """Removes a member from the selected profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='config_name', type=str, metavar='NAME'),
                ConfirmationParameter(prompt='Do you want to continue?')]

    def __call__(self, config_name):
        """Removes a member from the selected profile.

        Args:
            config_name (str): Name of the member in the config.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho(f'Unable to remove {config_name}! Directories missing!', fg='red',
                        bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return

        profile = selected_profile()
        if profile is None:
            click.secho(f'Unable to remove {config_name}! Cannot find selected profile!', fg='red',
                        bold=True)
            return

        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
        parser = io.read_config(file_path)
        if not parser.remove_section(config_name):
            click.secho(f'Section {config_name} does not exist!', fg='red', bold=True)
            return
        io.write_config(file_path, parser)
        click.secho(f'Removed section {config_name}!', fg='green', bold=True)

    @classmethod
    def help(cls):
        return """Remove a member from the selected profile.

               CONFIG_NAME: Name of the section of the member to be removed.
               """

class Select(Command, command_name='select'):
    """Selects a profile."""
    @property
    def parameters(self):
        return [PositionalParameter(name='profile', type=str, metavar='NAME')]

    def __call__(self, profile):
        """Selects a profile.

        Args:
            profile (str): Name of profile to select.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.CFG:
            click.secho(f'Unable to select profile! Configuration files missing!', fg='red',
                        bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return

        if profile.endswith('.cfg'):
            profile = profile[:-4]

        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
        if not file_path.exists():
            click.secho(f'Profile {profile} does not exist!', fg='red', bold=True)
            return

        file_path = config_file_path_dict()[PathEnum.CFG]
        parser = io.read_config(file_path)
        parser['Main'] = {'selected_profile' : profile}
        io.write_config(file_path, parser)
        click.secho(f'Selected profile {profile}!', fg='green', bold=True)

    @classmethod
    def help(cls):
        return """Select a profile.
               The selected profile is the profile upon which the 'add' and 'remove' commands act.

               PROFILE: Name of the profile to be selected.
               """

class Show(Command, command_name='show'):
    """Shows the help message of a member."""
    @property
    def parameters(self):
        return [PositionalParameter(name='type_name', metavar='TYPE',
                                    type=click.Choice(['profile', 'filter', 'global_options',
                                                      'input_device', 'input_stream',
                                                      'output_device', 'output_stream'])),
                PositionalParameter(name='name', type=str),
                KeywordParameter(name_long='--any', name_short='forced', flag_value='any',
                                 default=True, is_flag=True),
                KeywordParameter(name_long='--audio', name_short='forced', flag_value='audio',
                                 is_flag=True),
                KeywordParameter(name_long='--video', name_short='forced', flag_value='video',
                                 is_flag=True)]

    def __call__(self, type_name, name, forced):
        """Shows the help message of a member. See
        :meth:`simple_capture.utils.RegistryEnabledObject.help`.

        Args:
            type_name (str): Name of type of member.
            name (str): Name of member in type registry.
            forced (str): Certain members of type input_device or output_device, e.g.
                :class:`simple_capture.source.input_device.AvFoundationAudio` and
                :class:`simple_capture.source.input_device.AvFoundationVideo`,
                are found in both the
                :meth:`simple_capture.source.input_device.AudioInputDevice.retrieve_registry` and
                the :meth:`simple_capture.source.input_device.VideoInputDevice.retrieve_registry`,
                or the
                :meth:`simple_capture.source.output_device.AudioOutputDevice.retrieve_registry` and
                the
                :meth:`simple_capture.source.output_device.VideoOutputDevice.retrieve_registry`,
                as they share a name. So one would not be found in the combined registry.
                This flag forces the command to find the member in a certain registry. Either
                'audio', 'video' or 'any'. Defaults to 'any'.
        """
        if type_name == 'profile':
            self._ignore_flag(type_name, 'forced', forced, 'any')
            self._profiles(name)
            return
        elif type_name == 'global_options':
            self._ignore_flag(type_name, 'forced', forced, 'any')
            self._ignore_flag(type_name, 'name', name, '')
            click.secho(global_options.GlobalOptions.help(), fg='green', bold=True)
            return
        elif type_name == 'input_device' or type_name == 'output_device':
            registry = self._devices_registry(type_name, forced)
        else:
            self._ignore_flag(type_name, 'forced', forced, 'any')
            registry = io.base_type_dict()[type_name].retrieve_registry()

        member = registry.get(name)
        if member is None:
            click.secho(f'Unable to find {type_name} {name}!', fg='red', bold=True)
            return
        click.secho(member.help(), fg='green', bold=True)


    def _ignore_flag(self, type_name, flag_name, flag_value, flag_default):
        """Checks if an option that should be ignored has been altered, and notifies the user.

        Args:
            type_name (str): Name of type.
            flag_name (str): Name of the flag/option.
            flag_value (str): Value of the flag/option provided by the user.
            flag_default (str): The default/unaltered value of the flag/option.
        """
        if flag_value != flag_default:
            click.secho(f'Ignoring flag {flag_name}, invalid option for type {type_name}!',
                        fg='red')

    def _profiles(self, name):
        """Shows the contents of a profile.

        Args:
            name (str): Name of the profile to display.
        """
        result = generate_paths()
        if result == PathEnum.DIR or result == PathEnum.PROFILES:
            click.secho('Unable to show profile! Directories missing!', fg='red', bold=True)
            click.secho(f'Error: {result}.', fg='red', bold=True)
            return
        if name.endswith('.cfg'):
            name = name[:-4]

        file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{name}.cfg')
        if not file_path.exists():
            click.secho(f'Profile {name} does not exist!', fg='red', bold=True)
            return
        profile = io.read_config(file_path)
        for section in profile.sections():
            color = 'green'
            name_ = profile.get(section, 'name', fallback='Unknown')
            type_ = profile.get(section, 'type', fallback='Unknown')
            stream = profile.get(section, 'stream', fallback='Unknown')
            layer = profile.getint(section, 'layer', fallback='Unknown')
            for attr in [name_, type_, stream, layer]:
                if attr == 'Unknown':
                    color = 'red'
                    break
            section_str = (f'{section} (name={name_}, type={type_}, stream={stream}, '
                          f'layer={layer}):\n\tArguments:\n')
            options = profile.options(section)
            for option in options:
                section_str = f'{section_str}\t\t{option} = {profile.get(section, option)}\n'
            click.secho(section_str, fg=color, bold=True)

    def _devices_registry(self, type_name, forced):
        """Get the device registry.

        Args:
            type_name (str): Name of the type.
            forced (str): Force a registry. Either 'audio' or 'video'.
        """
        base_dict = {'input_device' : {'audio' : input_devices.AudioInputDevice,
                                       'video' : input_devices.VideoInputDevice,
                     'output_device' : {'audio' : output_devices.AudioOutputDevice,
                                        'video' : output_devices.VideoOutputDevice}}}

        if forced != 'any':
            return base_dict[type_name][forced].retrieve_registry()
        return {**base_dict[type_name]['audio'].retrieve_registry(),
                **base_dict[type_name]['video'].retrieve_registry()}

    @classmethod
    def help(cls):
        return """Show help message for a member of any type.

               TYPE_NAME: Name of type.

               NAME: Name of member of the specified type. Ignored if type is global_options.

               FORCED: Flag to force audio or video, only used if type is input_device or
               output_device. This should be used when showing help for input devices like
               'avfoundation', which can be used for both audio and video capture, as parameters
               differ depending on what it is used for.
               """

def generate_paths():
    """Ensures that all simple_capture paths exist.

    Returns:
        PathEnum: If returns other than None, then the return value indicates what the error
            relates to.
    """
    directory = config_file_path_dict()[PathEnum.DIR]
    gen_dir = config_backup_dict()[PathEnum.DIR]
    config = config_file_path_dict()[PathEnum.CFG]
    gen_cfg = config_backup_dict()[PathEnum.CFG]
    profiles = config_file_path_dict()[PathEnum.PROFILES]
    gen_profile_dir = config_backup_dict()[PathEnum.PROFILES]
    plugins = config_file_path_dict()[PathEnum.PLUGINS]
    gen_plugin_dir = config_backup_dict()[PathEnum.PLUGINS]

    if not directory.exists():
        logging.info(f'Creating simple_capture directory at {directory}!')
        try:
            gen_dir()
        except OSError:
            logging.error(f'Unable to make config directory {directory}!')
            logging.info(traceback.format_exc())
            return PathEnum.DIR 
    elif not directory.is_dir():
        logging.warning(f'Removing file at {directory}!')
        try:
            directory.unlink()
        except OSError:
            logging.error(f'Unable to remove {directory}!')
            logging.info(traceback.format_exc())
            logging.info(f'To make config directory, remove {directory}!')
            return PathEnum.DIR
        logging.info(f'Creating simple_capture directory at {directory}!')
        try:
            gen_dir()
        except OSError:
            logging.error(f'Unable to make config directory {directory}!')
            logging.info(traceback.format_exc())
            return PathEnum.DIR

    if not config.exists():
        logging.info(f'Creating simple_capture config at {config}!')
        try:
            gen_cfg()
        except OSError:
            logging.error(f'Unable to make config file {config}!')
            logging.info(traceback.format_exc())
            return PathEnum.CFG
    elif not config.is_file():
        logging.warning(f'Removing directory at {config}!')
        try:
            shutil.rmtree(config)
        except OSError:
            logging.error(f'Unable to remove {config}!')
            logging.info(traceback.format_exc())
            logging.info(f'To make config file, remove {config}!')
            return PathEnum.CFG
        logging.info(f'Creating simple_capture config at {config}!')
        try:
            gen_cfg()
        except OSError:
            logging.error(f'Unable to make config file {config}!')
            logging.info(traceback.format_exc())
            return PathEnum.CFG

    if not profiles.exists():
        logging.info(f'Creating simple_capture profile directory at {profiles}!')
        try:
            gen_profile_dir()
        except OSError:
            logging.error(f'Unable to make profile directory {profiles}!')
            logging.info(traceback.format_exc())
            return PathEnum.PROFILES
    elif not profiles.is_dir():
        logging.warning(f'Removing file at {profiles}!')
        try:
            profiles.unlink()
        except OSError:
            logging.error(f'Unable to remove {profiles}!')
            logging.info(traceback.format_exc())
            logging.info(f'To make profile directory, remove {profiles}!')
            return PathEnum.PROFILES 
        logging.info(f'Creating simple_capture profile directory at {profiles}!')
        try:
            gen_profile_dir()
        except OSError:
            logging.error(f'Unable to make profile directory {profiles}!')
            logging.info(traceback.format_exc())
            return PathEnum.PROFILES 

    if not plugins.exists():
        logging.info(f'Creating simple_capture plugin directory at {plugins}!')
        try:
            gen_plugin_dir()
        except OSError:
            logging.error(f'Unable to make plugin directory {plugins}!')
            logging.info(traceback.format_exc())
            return PathEnum.PLUGINS 
    elif not plugins.is_dir():
        logging.warning(f'Removing file at {plugins}!')
        try:
            plugins.unlink()
        except OSError:
            logging.error(f'Unable to remove {plugins}!')
            logging.info(traceback.format_exc())
            logging.info(f'To make plugin directory, remove {plugins}!')
            return PathEnum.PLUGINS 
        logging.info(f'Creating simple_capture plugin directory at {plugins}!')
        try:
            gen_plugin_dir()
        except OSError:
            logging.error(f'Unable to make plugin directory {plugins}!')
            logging.info(traceback.format_exc())
            return PathEnum.PLUGINS 

def record(profile):
    """Starts a capture with the given profile.

    Args:
        profile (str): Name of the profile to use.
    """
    file_path = config_file_path_dict()[PathEnum.PROFILES].joinpath(f'{profile}.cfg')
    parser = io.read_config(file_path)
    capture, sudo = io.generate_ffmpeg_node_structure(parser)
    if capture is None:
        click.secho('Unable to start capture! See log for details.', fg='red', bold=True)
        return
    executable = ['sudo', 'ffmpeg'] if sudo else 'ffmpeg'
    click.secho(f'Starting capture with profile {profile}.', fg='green', bold=True)
    capture.run(cmd=executable)

def selected_profile():
    """Gets the selected profile.

    Returns:
        str: The name of the selected profile (not a filepath). Returns None on fail.
    """
    result = generate_paths()
    if result == PathEnum.DIR or result == PathEnum.CFG:
        logging.error(f'Unable to find selected profile! Configuration files missing!')
        logging.info(f'Error: {result}.')
        return

    file_path = config_file_path_dict()[PathEnum.CFG]

    try:
        parser = io.read_config(file_path)
    except OSError:
        logging.error(f'Unable to read config file {file_path}!')
        logging.info(traceback.format_exc())
        logging.info(f'Removing config file {file_path}!')
        try:
            file_path.unlink()
        except OSError:
            logging.error(f'Unable to remove {file_path}!')
            logging.info(traceback.format_exc())
            logging.error(f'Unable to find selected profile!')
            return
        if generate_paths() == PathEnum.CFG:
            logging.error(f'Unable to find selected profile! Configuration files missing!')
            return
        parser = io.read_config(file_path)
    if 'Main' not in parser.sections() or 'selected_profile' not in parser.options('Main'):
        logging.info(f'Rewriting config file {file_path}!')
        parser = configparser.ConfigParser()
        parser['Main'] = {'selected_profile' : 'default'}
        io.write_config(file_path, parser)

    return parser['Main']['selected_profile']
