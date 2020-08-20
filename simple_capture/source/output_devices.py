"""Contains classes to define FFmpeg output devices, as well as generic output device classes,
:class:`OtherAudioDevice` and :class`OtherVideoDevice` to support for any FFmpeg output device.
"""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_output_device',
           'output_device_parameters',
           'register_audio_output_device',
           'register_video_output_device',
           'audio_output_device',
           'video_output_device',
           'OutputDevice',
           'AudioOutputDevice',
           'VideoOutputDevice',
           'Alsa',
           'AudioToolbox',
           'OpenGl',
           'OtherAudioDevice',
           'OtherVideoDevice',
           'Sdl',
           'Video4Linux2',
           'XVideo']

import abc
import functools
import logging
import traceback

from simple_capture.source import devices, filters
from simple_capture import utils

import ffmpeg


def output_device_parameters():
    """Helper function to read arguments from a config file to create a node.

    Returns:
        dict(str, type): A dictionary of the types of the arguments of
            :class:`simple_capture.source.output_devices.AudioOutputDevice`, and
            :class:`simple_capture.source.output_devices.VideoOutputDevice`. Used to instruct
            :func:`simple_capture.config.io.generate_ffmpeg_node_structure` how to collect
            arguments from a config file.
    """
    return {'card' : str, 'display' : str}

class OutputDevice(devices.Device, metaclass=abc.ABCMeta, device_name='',
                   spec=utils.FfSpec.OUTPUT):
    """Output device base class."""
    def __init_subclass__(cls, device_name, device_type, **kwargs):
        super().__init_subclass__(spec=cls._flag, device_name=device_name, device_type=device_type,
                                  **kwargs)
        logging.info((f'OutputDevice {cls} found with name {cls.device_name} and type '
                      f'{cls.device_type}!'))

class AudioOutputDevice(OutputDevice, metaclass=abc.ABCMeta, device_type=devices.DeviceType.AUDIO,
                        device_name=''):
    """Audio output device base class.

    Args:
        card (str): Device identifier.
    """
    _audio_output_device_registry = {}

    @abc.abstractmethod
    def __init__(self, card):
        super().__init__(card=card)

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device}

    def __init_subclass__(cls, device_name, **kwargs):
        super().__init_subclass__(device_name=device_name, device_type=cls.device_type, **kwargs)
        cls.retrieve_registry()[device_name] = cls
        if cls.device_type != devices.DeviceType.AUDIO:
            logging.warning(f'Invalid device type {cls.device_type} for AudioOutputDevice!')
        logging.debug(f'Found AudioOutputDevices: {cls.retrieve_registry()}.')

    @classmethod
    def retrieve_registry(cls):
        return cls._audio_output_device_registry

class VideoOutputDevice(OutputDevice, metaclass=abc.ABCMeta, device_type=devices.DeviceType.VIDEO,
                        device_name=''):
    """Video output device base class.

    Args:
        display (str): Device identifier.
    """
    _video_output_device_registry = {}

    @abc.abstractmethod
    def __init__(self, display):
        super().__init__(display=display)

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device}

    def __init_subclass__(cls, device_name, **kwargs):
        super().__init_subclass__(device_name=device_name, device_type=cls.device_type, **kwargs)
        cls.retrieve_registry()[device_name] = cls
        if cls.device_type != devices.DeviceType.VIDEO:
            logging.warning(f'Invalid device type {cls.device_type} for VideoOutputDevice!')
        logging.debug(f'Found VideoOutputDevices: {cls.retrieve_registry()}.')

    @classmethod
    def retrieve_registry(cls):
        return cls._video_output_device_registry

def audio_output_device(cls):
    """Decorator to register an audio output device. The key is
    :attr:`simple_capture.source.devices.Device.device_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return devices.device(AudioOutputDevice)(cls)

def video_output_device(cls):
    """Decorator to register an video output device. The key is
    :attr:`simple_capture.source.devices.Device.device_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return devices.device(VideoOutputDevice)(cls)

register_audio_output_device = functools.partial(devices.register_device, AudioOutputDevice)
register_video_output_device = functools.partial(devices.register_device, VideoOutputDevice)

class Alsa(AudioOutputDevice, device_name='alsa'):
    """FFmpeg audio output device 'alsa' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#alsa-1 for more information. Use the command 'arecord
    -l' to list all available ALSA devices.

    Args:
        card (:obj:`str`, optional): Device identifier in the form 'hw:card[,device[,subdevice]]',
            where card, device, and subdevice are integer indexes starting from 0. Defaults to
            'hw:0'.
    """
    def __init__(self, card='hw:0'):
        super().__init__(card=card)
        self._device = card 

    @property
    def device(self):
        return self._device

    @classmethod
    def help(cls):
        return """'alsa' audio output device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#alsa-1'.
               Use the command 'arecord -l' to list all available ALSA devices.

               CARD: Device identifier in the form 'hw:card[,device[,subdevice]]', where card,
               device, and subdevice are integer indexes starting from 0. Defaults to 'hw:0'.
               """

class AudioToolbox(AudioOutputDevice, device_name='audiotoolbox'):
    """FFmpeg audio input device 'avfoundation' for macOS systems. See
    https://ffmpeg.org/ffmpeg-devices.html#AudioToolbox for more information.

    Args:
        card (:obj:`str`, optional): Device identifier as an integer index. Defaults to '0'.
    """
    def __init__(self, card='0'):
        self._ffmpeg_arguments = {'filename' : '-', 'audio_device_index' : card}

    @property
    def device(self):
        return self._ffmpeg_arguments['audio_device_index']

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """'audiotoolbox' audio output device for macOS systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#AudioToolbox'.

               CARD: Device identifier as an integer index.
               """

class OpenGl(VideoOutputDevice, device_name='opengl'):
    """FFmpeg output device 'opengl'. See 'https://ffmpeg.org/ffmpeg-devices.html#opengl' for more
    information.

    Args:
        display (:obj:`str`, optional): Specify a semicolon separated list of keyword arguments in
            the form 'KWD=VAL;KWD2=VAL2...'.
    """
    def __init__(self, display='window_title=Window'):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        self._options = ['background', 'no_window', 'window_title', 'window_size']
        for ffmpeg_argument in self._ffmpeg_arguments:
            if ffmpeg_argument not in self._options:
                logging.warning(f'Unknown argument {ffmpeg_argument}, skipping!')
                self._ffmpeg_arguments.pop(ffmpeg_argument)
        self._ffmpeg_arguments['filename'] = 'Window'

    @property
    def device(self):
        return self.ffmpeg_arguments.get('window_title', self.ffmpeg_arguments['filename'])

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """'opengl' video output device.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#opengl'.

               DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'.
               """

class OtherAudioDevice(AudioOutputDevice, device_name='other-audio-device'):
    """Generic FFmpeg audio output device. See https://ffmpeg.org/ffmpeg-devices.html for more
    information.

    Args:
        card (str): Specify a semicolon separated list of keyword arguments in the form
            'KWD=VAL;KWD2=VAL2...'.
    """
    def __init__(self, card):
        self._ffmpeg_arguments = filters.process_argument_string(card)
        if 'filename' not in self._ffmpeg_arguments:
            logging.warning(('Output source for output device not defined! Use the keyword '
                             'argument filename to define an output source! Defaulting to \'-\'.'))
            self._ffmpeg_arguments['filename'] = '-'
        elif 'device_name' not in self._ffmpeg_arguments:
            logging.warning(('Device name (\'-f\' option for ffmpeg) for output device not defined'
                             '! Use the keyword argument device_name to define a device_name! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['device_name'] = '-'
        self.device_name = self._ffmpeg_arguments['device_name']
        self._ffmpeg_arguments.pop('device_name')

    @property
    def device(self):
        return self.ffmpeg_arguments['filename']

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """Generic audio output device type.
               'device_name' and 'filename' must be specified in the card argument string.

                DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'. 
               """

class OtherVideoDevice(VideoOutputDevice, device_name='other-video-device'):
    """Generic FFmpeg video output device. See https://ffmpeg.org/ffmpeg-devices.html for more
    information.

    Args:
        display (str): Specify a semicolon separated list of keyword arguments in the form
            'KWD=VAL;KWD2=VAL2...'.
    """
    def __init__(self, display):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        if 'filename' not in self._ffmpeg_arguments:
            logging.warning(('Output source for output device not defined! Use the keyword '
                             'argument filename to define an output source! Defaulting to \'-\'.'))
            self._ffmpeg_arguments['filename'] = '-'
        elif 'device_name' not in self._ffmpeg_arguments:
            logging.warning(('Device name (\'-f\' option for ffmpeg) for output device not defined'
                             '! Use the keyword argument device_name to define a device_name! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['device_name'] = '-'
        self.device_name = self._ffmpeg_arguments['device_name']
        self._ffmpeg_arguments.pop('device_name')

    @property
    def device(self):
        return self.ffmpeg_arguments['filename']

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """Generic video output device type.
               'device_name' and 'filename' must be specified in the display argument string.

                DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'. 
               """

class PulseAudio(AudioOutputDevice, device_name='pulse'):
    """FFmpeg audio output device 'alsa' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#pulse-1 for more information. Use the command 'pactl
    list sinks' to list all available PulseAudio devices.

    Args:
        card (:obj:`str`, optional): Device identifier as an integer index. Defaults to 'default'.
    """
    def __init__(self, card='default'):
        super().__init__(card=card)
        self._device = card 

    @property
    def device(self):
        return self._device

    @classmethod
    def help(cls):
        return """'pulse' audio output device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#pulse-1'.
               Use the command 'pactl list sinks' to list all available PulseAudio devices.

               CARD: Device identifier as an integer index. Defaults to 'default'.
               """

@register_video_output_device(name='sdl2')
class Sdl(VideoOutputDevice, device_name='sdl'):
    """FFmpeg output device 'sdl'. See 'https://ffmpeg.org/ffmpeg-devices.html#sdl' for more
    information.

    Args:
        display (:obj:`str`, optional): Specify a semicolon separated list of keyword arguments in
            the form 'KWD=VAL;KWD2=VAL2...'.
    """
    def __init__(self, display='window_title=Window'):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        self._options = ['window_fullscreen', 'icon_title', 'window_title', 'window_size',
                         'window_x', 'window_y', 'window_enable_quit']
        for ffmpeg_argument in self._ffmpeg_arguments:
            if ffmpeg_argument not in self._options:
                logging.warning(f'Unknown argument {ffmpeg_argument}, skipping!')
                self._ffmpeg_arguments.pop(ffmpeg_argument)
        self._ffmpeg_arguments['filename'] = 'Window'

    @property
    def device(self):
        return self.ffmpeg_arguments.get('window_title', self.ffmpeg_arguments['filename'])

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """'sdl' video output device. 'sdl2' is an alias.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#sdl'.

               DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'.
               """


@register_video_output_device(name='video4linux2,v4l2')
@register_video_output_device(name='v4l2')
class Video4Linux2(VideoOutputDevice, device_name='video4linux2'):
    """FFmpeg video output device 'v4l2' for GNU/Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#v4l2 for more information. Use the command 'v4l2-ctl
    --list-devices' to list all available Video4Linux2 devices.

    Args:
        display (:obj:`str`, optional): Device identifier as a file path. Defaults to '/dev/video0'.
    """
    def __init__(self, display='/dev/video0'):
        self._device = display

    @property
    def device(self):
        return self._device

    @classmethod
    def help(cls):
        return """'video4linux2' video output device for Linux systems. 'v4l2' and
               'video4linux2,v4l2' are aliases.
               Official documentation:
               'https://ffmpeg.org/ffmpeg-devices.html#v4l2'.
               Use the command 'v4l2-ctl --list-devices' to list all available Video4Linux2
               devices.

               DISPLAY: Device identifier as a file path. Defaults to '/dev/video0'.
               """
class XVideo(VideoOutputDevice, device_name='xv'):
    """FFmpeg video output device 'xv' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#xv for more information. Use the command 'xdpyinfo' to
    list information about your display.

    Args:
        display (:obj:`str`, optional): Device identifier in the form
            '[hostname]:display_number[.screen_number][+x_offset,[y_offset]]'. Defaults to ':0.0'.
            The environment variable 'DISPLAY' returns your default display.
    """
    def __init__(self, display=':0.0'):
        super().__init__(display=display)
        self._device = display 

    @property
    def device(self):
        return self._device

    @classmethod
    def help(cls):
        return """'xv' video output device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#xv'.
               Use the command 'xdpyinfo' to list information about your display.

               DISPLAY: Device identifier in the form
               '[hostname]:display_number[.screen_number][+x_offset,[y_offset]]'.
               Defaults to ':0.0'. The environment variable 'DISPLAY' returns your default display.
               """

def generate_output_device(name, *args, **kwargs):
    """Creates the FFmpeg output device node.

    Args:
        name (str): Name of the output device in the
            :meth:`simple_capture.source.output_device.AudioOutputDevice.retrieve_registry`, or the
            :meth:`simple_capture.source.output_device.VideoOutputDevice.retrieve_registry`.
        *args: Input streams.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.output_device.OutputDevice` or any of its subclasses.

    Returns:
        ffmpeg.nodes.OutputStream: Output device stream.
    """
    output_device_registry = {**AudioOutputDevice.retrieve_registry(),
                              **VideoOutputDevice.retrieve_registry()}

    if (AudioOutputDevice.retrieve_registry().get(name) and
        VideoOutputDevice.retrieve_registry().get(name)):
        logging.warning(f'Device name {name} found in both registries!')
        try:
            device = AudioOutputDevice.retrieve_registry()[name](**kwargs)
        except TypeError:
            logging.error(f'Device  {name} failed audio due to keyword arguments {kwargs}.')
            logging.info(traceback.format_exc())
            try:
                device = VideoOutputDevice.retrieve_registry()[name](**kwargs)
            except TypeError:
                logging.error(f'Device  {name} failed video due to keyword arguments {kwargs}.')
                logging.info(traceback.format_exc())

        logging.error((f'Unable to find device {name}! No device instantiated with keyword '
                       f'arguments {kwargs}.'))

        return None
    else:
        device = output_device_registry[name](**kwargs)

    logging.info((f'Instantiated device {device.device_name} of type {device.device_type} with '
                  f'ffmpeg arguments {device.ffmpeg_arguments} and keyword arguments {kwargs}.'))

    return ffmpeg.output(*args, format=device.device_name, **device.ffmpeg_arguments)
