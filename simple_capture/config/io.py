"""Reads and writes from configs into FFmpeg commands."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = []

import collections
import configparser
import functools
import logging
import pathlib
import traceback

import ffmpeg

from simple_capture.source import (filters, global_options, input_devices, input_streams,
                                   output_devices, output_streams)
from simple_capture import utils

def base_type_dict():
    """Helper function to generate FFmpeg node structures from config files.

    Returns:
        dict(str, type): Mapping between type strings and
            :class:`simple_capture.utils.RegistryEnabledObject` subclasses.
    """
    return {'filter' : filters.Filter,
            'global_options' : global_options.GlobalOptions,
            'input_device' : input_devices.InputDevice,
            'input_stream' : input_streams.InputStream,
            'output_device' : output_devices.OutputDevice,
            'output_stream' : output_streams.OutputStream}

def factory_type_dict():
    """Helper function to generate FFmpeg node structures from config files.

    Returns:
        dict(str, function): Mapping between type strings and factory functions for
            :class:`simple_capture.utils.RegistryEnabledObject` subclasses.
    """
    return {'filter' : filters.generate_filter,
            'global_options' : global_options.generate_global_options,
            'input_device' : input_devices.generate_input_device,
            'input_stream' : input_streams.generate_input_stream,
            'output_device' : output_devices.generate_output_device,
            'output_stream' : output_streams.generate_output_stream}

def parameter_type_dict():
    """Helper function to generate FFmpeg node structures from config files.

    Returns:
        dict(str, function): Mapping between type strings and functions, that return dictionaries
            indicating the types of parameters for
            :class:`simple_capture.utils.RegistryEnabledObject` subclasses.
    """
    return {'filter' : filters.filter_parameters,
            'global_options' : global_options.global_options_parameters,
            'input_device' : input_devices.input_device_parameters,
            'input_stream' : input_streams.input_stream_parameters,
            'output_device' : output_devices.output_device_parameters,
            'output_stream' : output_streams.output_stream_parameters}

def read_config(filename):
    """Reads a config file.

    Args:
        filename (str): Filename of config file to be read.

    Returns:
        configparser.ConfigParser: Read config file.
    """
    parser = configparser.ConfigParser()
    parser.read(filename)
    logging.info(f'Read config file \'{filename}\'.')
    return parser

def write_config(filename, parser, mode='w'):
    """Writes a config file.

    Args:
        filename (str): Filename of config file to be written.
        parser (configparser.ConfigParser): Config to be written to file.
        mode (str): Mode to open file. See modes for builtin :func:`open`.
    """
    with open(filename, mode) as config_file:
        parser.write(config_file)
    logging.info(f'Wrote config file \'{filename}\'.')

def generate_profile_config_parser(section_name, node_stream, node_layer, node_name, node_type,
                                   parser, **kwargs):
    """Writes a new node to the profile config parser.

    Args:
        section_name (str): 
        node_stream (str): Stream of node to add. Either 'audio' or 'video'.
        node_layer (int): Layer of node to add. If None, layer is set to the next available layer
            in the stream.
        node_name (str): Name of node in registry to add.
        node_type (str): Type of node to add.
        **kwargs: Options for the node.

    Returns:
        configparser.ConfigParser: Profile with new node written to it. Returns None on fail.
    """
    less = ['global_options', 'output_device', 'output_stream']

    if section_name in parser.sections():
        logging.error(f'{section_name} already found in profile! Cannot overwrite section!')
        return

    if (node_stream not in ['audio', 'video']) and (node_type not in less):
        logging.error(f'Unknown stream {node_stream}! Skipping {section_name}!')

    check = [s for s in parser.sections() if (parser[s]['stream'] == node_stream) and
                   (parser[s]['type'] not in less)]

    if node_layer is None:
        if (node_type in less) or (len(check) == 0):
            node_layer = 0
        else:
            node_layer = int(sorted([parser[s]['layer'] for s in check])[-1]) + 1

    inputs = []
    outputs = []
    for node in check:
        if parser[node]['type'] == 'filter':
            if parser.get(node, 'input_layer_string', fallback='') == '':
                logging.error(f'Removing filter {node}! Missing argument input_layer_string!')
                parser.remove_section(node)
                continue
            inputs.extend(filters.process_layer_string(parser.get(node, 'input_layer_string')))
            outputs.append(parser[node]['layer'])
            outputs.extend(filters.process_layer_string(parser.get(node, 'output_layer_string',
                                                                   fallback='')))
        else:
            try:
                outputs.append(parser.getint(node, 'layer'))
            except ValueError:
                logging.error(f'Invalid layer value for {node}!')
                logging.info(traceback.format_exc())

    logging.debug(f'Populated input layers: {inputs}.')
    logging.debug(f'Populated output layers: {outputs}.')

    has_argument = lambda arg_name: arg_name in kwargs
    has_arg = lambda arg_name, arg_str: arg_name in filters.process_argument_string(arg_str)
    def check_registry(registry):
        result = node_name in registry
        if not result:
            logging.error(f'Unknown node name {node_name}! Skipping {node_type} {section_name}!')
        return result

    flag = base_type_dict()[node_type]._flag
    if flag == utils.FfSpec.FILTER:
        if node_name == 'other-filter':
            for argument_name in ['argument_string', 'input_layer_string']:
                if not has_argument(argument_name):
                    logging.error((f'Skipped {node_type} {section_name}! Argument {argument_name} '
                                   'is required!'))
                    return
            if not has_arg('filter_name', kwargs['argument_string']):
                logging.error(('Argument \'filter_name\' in argument_string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
        else:
            if not has_argument('input_layer_string'):
                logging.error((f'Skipped {node_type} {section_name}! Argument input_layer_string '
                               'is required!'))
                return

        filter_inputs = filters.process_layer_string(kwargs['input_layer_string'])
        filter_outputs = filters.process_layer_string(kwargs.get('output_layer_string', ''))
        filter_outputs.append(node_layer)

        for layer, count in collections.Counter(filter_inputs).items():
            if layer in inputs or count > 1:
                logging.error(f'Cannot write {node_type} {section_name}! Input collision!')
                logging.info(f'Found \'{layer}\' {count} times!')
                return

        for layer, count in collections.Counter(filter_outputs).items():
            if layer in outputs or count > 1:
                logging.error(f'Cannot write {node_type} {section_name}! Output collision!')
                logging.info(f'Found \'{layer}\' {count} times!')
                return

        if not check_registry(base_type_dict()[node_type].retrieve_registry()):
            return
    elif flag == utils.FfSpec.GLOBAL:
        if len([s for s in parser.sections() if parser[s]['type'] == 'global_options']) > 0:
            logging.error('Global options already found in profile! Cannot overwrite section!')
            return
    elif flag == utils.FfSpec.INPUT:
        if node_name == 'other-audio-device':
            if not has_argument('card'):
                logging.error((f'Skipped {node_type} {section_name}! Argument card is '
                               'required!'))
                return
            elif not has_arg('device_name', kwargs['card']):
                logging.error(('Argument \'device_name\' in card argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
            elif not has_arg('filename', kwargs['card']):
                logging.error(('Argument \'filename\' in card argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
        elif node_name == 'other-video-device':
            if not has_argument('display'):
                logging.error((f'Skipped {node_type} {section_name}! Argument display is '
                               'required!'))
                return
            elif not has_arg('device_name', kwargs['display']):
                logging.error(('Argument \'device_name\' in display argument string is required '
                               f'for {node_name}, skipping {section_name}!'))
                return
            elif not has_arg('filename', kwargs['display']):
                logging.error(('Argument \'filename\' in display argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
        if node_type == 'input_stream':
            if not has_argument('filename'):
                logging.error((f'Skipped {node_type} {section_name}! Argument filename is '
                               'required!'))
                return
        if node_layer in outputs:
            logging.error(f'Cannot write {node_type} {section_name}! Layer collision!')
            return
        if not check_registry({**base_type_dict()['input_stream'].retrieve_registry(),
                               **input_devices.AudioInputDevice.retrieve_registry(),
                               **input_devices.VideoInputDevice.retrieve_registry()}):
            return
    elif flag == utils.FfSpec.OUTPUT:
        if node_name == 'other-audio-device':
            if not has_argument('card'):
                logging.error((f'Skipped {node_type} {section_name}! Argument card is '
                               'required!'))
                return
            elif not has_arg('device_name', kwargs['card']):
                logging.error(('Argument \'device_name\' in card argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
            elif not has_arg('filename', kwargs['card']):
                logging.error(('Argument \'filename\' in card argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
        elif node_name == 'other-video-device':
            if not has_argument('display'):
                logging.error((f'Skipped {node_type} {section_name}! Argument display is '
                               'required!'))
                return
            elif not has_arg('device_name', kwargs['display']):
                logging.error(('Argument \'device_name\' in display argument string is required '
                               f'for {node_name}, skipping {section_name}!'))
                return
            elif not has_arg('filename', kwargs['display']):
                logging.error(('Argument \'filename\' in display argument string is required for '
                               f'{node_name}, skipping {section_name}!'))
                return
        if node_type == 'output_stream':
            if not has_argument('filename'):
                logging.error((f'Skipped {node_type} {section_name}! Argument filename is '
                               'required!'))
                return

        if not check_registry({**base_type_dict()['output_stream'].retrieve_registry(),
                               **output_devices.AudioOutputDevice.retrieve_registry(),
                               **output_devices.VideoOutputDevice.retrieve_registry()}):
            return

    element = {'stream' : node_stream, 'layer' : node_layer, 'name' : node_name,
               'type' : node_type}
    parser[section_name] = {key:str(val) for key, val in {**kwargs, **element}.items()}

    return parser

def generate_ffmpeg_node_structure(parser):
    """Convert a profile config parser to a FFmpeg node structure.

    Args:
        parser (configparser.ConfigParser): Profile config parser, see
            :func:`simple_capture.config.io.read_config`.

    Returns:
        tuple(ffmpeg.nodes.OutputStream, bool): FFmpeg node structure as well as a boolean flag to
            indicate whether 'sudo' should be used, if found in a global_options section of a
            profile, e.g. when using kmsgrab. Returns None on fail.
    """
    type_getters = {bool : parser.getboolean, float : parser.getfloat,
                    int : parser.getint}
    create_stream = lambda: {'inputs' : {}, 'filters' : {}}
    stream_dict = {'audio' : create_stream(),
                   'video' : create_stream()}
    outputs = []
    global_option = None
    audio_structure = None
    video_structure = None

    def get_options(node_name):
        options = parser.options(node_name)
        for unwanted in 'name', 'type', 'layer', 'stream':
            try:
                options.remove(unwanted)
            except ValueError:
                pass

        return options

    def create_node(element, *args, **kwargs):
        factory = factory_type_dict()[element['type']]
        parameters = parameter_type_dict()[element['type']]

        try:
            kwargs.update({option:type_getters.setdefault(parameters()[option], parser.get)
                           (element['node'], option) for option in get_options(element['node'])})
        except: # pylint:disable=bare-except
            logging.error(f'Unable to instantiate node {element["node"]} with arguments {kwargs}!')
            logging.info(traceback.format_exc())

            return

        try:
            node = factory(element['name'], *args, **kwargs)
        except: # pylint:disable=bare-except
            logging.error(f'Unable to instantiate node {element["node"]} with arguments {kwargs}!')
            logging.info(traceback.format_exc())

            return
        if node is None:
            logging.warning((f'Node {element["node"]} has not been instantiated'))

        return node

    def preprocess_filters(stream):
        new_filters = {}
        all_inputs = []
        all_outputs = list(stream['inputs'])
        for layer, filter_element in stream['filters'].items():
            skip = False
            logging.debug(f'Preprocessing filter {filter_element["node"]} (layer={layer}).')
            inputs = parser.get(filter_element['node'], 'input_layer_string', fallback='')
            logging.debug(f'Input layer string: {inputs}.')
            inputs = filters.process_layer_string(inputs)
            logging.info(f'Input layers: {inputs}.')
            if len(inputs) == 0:
                logging.warning((f'No input layers found for node {filter_element["node"]}, '
                                 'removing!'))
                continue
            for input_layer in inputs:
                if input_layer in all_inputs:
                    logging.warning(f'Removing node {filter_element["node"]}, input collision!')
                    skip = True
            outputs = parser.get(filter_element['node'], 'output_layer_string', fallback='')
            logging.debug(f'Output layer string: {outputs}.')
            outputs = filters.process_layer_string(outputs)
            outputs.append(layer)
            logging.info(f'Output layers: {outputs}.')
            for output_layer in outputs:
               if output_layer in all_outputs:
                    logging.warning(f'Removing node {filter_element["node"]}, output collision!')
                    skip = True
            if skip:
                all_inputs.extend(outputs)
                all_outputs.extend(inputs)
            all_inputs.extend(inputs)
            all_outputs.extend(outputs)
            if skip:
                continue
            new_filters[layer] = filter_element

        stream['filters'] = new_filters

    def process_filters(stream):
        new_filters = stream['filters'].copy()
        for layer, filter_element in stream['filters'].items():
            logging.debug(f'Processing filter {filter_element["node"]} (layer={layer}).')
            inputs = parser.get(filter_element['node'], 'input_layer_string')
            logging.debug(f'Input layer string: {inputs}.')
            inputs = filters.process_layer_string(inputs)
            logging.info(f'Input layers: {inputs}.')
            if all([i in stream['inputs'] for i in inputs]):
                filter_ = create_node(filter_element, stream['inputs'])
                logging.info(f'Instantiated filter {filter_element["node"]} (layer={layer})!')
                new_filters.pop(layer)
                if filter_ is None:
                    continue

                filter_ffmpeg, filter_outputs, _ = filter_
                for i in inputs:
                    stream['inputs'].pop(i)
                stream['inputs'][layer] = filter_ffmpeg
                stream['inputs'].update(filter_outputs)
                logging.debug(f'Current inputs: {stream["inputs"]}')

        stream['filters'] = new_filters
        logging.debug(f'Remaining filters: {stream["filters"]}.')
        logging.debug(f'Current inputs: {stream["inputs"]}.')
        if len(new_filters) > 0:
            process_filters(stream)

    for section_name in parser.sections():
        logging.info(f'Looking through node \'{section_name}\'.')

        section = parser[section_name]

        element_name = section.get('name', fallback='')
        element_type = section.get('type', fallback='')
        element_stream = section.get('stream', fallback='')
        element_layer = section.getint('layer', fallback=-1)
        element = {'node' : section_name, 'name' : element_name, 'type' : element_type,
                   'layer' : element_layer, 'stream' : element_stream}

        logging.debug((f'Section details: (name={element_name}, type={element_type}, layer='
                      f'{element_layer}, stream={element_stream}).'))

        if element_name == '' or element_type == '' or element_stream == '' or element_layer == -1:
            logging.warning(f'Skipping section {section_name}! Insufficient metadata.')
            continue

        if element_stream not in ['audio', 'video']:
            logging.warning(f'Skipping section {section_name}! Incorrect metadata.')
            continue

        del element_name, element_type, element_layer, element_stream

        flag = base_type_dict().get(element['type'], utils.NoType)._flag
        stream = stream_dict.get(element['stream'], 'video')
        if flag == utils.FfSpec.FILTER:
            stream['filters'][element['layer']] = element
        elif flag == utils.FfSpec.GLOBAL:
            if global_option is None:
                global_option = element
            else:
                logging.warning(f'Skipping section {section_name}! Global options already found.')
                continue
        elif flag == utils.FfSpec.INPUT:
            stream['inputs'][element['layer']] = create_node(element)
        elif flag == utils.FfSpec.OUTPUT:
            outputs.append(element)
        else:
            logging.warning(f'Unable to determine specifier of type \'{element["type"]}\'!')

    for stream in stream_dict.values():
        preprocess_filters(stream)
        try:
            process_filters(stream)
        except RecursionError:
            logging.error(f'Unable to process filters!')
            logging.info(traceback.format_exc())
        logging.debug(f'Foremost layers: {list(stream["inputs"])}.')
        # check_disjoint(stream_name)

    #if len(stream_dict['video']['inputs']) == 1:
    #    video_structure = list(stream_dict['video']['inputs'].values())[0]
    if len(stream_dict['audio']['inputs']) == 1:
        audio_structure = list(stream_dict['audio']['inputs'].values())[0]

    for layer, input_node in stream_dict['video']['inputs'].items():
        if video_structure is None:
            video_structure = input_node
            logging.debug(f'Video structure has been set to node {input_node}(layer={layer})!')
            continue
        result = filters.generate_filter('overlay', {0:video_structure, 1:input_node},
                                         input_layer_string='0,1')
        if result is not None:
            video_structure, _, _ = result

    if audio_structure is None:
        inputs = stream_dict['audio']['inputs']
        input_layer_string = ','.join((str(i) for i in range(len(inputs))))
        result = filters.generate_filter('amix',
                                         {i:layer for i, layer in enumerate(inputs.values())},
                                         argument_string=f'input_count={len(inputs)}',
                                         input_layer_string=input_layer_string)
        if result is not None:
            audio_structure, _, _ = result
    
    structures = []
    if audio_structure is not None:
        structures.append(audio_structure.filter_multi_output('asplit'))
    if video_structure is not None:
        structures.append(video_structure.filter_multi_output('split'))

    output_nodes = []
    for i, output in enumerate(outputs):            
        output_nodes.append(create_node(output, *[structure[i] for structure in structures]))

    output_nodes = [node for node in output_nodes if node is not None]

    if len(output_nodes) == 0:
       logging.error('Unable to generate ffmpeg node structure! No outputs!')
       return None, False

    node_structure = ffmpeg.merge_outputs(*output_nodes)
    if global_option is not None:
        global_node = create_node(global_option, node_structure)
        if global_node is not None:
            logging.info(f'Applied global options to node structure!')
            return global_node, 'sudo' in get_options(global_option['node'])
        logging.error(f'Failed to apply global options to node structure!')

    return node_structure, False 
