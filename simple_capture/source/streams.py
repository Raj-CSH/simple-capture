"""Contains :class:`Stream` base class to be used in input and output stream classes."""


__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['register_stream', 'stream', 'Stream']

import abc
import enum
import functools
import logging

from simple_capture import utils


stream = functools.partial(utils.class_attribute_register, name_attribute='stream_name')
register_stream = utils.register

class Stream(utils.RegistryEnabledObject, metaclass=abc.ABCMeta, spec=utils.FfSpec.ANY):
    """Stream base class."""
    @property
    @abc.abstractmethod
    def filename(self):
        """str: The working filename of the stream."""

    @property
    @abc.abstractmethod
    def ffmpeg_arguments(self):
        """dict(str, str): Keyword arguments to be provided to the ffmpeg node constructor."""

    def __init_subclass__(cls, spec, stream_name, **kwargs):
        super().__init_subclass__(spec=spec, **kwargs)
        cls.stream_name = stream_name
        logging.info(f'Stream {cls} found with spec {cls._flag} and name {cls.stream_name}!')

    def __repr__(self):
        return f'{type(self).__name__}(spec={self._flag}, stream_name={self.stream_name})'

    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'stream_name') or subclass in cls.retrieve_registry())

    
