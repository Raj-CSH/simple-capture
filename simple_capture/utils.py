"""Contains miscellaneous utilities."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['init_log',
           'register',
           'class_attribute_register',
           'RegistryError',
           'RegistryEnabledObject']

import abc
import enum
import importlib
import logging

import screeninfo

def init_log(level=logging.INFO, log_file=None):
    importlib.reload(logging)
    if log_file is None:
        logging.basicConfig(level=level)
    else:
        with open(log_file, 'w'):
            pass
        logging.basicConfig(level=level, filename=log_file)
    logging.info('Initialized log!')

def resolution():
    monitors = screeninfo.get_monitors()
    if len(monitors) == 0:
        logging.warning('Cannot find resolution! Defaulting to \'1920x1080\'')
        return '1920x1080'
    return f'{monitors[0].width}x{monitors[0].height}'

def register(registry_enabled_object, name):
    def registered(callable_object):
        registry_enabled_object.retrieve_registry()[name] = callable_object
        return callable_object
    return registered

def class_attribute_register(registry_enabled_object, name_attribute):
    def registered(callable_object):
        name = getattr(callable_object, name_attribute)
        return register(registry_enabled_object, name)(callable_object)
    return registered

class RegistryError(ValueError):
    """Alias for ValueError."""

class RegistryEnabledObject(metaclass=abc.ABCMeta):
    def __init__(self, **kwargs):
        logging.debug((f'{type(self).__name__} passed keyword arguments '
                       f'\'{", ".join(f"{name}={value}" for name, value in kwargs.items())}\'.'))

    @abc.abstractmethod
    def __init_subclass__(cls, spec, **kwargs):
        cls._flag = spec
        super().__init_subclass__(**kwargs)

    @classmethod
    @abc.abstractmethod
    def __subclasshook__(cls, subclass):
        pass

    @classmethod
    @abc.abstractmethod
    def retrieve_registry(cls):
        """Get the registry of this class.

        Returns:
            dict(str, type): Registry of subclasses
        """

    @classmethod
    @abc.abstractmethod
    def help(cls):
        """Get a help message, used in the :class:`simple_capture.config.commands.Show` command.

        Returns:
            str: Help message.
        """

class FfSpec(enum.Enum):
    ANY = enum.auto()
    INPUT = enum.auto()
    FILTER = enum.auto()
    GLOBAL = enum.auto()
    NONE = enum.auto()
    OUTPUT = enum.auto()

class NoType:
    _flag = FfSpec.NONE