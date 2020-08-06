"""Contains :class:`simple_capture.source.devices.Device` base class and the
:class:`simple_capture.source.devices.DeviceType` enum to be used in input and output device
classes.
"""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['register_device', 'device', 'DeviceType', 'Device']

import abc
import enum
import functools
import logging

from simple_capture import utils


device = functools.partial(utils.class_attribute_register, name_attribute='device_name')
register_device = utils.register

class DeviceType(enum.Enum):
    """Enum to indicate the type of device."""
    ANY = enum.auto()
    AUDIO = enum.auto()
    NONE = enum.auto()
    VIDEO = enum.auto()

class Device(utils.RegistryEnabledObject, metaclass=abc.ABCMeta, spec=utils.FfSpec.ANY):
    """Device base class."""
    @property
    @abc.abstractmethod
    def device(self):
        """str: The source or sink of the device."""

    @property
    @abc.abstractmethod
    def ffmpeg_arguments(self):
        """dict(str, str): Keyword arguments to be provided to the ffmpeg node constructor."""

    def __init_subclass__(cls, spec, device_name, device_type=DeviceType.NONE, **kwargs):
        super().__init_subclass__(spec=spec, **kwargs)
        cls.device_name = device_name
        if not hasattr(cls, 'device_type') or device_type is not DeviceType.NONE:
            cls.device_type = device_type
        logging.info((f'Device {cls} found with name {cls.device_name} and type '
                      f'{cls.device_type}!'))

    def __repr__(self):
        return (f'{type(self).__name__}'
                f'(device_name=\'{self.device_name}\', device_type={self.device_type})')

    @classmethod
    def __subclasshook__(cls, subclass):
        return ((hasattr(subclass, 'device_name') and
                 getattr(subclass, 'device_type') == cls.device_type) or subclass in
                cls.retrieve_registry())
