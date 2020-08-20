"""Contains :class:`InputStream` to allow for input sources other than devices."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_input_stream',
           'input_stream_parameters',
           'register_input_stream',
           'input_stream',
           'InputStream']

import abc
import enum
import functools
import logging

from simple_capture.source import streams
from simple_capture import utils

import ffmpeg


def input_stream_parameters():
    return {'filename' : str, 'fmt' : str, 'loop_count' : int, 'video_codec' : str,
            'audio_codec' : str, 'duration' : str, 'end_position' : str, 'seek_position' : str,
            'eof_seek_position' : str, 'timestamp_offset' : str, 'timestamp_scale' : float,
            'framerate' : float, 'pixel_format' : str, 'sample_rate' : int, 'channels' : int,
            'thread_queue_size' : int}

class InputStream(streams.Stream, stream_name='other-stream', spec=utils.FfSpec.INPUT):
    """Input stream class, used to add input media in forms other than live device capture.

    Args:
        filename (str): Maps to '-i' option for ffmpeg.
        fmt (:obj:`str`, optional): Maps to '-f' option for ffmpeg.
        loop_count (:obj:`int`, optional): Maps to '-stream_loop' option for ffmpeg.
        video_codec (:obj:`str`, optional): Maps to '-vcodec/-c:v' option for ffmpeg.
        audio_codec (:obj:`str`, optional): Maps to '-acodec/-c:a' option for ffmpeg.
        duration (:obj:`str`, optional): Maps to '-t' option for ffmpeg.
        end_position (:obj:`str`, optional): Maps to '-to' option for ffmpeg.
        seek_position (:obj:`str`, optional): Maps to '-ss' option for ffmpeg.
        eof_seek_position (:obj:`str`, optional): Maps to '-sseof' option for ffmpeg.
        timestamp_offset (:obj:`str`, optional): Maps to '-itoffset' option for ffmpeg.
        timestamp_scale (:obj:`float`, optional): Maps to '-itscale' option for ffmpeg.
        framerate (:obj:`float`, optional): Maps to '-framerate' option for ffmpeg.
        pixel_format (:obj:`str`, optional): Maps to '-pix_fmt' option for ffmpeg.
        sample_rate (:obj:`int`, optional): Maps to '-ar' option for ffmpeg.
        channels (:obj:`int`, optional): Maps to '-ac' option for ffmpeg.
        thread_queue_size (:obj:`int`, optional): Maps to '-thread_queue_size' option for ffmpeg.
    """
    _input_stream_registry = {}

    def __init__(self, filename, fmt=None, loop_count=None, video_codec=None, audio_codec=None,
                 duration=None, end_position=None, seek_position=None, eof_seek_position=None,
                 timestamp_offset=None, timestamp_scale=None, framerate=None, pixel_format=None,
                 sample_rate=None, channels=None, thread_queue_size=None):
        self._options = {'filename' : filename, 'format' : fmt, 'stream_loop' : loop_count,
                         'vcodec' : video_codec, 'acodec' : audio_codec, 't' : duration,
                         'to' : end_position, 'ss' : seek_position, 'sseof' : eof_seek_position,
                         'itoffset' : timestamp_offset, 'itscale' : timestamp_scale,
                         'framerate' : framerate, 'pix_fmt' : pixel_format, 'ar' : sample_rate,
                         'ac' : channels, 'thread_queue_size' : thread_queue_size}
        self._mutually_exclusive = []
        self._define_mutually_exclusive('t', 'to')
        self._define_mutually_exclusive('ss', 'sseof')

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
        logging.info(f'InputStream {cls} found with name {cls.stream_name}!')
        logging.debug(f'Found InputStreams: {cls.retrieve_registry()}.')

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
            logging.info(f'Discarding input stream arguments {to_remove}.')
            for arg in to_remove:
                del filtered_options[arg]

    @classmethod
    def help(cls):
        return """Generic input stream type. Used to add other input media, such as logos.
               Official documentation: 'https://ffmpeg.org/ffmpeg.html#Main-options'.
               """

    @classmethod
    def retrieve_registry(cls):
        return cls._input_stream_registry

def input_stream(cls):
    """Decorator to register an input stream. The key is
    :attr:`simple_capture.source.streams.Stream.stream_name` attribute of the class.

    Args:
        cls (type): Class to register.

    Returns:
        type: Registered class.
    """
    return streams.stream(InputStream)(cls)

register_input_stream = functools.partial(streams.register_stream, InputStream)

input_stream(InputStream)


def generate_input_stream(name, filename, **kwargs):
    """Creates the FFmpeg input stream node.

    Args:
        name (str): Name of the input stream, in the
            :meth:`simple_capture.source.input_streams.InputStream.retrieve_registry`.
        filename (str): Input filename.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.input_streams.InputStream` or any of its subclasses.

    Returns:
        ffmpeg.nodes.FilterableStream: Input stream.
    """

    stream = InputStream.retrieve_registry().get(name)
    if stream is None:
        logging.error((f'Unable to find stream {name}! No stream instantiated with keyword '
                       f'arguments {kwargs}.'))

        return None
    return ffmpeg.input(**stream(filename=filename, **kwargs).ffmpeg_arguments)
