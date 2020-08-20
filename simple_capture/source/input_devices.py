"""Contains classes to define FFmpeg input devices, as well as generic input device classes,
:class:`OtherAudioDevice` and :class`OtherVideoDevice` to support for any FFmpeg input device.
"""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_input_device',
           'input_device_parameters',
           'register_audio_input_device',
           'register_video_input_device',
           'audio_input_device',
           'video_input_device',
           'InputDevice',
           'AudioInputDevice',
           'VideoInputDevice',
           'Alsa',
           'AvFoundationAudio',
           'AvFoundationVideo',
           'DirectShowAudio',
           'DirectShowVideo',
           'GdiGrab',
           'KmsGrab',
           'OpenAl',
           'OtherAudioDevice',
           'OtherVideoDevice',
           'PulseAudio',
           'Video4Linux2',
           'X11Grab']

import abc
import enum
import functools
import logging
import traceback

from simple_capture.source import devices, filters
from simple_capture import utils

import ffmpeg


def input_device_parameters():
    """Helper function to read arguments from a config file to create a node.

    Returns:
        dict(str, type): A dictionary of the types of the arguments of
            :class:`simple_capture.source.input_devices.AudioInputDevice`, and
            :class:`simple_capture.source.input_devices.VideoInputDevice`. Used to instruct
            :func:`simple_capture.config.io.generate_ffmpeg_node_structure` how to collect
            arguments from a config file.
    """
    return {'sample_rate' : int, 'channels' : int, 'card' : str,
            'video_size' : str, 'framerate' : float, 'draw_mouse' : bool, 'display' : str}

class InputDevice(devices.Device, metaclass=abc.ABCMeta, device_name='', spec=utils.FfSpec.INPUT):
    """Input device base class."""
    def __init_subclass__(cls, device_name, device_type, **kwargs):
        super().__init_subclass__(spec=cls._flag, device_name=device_name, device_type=device_type,
                                  **kwargs)
        logging.info((f'InputDevice {cls} found with name {cls.device_name} and type '
                      f'{cls.device_type}!'))

class AudioInputDevice(InputDevice, metaclass=abc.ABCMeta, device_type=devices.DeviceType.AUDIO,
                       device_name=''):
    """Audio input device base class.

    Args:
        card (str): Device identifier.
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
    """
    _audio_input_device_registry = {}

    @abc.abstractmethod
    def __init__(self, card, sample_rate=48000, channels=2):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)

    @property
    @abc.abstractmethod
    def sample_rate(self):
        """int: Sample rate of audio capture in Hz."""

    @property
    @abc.abstractmethod
    def channels(self):
        """int: Number of audio channels. """

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device, 'sample_rate' : self.sample_rate,
                'channels' : self.channels}

    def __init_subclass__(cls, device_name, **kwargs):
        super().__init_subclass__(device_name=device_name, device_type=cls.device_type, **kwargs)
        cls.retrieve_registry()[device_name] = cls
        if cls.device_type != devices.DeviceType.AUDIO:
            logging.warning(f'Invalid device type {cls.device_type} for AudioInputDevice!')
        logging.debug(f'Found AudioInputDevices: {cls.retrieve_registry()}.')

    @classmethod
    def retrieve_registry(cls):
        return cls._audio_input_device_registry

class VideoInputDevice(InputDevice, metaclass=abc.ABCMeta, device_type=devices.DeviceType.VIDEO,
                       device_name=''):
    """Video input device base class.

    Args:
        display (str): Device identifier. Defaults to None.
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True.
    """
    _video_input_device_registry = {}

    @abc.abstractmethod
    def __init__(self, display, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)

    @property
    @abc.abstractmethod
    def video_size(self):
        """str: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is height."""

    @property
    @abc.abstractmethod
    def framerate(self):
        """float:  Desired framerate of capture."""

    @property
    @abc.abstractmethod
    def draw_mouse(self):
        """bool: Draw mouse cursor on capture."""

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device, 's' : self.video_size,
                'framerate' : self.framerate, 'draw_mouse' : self.draw_mouse}

    def __init_subclass__(cls, device_name, **kwargs):
        super().__init_subclass__(device_name=device_name, device_type=cls.device_type, **kwargs)
        cls.retrieve_registry()[device_name] = cls
        if cls.device_type != devices.DeviceType.VIDEO:
            logging.warning(f'Invalid device type {cls.device_type} for VideoInputDevice!')
        logging.debug(f'Found VideoInputDevices: {cls.retrieve_registry()}.')

    @classmethod
    def retrieve_registry(cls):
        return cls._video_input_device_registry

def audio_input_device(cls):
    """Decorator to register an audio input device. The key is
    :attr:`simple_capture.source.devices.Device.device_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return devices.device(AudioInputDevice)(cls)

def video_input_device(cls):
    """Decorator to register an video input device. The key is
    :attr:`simple_capture.source.devices.Device.device_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return devices.device(VideoInputDevice)(cls)

register_audio_input_device = functools.partial(devices.register_device, AudioInputDevice)
register_video_input_device = functools.partial(devices.register_device, VideoInputDevice)

class Alsa(AudioInputDevice, device_name='alsa'):
    """FFmpeg audio input device 'alsa' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#alsa for more information. Use the command 'arecord -l'
    to list all available ALSA devices.

    Args:
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
        card (:obj:`str`, optional): Device identifier in the form 'hw:card[,device[,subdevice]]',
            where card, device, and subdevice are integer indexes starting from 0. Defaults to
            'hw:0'.
    """
    def __init__(self, sample_rate=48000, channels=2, card='hw:0'):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)
        self._device = card
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def device(self):
        return self._device

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channels(self):
        return self._channels

    @classmethod
    def help(cls):
        return """'alsa' audio input device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#alsa'.
               Use the command 'arecord -l' to list all available ALSA devices.

               SAMPLE_RATE: Sample rate of audio capture in Hz. Defaults to 48000.

               CHANNELS: Number of audio channels. Defaults to 2.

               CARD: Device identifier in the form 'hw:card[,device[,subdevice]]', where card,
               device, and subdevice are integer indexes starting from 0. Defaults to 'hw:0'.
               """

class AvFoundationAudio(AudioInputDevice, device_name='avfoundation'):
    """FFmpeg audio input device 'avfoundation' for macOS systems. See
    https://ffmpeg.org/ffmpeg-devices.html#avfoundation for more information. Use the command
    'ffmpeg -f avfoundation -list_devices true -i ""' to list all available AVFoundation devices.

    Args:
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
        card (:obj:`str`, optional): Device identifier as an integer index. Defaults to 'default'.
    """
    def __init__(self, sample_rate=48000, channels=2, card='default'):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)
        self._device = card
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def device(self):
        return self._device

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channels(self):
        return self._channels

    @classmethod
    def help(cls):
        return """'avfoundation' audio input device for macOS systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#avfoundation'.
               Use the command 'ffmpeg -f avfoundation -list_devices true -i ""' to list all
               available AVFoundation devices

               SAMPLE_RATE: Sample rate of audio capture in Hz. Defaults to 48000.

               CHANNELS: Number of audio channels. Defaults to 2.

               CARD: Device identifier as an integer index. Defaults to 'default'.
               """

class AvFoundationVideo(VideoInputDevice, device_name='avfoundation'):
    """FFmpeg video input device 'avfoundation' for macOS systems. See
    https://ffmpeg.org/ffmpeg-devices.html#avfoundation for more information. Use the command
    'ffmpeg -f avfoundation -list_devices true -i ""' to list all available AVFoundation devices.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True.
        display (:obj:`str1, optional): Device identifier as an integer index. Defaults to
            'default'.
    """
    def __init__(self, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True,
                 display='default'):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)
        self._device = display
        self._video_size = video_size
        self._framerate = framerate
        self._capture_cursor = int(draw_mouse)

    @property
    def device(self):
        return self._device

    @property
    def video_size(self):
        return self._video_size

    @property
    def framerate(self):
        return self._framerate

    @property
    def draw_mouse(self):
        return self._capture_cursor

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device, 's' : self.video_size,
                'framerate' : self.framerate, 'capture_cursor' : self.draw_mouse}

    @classmethod
    def help(cls):
        return """'avfoundation' video input device for macOS systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#avfoundation'.
               Use the command 'ffmpeg -f avfoundation -list_devices true -i ""' to list all
               available AVFoundation devices.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is
               height. Defaults to fullscreen.

               FRAMERATE: Desired framerate of capture. Defaults to 'ntsc' ~= 29.97.

               DRAW_MOUSE: Draw mouse on capture. Defaults to true.

               DISPLAY: Device identifier as an integer index. Defaults to 'default'.
               """

class DirectShowAudio(AudioInputDevice, device_name='dshow'):
    """FFmpeg video input device 'dshow' for Windows systems. See
    https://ffmpeg.org/ffmpeg-devices.html#dshow for more information. Use the command 'ffmpeg
    -list_devices true -f dshow -i dummy' to list all available DirectShow devices.

    Args:
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
        card (:obj:`str`, optional): Device identifier as a name. Defaults to
            'virtual-audio-capturer'.
    """
    def __init__(self, sample_rate=48000, channels=2, card='virtual-audio-capturer'):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)
        self._device = f'audio={card}'
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def device(self):
        return self._device

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channels(self):
        return self._channels

    @classmethod
    def help(cls):
        return """'dshow' audio input device for Windows systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#dshow'.
               Use the command 'ffmpeg -list_devices true -f dshow -i dummy' to list all available
               DirectShow devices

               SAMPLE_RATE: Sample rate of audio capture in Hz. Defaults to 48000.

               CHANNELS: Number of audio channels. Defaults to 2.

               CARD: Device identifier as a name. Defaults to 'virtual-audio-capturer'.
               """

class DirectShowVideo(VideoInputDevice, device_name='dshow'):
    """FFmpeg video input device 'dshow' for Windows systems. See
    https://ffmpeg.org/ffmpeg-devices.html#dshow for more information. Use the command 'ffmpeg
    -list_devices true -f dshow -i dummy' to list all available DirectShow devices.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True.
        display (:obj:`str`, optional): Device identifier as a name. Defaults to
            'screen-capture-recorder'.
    """
    def __init__(self, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True,
                 display='screen-capture-recorder'):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)
        self._device = f'video={display}'
        self._video_size = video_size
        self._framerate = framerate
        self._draw_mouse = int(draw_mouse)

    @property
    def device(self):
        return self._device

    @property
    def video_size(self):
        return self._video_size

    @property
    def framerate(self):
        return self._framerate

    @property
    def draw_mouse(self):
        return self._draw_mouse

    @classmethod
    def help(cls):
        return """'dshow' video input device for Windows systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#dshow'.
               Use the command 'ffmpeg -list_devices true -f dshow -i dummy' to list all available
               DirectShow devices.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is
               height. Defaults to fullscreen.

               FRAMERATE: Desired framerate of capture. Defaults to 'ntsc' ~= 29.97.

               DRAW_MOUSE: Draw mouse on capture. Defaults to true.

               DISPLAY: Device identifier as a name. Defaults to 'screen-capture-recorder'.
               """

class GdiGrab(VideoInputDevice, device_name='gdigrab'):
    """FFmpeg video input device 'gdigrab' for Windows systems. See
    https://ffmpeg.org/ffmpeg-devices.html#gdigrab for more information.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True.
        display (:obj:`str`, optional): Device identifier in the form 'window', where window is the
            title of the window to be captured, e.g. 'Calculator' or 'desktop' to capture screen
            regardless of window. Defaults to 'desktop'.

    """
    def __init__(self, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True,
                 display='desktop'):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)
        self._device = f'title={display}' if display != 'desktop' else display
        self._video_size = video_size
        self._framerate = framerate
        self._draw_mouse = int(draw_mouse)

    @property
    def device(self):
        return self._device

    @property
    def video_size(self):
        return self._video_size

    @property
    def framerate(self):
        return self._framerate

    @property
    def draw_mouse(self):
        return self._draw_mouse

    @classmethod
    def help(cls):
        return """'gdigrab' video input device for Windows systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#gdigrab'.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is
               height. Defaults to fullscreen.

               FRAMERATE: Desired framerate of capture. Defaults to 'ntsc' ~= 29.97.

               DRAW_MOUSE: Draw mouse on capture. Defaults to true.

               DISPLAY: Device identifier in the form 'window', where window is the title of the
               window to be captured, e.g. 'Calculator' or 'desktop' to capture screen regardless
               of window. Defaults to 'desktop'.
               """

class KmsGrab(VideoInputDevice, device_name='kmsgrab'):
    """FFmpeg video input device 'kmsgrab' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#kmsgrab for more information.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Ignored here. Use the 'crop' filter instead.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True. Ignored
            here.
        display (:obj:`str`, optional): Specify a semicolon separated list of keyword arguments in
            the form 'KWD=VAL;KWD2=VAL2...'.
    """
    def __init__(self, video_size=utils.resolution(), framerate=29.97, draw_mouse=True,
                 display='device=/dev/dri/card0'):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        self._options = ['device', 'format', 'format_modifier', 'plane_id', 'crtc_id']
        for ffmpeg_argument in self._ffmpeg_arguments:
            if ffmpeg_argument not in self._options:
                logging.warning(f'Unknown argument {ffmpeg_argument}, skipping!')
                self._ffmpeg_arguments.pop(ffmpeg_argument)
        self._ffmpeg_arguments['framerate'] = framerate
        self._ffmpeg_arguments['filename'] = '-'

    @property
    def device(self):
        return self.ffmpeg_arguments.get('device', '/dev/dri/card0')

    @property
    def video_size(self):
        return utils.resolution()

    @property
    def framerate(self):
        return self.ffmpeg_arguments['framerate'] 

    @property
    def draw_mouse(self):
        return True

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """'kmsgrab' video input device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#kmsgrab'.
               You may have to run simple_capture as root for this to work, or set CAP_SYS_ADMIN
               for FFmpeg, see https://ffmpeg.org/pipermail/ffmpeg-user/2018-June/040338.html,
               or just run 'sudo setcap cap_sys_admin+ep $(which ffmpeg)'. As well as the 'hwmap'
               (with derive_device=vaapi) and 'scale_vaapi' (with format='nv12') filters and a
               vaapi video codec, and in the display argument list, the crtc_id option set to 42
               for kmsgrab to function. See the examples in the official documentation.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width
               and 'h' is height. Ignored here. Use the 'crop' filter instead.

               FRAMERATE: Desired framerate of capture. Defaults to 29.97.

               DRAW_MOUSE: Draw mouse cursor on capture. Defaults to True. Ignored here.

               DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'.
               """

class LibAvFilter(VideoInputDevice, device_name='lavfi'):
    """FFmpeg input device 'lavfi'. See 'https://ffmpeg.org/ffmpeg-devices.html#lavfi' for more
    information. Use the command 'ffmpeg -filters' to list all available filters.

    Args:
        display (str): Specify a semicolon separated list of keyword arguments in the form
            'KWD=VAL;KWD2=VAL2...'.
        **kwargs: Arbitrary keyword arguments.
    """
    def __init__(self, display, **kwargs):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        self._options = ['graph', 'graph_file', 'dumpgraph']
        for ffmpeg_argument in self._ffmpeg_arguments:
            if ffmpeg_argument not in self._options:
                logging.warning(f'Unknown argument {ffmpeg_argument}, skipping!')
                self._ffmpeg_arguments.pop(ffmpeg_argument)
        self._ffmpeg_arguments['filename'] = self._ffmpeg_arguments['graph']
        self._ffmpeg_arguments.pop('graph')

    @property
    def device(self):
        return self.ffmpeg_arguments['filename']

    @property
    def video_size(self):
        return None

    @property
    def framerate(self):
        return None

    @property
    def draw_mouse(self):
        return None

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """'lavfi' input device.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#lavfi'.
               Use the command 'ffmpeg -filters' to list all available filters.
               'graph' must be specified in the display argument string.

                DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'.
               """

class OpenAl(AudioInputDevice, device_name='openal'):
    """FFmpeg audio input device 'openal'. See 'https://ffmpeg.org/ffmpeg-devices.html#openal' for
    more information. Use the command 'ffmpeg -list_devices true -f openal -i dummy out.ogg' to
    list all available OpenAL devices.

    Args:
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
        card (:obj:`str`, optional): Device identifier as a name. Defaults to ''.
    """
    def __init__(self, sample_rate=48000, channels=2, card=''):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)
        self._device = card
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def device(self):
        return self._device

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channels(self):
        return self._channels

    @classmethod
    def help(cls):
        return """'openal' audio input device.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#openal'.
               Use the command 'ffmpeg -list_devices true -f openal -i dummy out.ogg'
               to list all available OpenAL devices.

               SAMPLE_RATE: Sample rate of audio capture in Hz. Defaults to 48000.

               CHANNELS: Number of audio channels. Defaults to 2.

               CARD: Device identifier as a name. Defaults to ''.
               """

class OtherAudioDevice(AudioInputDevice, device_name='other-audio-device'):
    """Generic FFmpeg audio input device. See https://ffmpeg.org/ffmpeg-devices.html for more
    information.

    Args:
        card (str): Specify a semicolon separated list of keyword arguments in the form
            'KWD=VAL;KWD2=VAL2...'.
        **kwargs: Arbitrary keyword arguments.
    """
    def __init__(self, card, **kwargs):
        self._ffmpeg_arguments = filters.process_argument_string(card)
        if 'filename' not in self._ffmpeg_arguments:
            logging.warning(('Input source (\'-i\' option for ffmpeg) for input device not defined'
                             '! Use the keyword argument filename to define an input source! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['filename'] = '-'
        elif 'device_name' not in self._ffmpeg_arguments:
            logging.warning(('Device name (\'-f\' option for ffmpeg) for input device not defined!'
                             ' Use the keyword argument device_name to define a device_name! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['device_name'] = '-'
        self.device_name = self._ffmpeg_arguments['device_name']
        self._ffmpeg_arguments.pop('device_name')

    @property
    def device(self):
        return self.ffmpeg_arguments['filename']

    @property
    def sample_rate(self):
        return self.ffmpeg_arguments.get('sample_rate', -1)

    @property
    def channels(self):
        return self.ffmpeg_arguments.get('channels', -1)

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """Generic audio input device type.
               'device_name' and 'filename' must be specified in the card argument string.

               CARD: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'. 
               """

class OtherVideoDevice(VideoInputDevice, device_name='other-video-device'):
    """Generic FFmpeg video input device. See https://ffmpeg.org/ffmpeg-devices.html for more
    information.

    Args:
        display (str): Specify a semicolon separated list of keyword arguments in the form
            'KWD=VAL;KWD2=VAL2...'.
        **kwargs: Arbitrary keyword arguments.
    """
    def __init__(self, display, **kwargs):
        self._ffmpeg_arguments = filters.process_argument_string(display)
        if 'filename' not in self._ffmpeg_arguments:
            logging.warning(('Input source (\'-i\' option for ffmpeg) for input device not defined'
                             '! Use the keyword argument filename to define an input source! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['filename'] = '-'
        elif 'device_name' not in self._ffmpeg_arguments:
            logging.warning(('Device name (\'-f\' option for ffmpeg) for input device not defined!'
                             ' Use the keyword argument device_name to define a device_name! '
                             'Defaulting to \'-\'.'))
            self._ffmpeg_arguments['device_name'] = '-'
        self.device_name = self._ffmpeg_arguments['device_name']
        self._ffmpeg_arguments.pop('device_name')

    @property
    def device(self):
        return self.ffmpeg_arguments['filename']

    @property
    def video_size(self):
        return self.ffmpeg_arguments.get('video_size', -1)

    @property
    def framerate(self):
        return self.ffmpeg_arguments.get('framerate', -1)

    @property
    def draw_mouse(self):
        return self.ffmpeg_arguments.get('draw_mouse', -1)

    @property
    def ffmpeg_arguments(self):
        return self._ffmpeg_arguments

    @classmethod
    def help(cls):
        return """Generic video input device type.
               'device_name' and 'filename' must be specified in the display argument string.

                DISPLAY: Specify a semicolon separated list of keyword arguments in the form
               'KWD=VAL;KWD2=VAL2...'. 
               """
class PulseAudio(AudioInputDevice, device_name='pulse'):
    """FFmpeg audio input device 'pulse' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#pulse for more information. Use the command 'pactl list
    sources' to list all available PulseAudio devices.

    Args:
        sample_rate (:obj:`int`, optional): Sample rate of audio capture in Hz. Defaults to 48000.
        channels (:obj:`int`, optional): Number of audio channels. Defaults to 2.
        card (:obj:`str`, optional): Device identifier as an integer index. Defaults to 'default'.
    """
    def __init__(self, sample_rate=48000, channels=2, card='default'):
        super().__init__(sample_rate=sample_rate, channels=channels, card=card)
        self._device = card
        self._sample_rate = sample_rate
        self._channels = channels

    @property
    def device(self):
        return self._device

    @property
    def sample_rate(self):
        return self._sample_rate

    @property
    def channels(self):
        return self._channels

    @classmethod
    def help(cls):
        return """'pulse' audio input device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#pulse'.
               Use the command 'pactl list sources' to list all available PulseAudio devices.

               SAMPLE_RATE: Sample rate of audio capture in Hz. Defaults to 48000.

               CHANNELS: Number of audio channels. Defaults to 2.

               CARD: Device identifier as an integer index. Defaults to 'default'.
               """

@register_video_input_device(name='video4linux2,v4l2')
@register_video_input_device(name='v4l2')
class Video4Linux2(VideoInputDevice, device_name='video4linux2'):
    """FFmpeg video input device 'v4l2' for GNU/Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#video4linux2_002c-v4l2 for more information. Use the
    command 'v4l2-ctl --list-devices' to list all available Video4Linux2 devices.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True. Ignored
            here.
        display (:obj:`str`, optional): Device identifier as a file path. Defaults to '/dev/video0'.
    """
    def __init__(self, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True,
                 display='/dev/video0'):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)
        self._device = display
        self._video_size = video_size
        self._framerate = framerate

    @property
    def device(self):
        return self._device

    @property
    def video_size(self):
        return self._video_size

    @property
    def framerate(self):
        return self._framerate

    @property
    def draw_mouse(self):
        return 0

    @property
    def ffmpeg_arguments(self):
        return {'filename' : self.device, 's' : self.video_size,
                'framerate' : self.framerate}

    @classmethod
    def help(cls):
        return """'video4linux2' video input device for Linux systems. 'v4l2' and
               'video4linux2,v4l2' are aliases.
               Official documentation:
               'https://ffmpeg.org/ffmpeg-devices.html#video4linux2_002c-v4l2'.
               Use the command 'v4l2-ctl --list-devices' to list all available Video4Linux2
               devices.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is
               height. Defaults to fullscreen.

               FRAMERATE: Desired framerate of capture. Defaults to 'ntsc' ~= 29.97.

               DRAW_MOUSE: Draw mouse on capture. Defaults to true. Ignored here.

               DISPLAY: Device identifier as a file path. Defaults to '/dev/video0'.
               """

class X11Grab(VideoInputDevice, device_name='x11grab'):
    """FFmpeg video input device 'x11grab' for Linux systems. See
    https://ffmpeg.org/ffmpeg-devices.html#x11grab for more information. Use the command 'xdpyinfo'
    to list information about your display.

    Args:
        video_size (:obj:`str`, optional): Dimensions of capture, in the form 'wxh', where 'w' is
            width and 'h' is height. Defaults to fullscreen.
        framerate (:obj:`float`, optional): Desired framerate of capture. Defaults to 'ntsc' ~=
            29.97.
        draw_mouse (:obj:`bool`, optional): Draw mouse cursor on capture. Defaults to True.
        display (:obj:`str`, optional): Device identifier in the form
            '[hostname]:display_number[.screen_number][+x_offset,[y_offset]]'. Defaults to ':0.0'.
            The environment variable 'DISPLAY' returns your default display.
    """
    def __init__(self, video_size=utils.resolution(), framerate='ntsc', draw_mouse=True,
                 display=':0.0'):
        super().__init__(framerate=framerate, draw_mouse=draw_mouse, video_size=video_size,
                         display=display)
        self._device = display
        self._video_size = video_size
        self._framerate = framerate
        self._draw_mouse = int(draw_mouse)

    @property
    def device(self):
        return self._device

    @property
    def video_size(self):
        return self._video_size

    @property
    def framerate(self):
        return self._framerate

    @property
    def draw_mouse(self):
        return self._draw_mouse

    @classmethod
    def help(cls):
        return """'x11grab' video input device for Linux systems.
               Official documentation: 'https://ffmpeg.org/ffmpeg-devices.html#x11grab'.
               Use the command 'xdpyinfo' to list information about your display.

               VIDEO_SIZE: Dimensions of capture, in the form 'wxh', where 'w' is width and 'h' is
               height. Defaults to fullscreen.

               FRAMERATE: Desired framerate of capture. Defaults to 'ntsc' ~= 29.97.

               DRAW_MOUSE: Draw mouse on capture. Defaults to true.

               DISPLAY: Device identifier in the form
               '[hostname]:display_number[.screen_number][+x_offset,[y_offset]]'.
               Defaults to ':0.0'. The environment variable 'DISPLAY' returns your default display.
               """

def generate_input_device(name, **kwargs):
    """Creates the FFmpeg input device node.

    Args:
        name (str): Name of the input device in the
            :meth:`simple_capture.source.input_device.AudioInputDevice.retrieve_registry`, or the
            :meth:`simple_capture.source.input_device.VideoInputDevice.retrieve_registry`.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.input_device.InputDevice` or any of its subclasses.

    Returns:
        ffmpeg.nodes.FilterableStream: Input device stream.
    """
    input_device_registry = {**AudioInputDevice.retrieve_registry(),
                             **VideoInputDevice.retrieve_registry()}

    if (AudioInputDevice.retrieve_registry().get(name) and
        VideoInputDevice.retrieve_registry().get(name)):
        logging.warning(f'Device name {name} found in both registries!')
        try:
            device = AudioInputDevice.retrieve_registry()[name](**kwargs)
        except TypeError:
            logging.error(f'Device  {name} failed audio due to keyword arguments {kwargs}.')
            logging.info(traceback.format_exc())
            try:
                device = VideoInputDevice.retrieve_registry()[name](**kwargs)
            except TypeError:
                logging.error(f'Device  {name} failed video due to keyword arguments {kwargs}.')
                logging.info(traceback.format_exc())
                logging.error(f'Unable to instantiate device {name}!')

                return None
    elif not (AudioInputDevice.retrieve_registry().get(name) or
              VideoInputDevice.retrieve_registry().get(name)):
        logging.error((f'Unable to find device {name}! No device instantiated with keyword '
                       f'arguments {kwargs}.'))

        return None
    else:
        device = input_device_registry[name](**kwargs)

    logging.info((f'Instantiated device {device.device_name} of type {device.device_type} with '
                  f'ffmpeg arguments {device.ffmpeg_arguments} and keyword arguments {kwargs}.'))

    return ffmpeg.input(format=device.device_name, **device.ffmpeg_arguments)
