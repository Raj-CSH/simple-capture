"""Contains miscellaneous utilities."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['init_log',
           'register',
           'class_attribute_register',
           'RegistryEnabledObject']

import abc
import enum
import importlib
import logging

import screeninfo

def init_log(level=logging.INFO, log_file=None):
    """Ensure the log is at the requested level.

    Args:
        level (int): Log level.
        log_file (bool): Log to a file instead of stdout.
    """
    importlib.reload(logging)
    if log_file is None:
        logging.basicConfig(level=level)
    else:
        with open(log_file, 'w'):
            pass
        logging.basicConfig(level=level, filename=log_file)
    logging.info('Initialized log!')

def resolution():
    """Get the resolution of the first monitor.

    Returns:
        str: Resolution in the form 'widthxheight'.
    """
    monitors = screeninfo.get_monitors()
    if len(monitors) == 0:
        logging.warning('Cannot find resolution! Defaulting to \'1920x1080\'')
        return '1920x1080'
    return f'{monitors[0].width}x{monitors[0].height}'

def register(registry_enabled_object, name):
    """Decorator factory. Used to add a class to a registry.
    >>> class Ham(RegistryEnabledObject):
    ...     _reg = {}
    ...     @classmethod
    ...     def retrieve_registry(cls):
    ...         return _reg
    ...
    >>> @register(Ham, 'spam')
    ... class Eggs:
    ...     pass
    ...
    >>> Ham.retrieve_registry()['spam']
    <class '__main__.Eggs'>

    Args:
        registry_enabled_object (type): Class containing target registry.
        name (str): Name of member in registry.

    Returns:
        callable: Decorator to register class.
    """
    def registered(callable_object):
        registry_enabled_object.retrieve_registry()[name] = callable_object
        return callable_object
    return registered

def class_attribute_register(registry_enabled_object, name_attribute):
    """Decorator factory. Used to add a class to a registry.
    >>> class Ham(RegistryEnabledObject):
    ...     _reg = {}
    ...     @classmethod
    ...     def retrieve_registry(cls):
    ...         return _reg
    ...
    >>> @class_attribute_register(Ham, 'name'):
    ... class Eggs:
    ...     name = spam
    ...
    >>> Ham.retrieve_registry()['spam']
    <class '__main__.Eggs'>

    Unlike :func:`simple_capture.utils.register`, this retrieves the name through a class
    attribute. This is useful when adding a base class to its own registry, see
    :class:`simple_capture.source.filters.Filter`.

    Args:
        registry_enabled_object (type): Class containing target registry.
        name_attribute (str): Name of class attribute specifying name in registry.

    Returns:
        callable: Decorator to register class.
    """
    def registered(callable_object):
        name = getattr(callable_object, name_attribute)
        return register(registry_enabled_object, name)(callable_object)
    return registered

class RegistryEnabledObject(metaclass=abc.ABCMeta):
    """Base class for registry classes."""
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
