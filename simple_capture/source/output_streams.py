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
    """[summary]

    Args:
        filename (str): Maps to '-i' option for ffmpeg.
        fmt (str): Maps to '-f' option for ffmpeg.
        video_codec (str): Maps to '-vcodec/-c:v' option for ffmpeg.
        audio_codec (str): Maps to '-acodec/-c:a' option for ffmpeg.
        file_size (int): Maps to '-fs' option for ffmpeg.
        duration (str): Maps to '-t' option for ffmpeg.
        end_position (str): Maps to '-to' option for ffmpeg.
        seek_position (str): Maps to '-ss' option for ffmpeg.
        timestamp (str): Maps to '-timestamp' option for ffmpeg.
        target (str): Maps to '-target' option for ffmpeg.
        preset (str): Maps to '-pre' option for ffmpeg.
        framerate (float): Maps to '-framerate' option for ffmpeg.
        video_size (str): Maps to '-s' option for ffmpeg.
        aspect_ratio (str): Maps to '-aspect' for ffmpeg.
        pixel_format (str): Maps to '-pix_fmt' option for ffmpeg.
        sample_rate (int): Maps to '-ar' option for ffmpeg.
        channels (int): Maps to '-ac' option for ffmpeg.
        sample_format (str): Maps to '-sample_fmt' option for ffmpeg.
        fourcc (str): Maps to '-atag' option for ffmpeg.
        minimum_rate (str): Maps to '-minrate' option for ffmpeg.
        maximum_rate (str): Maps to '-maxrate' option for ffmpeg.
        buffer_size (str): Maps to '-bufsize' option for ffmpeg.
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
        return """"""

def output_stream(cls):
    return streams.stream(OutputStream)(cls)

register_output_stream = functools.partial(streams.register_stream, OutputStream)

output_stream(OutputStream)


def generate_output_stream(name, *args, **kwargs):
    stream = OutputStream.retrieve_registry().get(name)
    if stream is None:
        logging.error((f'Unable to find stream {name}! No stream instantiated with keyword '
                       f'arguments {kwargs}.'))

        return None
    return ffmpeg.output(*args, **stream(**kwargs).ffmpeg_arguments)
