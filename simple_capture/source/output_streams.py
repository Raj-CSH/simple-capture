"""Contains :class:`InputStream` to allow for input sources other than devices."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_output_stream',
           'output_stream_parameters',
           'register_output_stream',
           'output_stream',
           'OutputStream']

import abc
import enum
import functools
import logging

from simple_capture.source import streams
from simple_capture import utils

import ffmpeg


def output_stream_parameters():
    return {'filename' : str, 'fmt' : str, 'video_codec' : str, 'audio_codec' : str,
            'file_size' : int, 'duration' : str, 'end_position' : str, 'seek_position' : str,
            'timestamp' : str, 'target' : str, 'preset' : str, 'framerate' : float,
            'video_size' : str, 'aspect_ratio' : str, 'pixel_format' : str, 'sample_rate' : int,
            'channels' : int, 'sample_format' : str, 'fourcc' : str, 'minimum_rate' : str,
            'maximum_rate' : str, 'buffer_size' : str}

class OutputStream(streams.Stream, stream_name='other-stream', spec=utils.FfSpec.OUTPUT):
    """Output stream class, used to add output targets in forms other than live device casting.

    Args:
        filename (str): Maps to '-i' option for ffmpeg.
        fmt (:obj:`str`, optional): Maps to '-f' option for ffmpeg.
        video_codec (:obj:`str`, optional): Maps to '-vcodec/-c:v' option for ffmpeg.
        audio_codec (:obj:`str`, optional): Maps to '-acodec/-c:a' option for ffmpeg.
        file_size (:obj:`int`, optional): Maps to '-fs' option for ffmpeg.
        duration (:obj:`str`, optional): Maps to '-t' option for ffmpeg.
        end_position (:obj:`str`, optional): Maps to '-to' option for ffmpeg.
        seek_position (:obj:`str`, optional): Maps to '-ss' option for ffmpeg.
        timestamp (:obj:`str`, optional): Maps to '-timestamp' option for ffmpeg.
        target (:obj:`str`, optional): Maps to '-target' option for ffmpeg.
        preset (:obj:`str`, optional): Maps to '-pre' option for ffmpeg.
        framerate (:obj:`float`, optional): Maps to '-framerate' option for ffmpeg.
        video_size (:obj:`str`, optional): Maps to '-s' option for ffmpeg.
        aspect_ratio (:obj:`str`, optional): Maps to '-aspect' for ffmpeg.
        pixel_format (:obj:`str`, optional): Maps to '-pix_fmt' option for ffmpeg.
        sample_rate (:obj:`int`, optional): Maps to '-ar' option for ffmpeg.
        channels (:obj:`int`, optional): Maps to '-ac' option for ffmpeg.
        sample_format (:obj:`str`, optional): Maps to '-sample_fmt' option for ffmpeg.
        fourcc (:obj:`str`, optional): Maps to '-atag' option for ffmpeg.
        minimum_rate (:obj:`str`, optional): Maps to '-minrate' option for ffmpeg.
        maximum_rate (:obj:`str`, optional): Maps to '-maxrate' option for ffmpeg.
        buffer_size (:obj:`str`, optional): Maps to '-bufsize' option for ffmpeg.
    """
    _output_stream_registry = {}

    def __init__(self, filename, fmt=None, video_codec=None, audio_codec=None, file_size=None,
                 duration=None, end_position=None, seek_position=None, timestamp=None,
                 target=None, preset=None, framerate=None, video_size=None, aspect_ratio=None,
                 pixel_format=None, sample_rate=None, channels=None, sample_format=None,
                 fourcc=None, minimum_rate=None, maximum_rate=None, buffer_size=None):

        self._options = {'filename' : filename, 'format' : fmt, 'fs' : file_size,
                         'vcodec' : video_codec, 'acodec' : audio_codec, 't' : duration,
                         'to' : end_position, 'ss' : seek_position, 'timestamp' : timestamp,
                         'target' : target, 'pre' : preset, 'framerate' : framerate,
                         's' : video_size, 'aspect' : aspect_ratio, 'pix_fmt' : pixel_format,
                         'ar' : sample_rate, 'ac' : channels, 'sample_fmt' : sample_format,
                         'atag' : fourcc, 'minrate' : minimum_rate, 'maxrate' : maximum_rate,
                         'bufsize' : buffer_size}
        self._mutually_exclusive = []
        self._define_mutually_exclusive('t', 'to')

    @property
    def filename(self):
        return self._options['filename']

    @functools.cached_property
    def ffmpeg_arguments(self):
        filtered_options = {arg:value for arg, value in self._options.items() if value is not None}
        self._process_mutually_exclusive(filtered_options)
        return filtered_options

    def __init_subclass__(cls, stream_name, **kwargs):
        super().__init_subclass__(spec=cls._flag, stream_name=stream_name, **kwargs)
        cls.retrieve_registry()[stream_name] = cls
        logging.info(f'OutputStream {cls} found with name {cls.stream_name}!')
        logging.debug(f'Found OutputStreams: {cls.retrieve_registry()}.')

    def _define_mutually_exclusive(self, *args):
        """Define any mutually exclusive arguments.

        Args:
            *args: Argument names.

        Note:
            Arguments must be passed in order of precedence/priority, with the first argument
            passed as having the most priority.
        """
        if len(args) <= 1:
            return
        self._mutually_exclusive.append(args)

    def _process_mutually_exclusive(self, filtered_options):
        """Removes arguments that are meant to be mutually exclusive with each other.

        Args:
            filtered_options (dict(str, Any)): Preprocessed options.
        """
        for mutually_exclusive in self._mutually_exclusive:
            found = [arg for arg in mutually_exclusive if arg in filtered_options]
            if len(found) <= 1:
                continue
            to_remove = found[1:]
            logging.info(f'Discarding output stream arguments {to_remove}.')
            for arg in to_remove:
                del filtered_options[arg]

    @classmethod
    def retrieve_registry(cls):
        return cls._output_stream_registry

    @classmethod
    def help(cls):
        return """Generic output stream type. Used to add other output targets, such as saving to a
               file. Official documentation: 'https://ffmpeg.org/ffmpeg.html#Main-options'.
               """

def output_stream(cls):
    """Decorator to register an output stream. The key is
    :attr:`simple_capture.source.streams.Stream.stream_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return streams.stream(OutputStream)(cls)

register_output_stream = functools.partial(streams.register_stream, OutputStream)

output_stream(OutputStream)


def generate_output_stream(name, *args, **kwargs):
    """Creates the FFmpeg output stream node.

    Args:
        name (str): Name of the output stream, in the
            :meth:`simple_capture.source.output_streams.OutputStream.retrieve_registry`.
        *args: Input streams.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.output_streams.OutputStream` or any of its subclasses.

    Returns:
        ffmpeg.nodes.OutputStream: Output stream.
    """

    stream = OutputStream.retrieve_registry().get(name)
    if stream is None:
        logging.error((f'Unable to find stream {name}! No stream instantiated with keyword '
                       f'arguments {kwargs}.'))

        return None
    return ffmpeg.output(*args, **stream(**kwargs).ffmpeg_arguments)
