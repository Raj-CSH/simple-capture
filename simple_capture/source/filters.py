"""Contains generic filter class, :class:`Filter`, to apply any FFmpeg filter."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_filter',
           'filter_parameters',
           'register_filter_complex',
           'filter_complex',
           'process_argument_string',
           'process_layer_string',
           'Filter',
           'VideoOverlay',
           'AudioMix']

import abc
import enum
import functools
import logging

from simple_capture.source import streams
from simple_capture import utils

from ffmpeg import nodes

_ARG_SEP_CHR = ';'
_ARG_EXP_CHR = '='
_LYR_SEP_CHR = ','


def filter_parameters():
    """Helper function to read arguments from a config file to create a node.

    Returns:
        dict(str, type): A dictionary of the types of the arguments of
            :class:`simple_capture.source.filters.Filter`. Used to instruct
            :func:`simple_capture.config.io.generate_ffmpeg_node_structure` how to collect
            arguments from a config file.
    """
    return {'argument_string' : str, 'input_layer_string' : str, 'output_layer_string' : str}

@nodes.filter_operator()
def filter_ffmpeg(*args, **kwargs):
    """FFmpeg node that accepts multiple inputs and outputs. Can be used for any filter. Filter
    must provide 'filter_name' in **kwargs to use this.

    Args:
        *args: Input streams.
        **kwargs: Filter options.
    """
    filter_name = kwargs.pop('filter_name')
    return nodes.FilterNode(args, filter_name, kwargs=kwargs, max_inputs=None)

class Filter(utils.RegistryEnabledObject, spec=utils.FfSpec.FILTER):
    """Generic filter type. Use the command 'ffmpeg -filters' to list all available filters.
    Provide their names as the 'filter_name' argument in the argument string.

    Args:
        argument_string (str): Semicolon separated list of keyword arguments to act as filter
            options.
        input_layer_string (str): Comma separated list of integers to act as input layers.
        output_layer_string (:obj:`str`, optional): Comma separated list of integers to act as
            output layers.
    """
    _filter_registry = {}
    filter_name = 'other-filter'
    ffmpeg_constructor = filter_ffmpeg

    def __init__(self, argument_string, input_layer_string, output_layer_string=''):
        self._ffmpeg_arguments = process_argument_string(argument_string)
        self._inputs = process_layer_string(input_layer_string)
        self._outputs = process_layer_string(output_layer_string)

    @property
    def ffmpeg_arguments(self):
        """dict(str, str): Keyword arguments to be provided to the ffmpeg node constructor."""
        return self._ffmpeg_arguments

    @property
    def input_layers(self):
        """list(int): List of input layer numbers."""
        return self._inputs

    @property
    def output_layers(self):
        """list(int): List of output layer numbers."""
        return self._outputs 

    def __init_subclass__(cls, filter_name, ffmpeg_constructor=filter_ffmpeg, **kwargs):
        super().__init_subclass__(spec=cls._flag, **kwargs)
        cls.retrieve_registry()[filter_name] = cls
        cls.filter_name = filter_name
        cls.ffmpeg_constructor = ffmpeg_constructor
        logging.info((f'Filter {cls} found with name {cls.filter_name} and constructor '
                      f'{cls.ffmpeg_constructor}!'))
        logging.debug(f'Found Filters: {cls.retrieve_registry()}.')

    def __repr__(self):
        return f'{type(self).__name__}(filter_name=\'{self.filter_name}\')'

    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'filter_name') or subclass in cls.retrieve_registry())

    @classmethod
    def help(cls):
        return f"""Generic filter type. 'filter_name' must be specified in the argument_string.

               ARGUMENT_STRING: A string of filter options in the form
               'KWD1{_ARG_EXP_CHR}VAL1{_ARG_SEP_CHR}KWD2{_ARG_EXP_CHR}VAL2...'. This argument is
               required for this filter.

               INPUT_LAYER_STRING: A string of input layer numbers in the form
               '0{_LYR_SEP_CHR}1{_LYR_SEP_CHR}2...'. This argument is required.

               OUTPUT_LAYER_STRING: A string of output layer numbers in the form
               '0{_LYR_SEP_CHR}1{_LYR_SEP_CHR}2...'. This implicitly includes the
               layer on which the filter is as well.
               """

    @classmethod
    def retrieve_registry(cls):
        return cls._filter_registry

filter_complex = functools.partial(utils.class_attribute_register, Filter, 'filter_name')()
register_filter_complex = functools.partial(utils.register, registry_enabled_object=Filter)

filter_complex(Filter)


class AudioMix(Filter, filter_name='amix'):
    """'amix' FFmpeg filter. See https://ffmpeg.org/ffmpeg-filters.html#amix for more information.

    Args:
        input_layer_string (str): Comma separated list of integers to act as input layers.
        argument_string (:obj:`str`, optional): Semicolon separated list of keyword arguments to
            act as filter options.
    """
    def __init__(self, input_layer_string, argument_string='', output_layer_string=''):
        super().__init__(argument_string, input_layer_string, output_layer_string)
        self._options = {'input_count' : 'inputs', 'eof_action' : 'duration',
                         'dropout_transition' : 'dropout_transition'}
        self._force_bool = []
        for arg in self._ffmpeg_arguments:
            if arg not in self._options:
                value = self._ffmpeg_arguments.pop(arg)
                logging.warning(f'Discarded unknown argument \'{arg}\' with value \'{value}\'!')

    @functools.cached_property
    def ffmpeg_arguments(self):
        to_bool = lambda s: str(s).lower() in ['yes', 'y', 'true', '1']
        for force_bool in self._force_bool:
            if force_bool in self._ffmpeg_arguments:
                self._ffmpeg_arguments[force_bool] = to_bool(self._ffmpeg_arguments[force_bool])
        renamed = {}
        for alias in self._ffmpeg_arguments:
            renamed[self._options[alias]] = self._ffmpeg_arguments[alias]
        self._ffmpeg_arguments = renamed
        self._ffmpeg_arguments['filter_name'] = 'amix'

        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return f"""'amix' filter, used to join audio inputs.
               Official documentation: 'https://ffmpeg.org/ffmpeg-filters.html#amix'.

               ARGUMENT_STRING: A string of filter options in the form
               'KWD1{_ARG_EXP_CHR}VAL1{_ARG_SEP_CHR}KWD2{_ARG_EXP_CHR}VAL2...'.

               INPUT_LAYER_STRING: A string of input layer numbers in the form
               '0{_LYR_SEP_CHR}1{_LYR_SEP_CHR}2...'. This argument is required.
               """

class VideoOverlay(Filter, filter_name='overlay'):
    """'overlay' FFmpeg filter. See https://ffmpeg.org/ffmpeg-filters.html#overlay for more
    information.

    Args:
        input_layer_string (str): Comma separated list of integers to act as input layers.
        argument_string (:obj:`str`, optional): Semicolon separated list of keyword arguments to
            act as filter options.
    """
    def __init__(self, input_layer_string, argument_string='', output_layer_string=''):
        super().__init__(argument_string, input_layer_string, output_layer_string)
        self._options = {'x_expression' : 'x', 'y_expression' : 'y', 'eof_action' : 'eof_action',
                         'evaluation_type' : 'eval', 'end_on_shortest' : 'shortest',
                         'pixel_format' : 'format', 'repeat_last_frame' : 'repeatlast'}
        self._force_bool = ['end_on_shortest', 'repeat_last_frame']
        for arg in self._ffmpeg_arguments:
            if arg not in self._options:
                value = self._ffmpeg_arguments.pop(arg)
                logging.warning(f'Discarded unknown argument \'{arg}\' with value \'{value}\'!')

    @functools.cached_property
    def ffmpeg_arguments(self):
        to_bool = lambda s: str(s).lower() in ['yes', 'y', 'true', '1']
        for force_bool in self._force_bool:
            if force_bool in self._ffmpeg_arguments:
                self._ffmpeg_arguments[force_bool] = to_bool(self._ffmpeg_arguments[force_bool])
        renamed = {}
        for alias in self._ffmpeg_arguments:
            renamed[self._options[alias]] = self._ffmpeg_arguments[alias]
        self._ffmpeg_arguments = renamed
        self._ffmpeg_arguments['filter_name'] = 'overlay'

        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return f"""'overlay' filter, used to join video inputs.
               Official documentation: 'https://ffmpeg.org/ffmpeg-filters.html#overlay'.

               ARGUMENT_STRING: A string of filter options in the form
               'KWD1{_ARG_EXP_CHR}VAL1{_ARG_SEP_CHR}KWD2{_ARG_EXP_CHR}VAL2...'.

               INPUT_LAYER_STRING: A string of input layer numbers in the form
               '0{_LYR_SEP_CHR}1{_LYR_SEP_CHR}2...'. This argument is required.
               """

def generate_filter(name, input_layers, **kwargs):
    """Creates the FFmpeg filter node.

    Args:
        name (str): Name of the filter in the
            :meth:`simple_capture.source.filters.Filter.retrieve_registry`.
        input_layers (dict(int, ffmpeg.nodes.FilterableStream)): Mapping between input layer
            numbers and the input layers associated with them.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.filters.Filter` or any of its subclasses.

    Returns:
        ffmpeg.nodes.FilterableStream: Stream with filter applied.
    """
    filter_ = Filter.retrieve_registry().get(name)
    if filter_ is None:
        logging.error((f'Unable to find filter {name}! No filter instantiated with keyword '
                       f'arguments {kwargs}.'))

        return

    filter_object = filter_(**kwargs)
    inputs = []
    for layer in filter_object.input_layers:
        try:
            inputs.append(input_layers[layer])
        except KeyError as key_error:
            logging.error(('Unable to find input layers! No filter instantiated with keyword '
                           f'keyword arguments {kwargs}.'))
            logging.info(repr(key_error))
            return

    if len(inputs) == 0:
        logging.error(('Unable to find input layers! No filter instantiated with keyword '
                       f'keyword arguments {kwargs}.'))

        return

    ffmpeg_filter = filter_.ffmpeg_constructor(*inputs, **filter_object.ffmpeg_arguments)

    outputs = {}
    for i, layer in enumerate(filter_object.output_layers):
        outputs[layer] = ffmpeg_filter.stream(i+1)

    ffmpeg_filter = ffmpeg_filter.stream(0)

    return ffmpeg_filter, outputs, filter_object

def process_argument_string(argument_string):
    f"""Converts an argument string into a dictionary of keyword arguments.

    Args:
        argument_string (str): String of arguments.

    Important:
        The model for an argument string shall be:
        'keyword{_ARG_EXP_CHR}value{_ARG_SEP_CHR}keyword2{_ARG_EXP_CHR}value2'.

    Returns:
        dict(str, str): Keyword arguments found in the argument string.
    """
    if argument_string == '':
        return {}
    ffmpeg_arguments = {}
    split_args_list = argument_string.split(_ARG_SEP_CHR)
    for split_args in split_args_list:
        sep_args = split_args.split(_ARG_EXP_CHR)
        if len(sep_args) != 2:
            logging.warning(f'Skipping arguments {split_args}! Invalid argument string syntax!')
            logging.warning((f'The model for an argument string is \'kwd1{_ARG_EXP_CHR}val'
                             f'{_ARG_SEP_CHR}kwd2{_ARG_EXP_CHR}val2\'.'))
            continue
        ffmpeg_arguments[sep_args[0]] = sep_args[1]

        logging.info(f'Argument name \'{sep_args[0]}\' set to \'{sep_args[1]}\'.')
        logging.debug(f'Current arguments: {ffmpeg_arguments}')

    return ffmpeg_arguments

def process_layer_string(layer_string):
    f"""Converts a layer string into a list of layer numbers.

    Args:
        layer_string (str): String of layers.

    Important:
        The model for a layer string shall be: 'layer_number{_LYR_SEP_CHR}layer_number'.

    Returns:
        list(int): Layer numbers found in the layer string.
    """
    if layer_string == '':
        return []
    layers = []
    for layer in layer_string.split(_LYR_SEP_CHR):
        try:
            layers.append(int(layer))
        except ValueError as value_error:
            logging.warning(f'Skipping layer {layer}. Invalid layer string syntax!')
            logging.warning((f'The model for a layer string is \'layer_number{_LYR_SEP_CHR}'
                             'layer_number\'.'))
            logging.warning(repr(value_error))

    logging.debug(f'Layers: {layers}')

    return layers
