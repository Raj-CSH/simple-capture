"""Contains :class:`GlobalOptions` to allow support for global options and flags for FFmpeg."""

__author__ = 'Rajarshi Mandal'
__version__ = '1.0'
__all__ = ['generate_global_options',
           'global_options_parameters',
           'GlobalOptions']

import functools

import ffmpeg._ffmpeg as ffmpeg

from simple_capture import utils


def global_options_parameters():
    """Helper function to read arguments from a config file to create a node.

    Returns:
        dict(str, type): A dictionary of the types of the arguments of
            :class:`simple_capture.source.global_options.GlobalOptions`. Used to instruct
            :func:`simple_capture.config.io.generate_ffmpeg_node_structure` how to collect
            arguments from a config file.
    """
    return {'filter_thread_count' : int, 'display_stats' : bool, 'send_progress' : bool,
            'show_timestamps' : bool, 'show_qp_histogram' : bool, 'show_benchmark' : bool,
            'show_benchmark_verbose' : bool, 'exit_time_limit' : int, 'dump_input_stderr' : bool,
            'dump_payload_stderr' : bool, 'filter_complex_thread' : int, 'dump_sdp_file' : str,
            'abort_on_flags' : str, 'exit_on_error' : bool, 'overwrite_output' : bool,
            'sudo' : bool}

class GlobalOptions:
    _flag = utils.FfSpec.GLOBAL
    """

    Args:
        filter_thread_count (int): Maps to '-filter_threads' option for ffmpeg.
        display_stats (bool): Maps to '-stats' and '-nostats' options for ffmpeg.
        send_progress (bool): Maps to '-progress' option for ffmpeg.
        show_timestamps (bool): Maps to '-debug_ts' option for ffmpeg.
        show_qp_histogram (bool): Maps to '-qphist' option for ffmpeg.
        show_benchmark (bool): Maps to '-benchmark' option for ffmpeg.
        show_benchmark_verbose (bool): Maps to '-benchmark_all' option for ffmpeg.
        exit_time_limit (int): Maps to '-timelimit' option for ffmpeg.
        dump_input_stderr (bool): Maps to '-dump' option for ffmpeg.
        dump_payload_stderr (bool): Maps to '-hex' option for ffmpeg.
        filter_complex_thread_count (int): Maps to '-filter_complex_threads' option for ffmpeg.
        dump_sdp_file (str): Maps to '-sdp_file' option for ffmpeg.
        abort_on_flags (str): Maps to '-abort_on' option for ffmpeg.
        exit_on_error (bool): Maps to '-xerror' option for ffmpeg.
        overwrite_output (bool): Maps to '-y' and '-n' options for ffmpeg.
        sudo (bool): Add 'sudo' to the beginning of the ffmpeg command.
    """
    def __init__(self, filter_thread_count=None, show_stats=True, send_progress=False,
                 show_timestamps=False, show_qp_histogram=False, show_benchmark=False,
                 show_benchmark_verbose=False, exit_time_limit=None, dump_input_stderr=False,
                 dump_payload_stderr=False, filter_complex_thread_count=None, dump_sdp_file=None,
                 abort_on_flags=None, exit_on_error=False, overwrite_output=False, sudo=False):
        self._options = {'filter_threads' : filter_thread_count, 'stats' : show_stats,
                         'progress' : send_progress, 'debug_ts' : show_timestamps,
                         'qphist' : show_qp_histogram, 'benchmark' : show_benchmark,
                         'benchmark_all' : show_benchmark_verbose, 'timelimit' : exit_time_limit,
                         'dump' : dump_input_stderr, 'hex' : dump_payload_stderr,
                         'filter_complex_threads' : filter_complex_thread_count,
                         'sdp_file' : dump_sdp_file, 'abort_on' : abort_on_flags,
                         'xerror' : exit_on_error, 'y' : overwrite_output}
        self._doubly_named_flags = {'stats' : 'nostats', 'y' : 'n'}

    @functools.cached_property
    def ffmpeg_arguments(self):
        ffmpeg_arguments = []
        for arg, val in self._options.items():
            if val is None:
                continue
            elif isinstance(val, bool):
                if val:
                    ffmpeg_arguments.append(f'-{arg}')
                else:
                    if arg in self._doubly_named_flags:
                        ffmpeg_arguments.append(f'-{self._doubly_named_flags[arg]}')
            else:
                ffmpeg_arguments.append(f'-{arg}')
                ffmpeg_arguments.append(str(val))

        return ffmpeg_arguments 

    @classmethod
    def help(cls):
        return """Used to specify global arguments for ffmpeg.
               Official documentation: 'https://ffmpeg.org/ffmpeg.html#Main-options' and
               'https://ffmpeg.org/ffmpeg.html#Advanced-options'.
               """

def generate_global_options(name, stream, **kwargs):
    """Creates the FFmpeg global options node.

    Args:
        name (str): Ignored.
        stream (ffmpeg.nodes.OutputStream): Stream to apply global options to.
        **kwargs: Arguments to provide to the constructor of
            :class:`simple_capture.source.global_options.GlobalOptions`.

    Returns:
        ffmpeg.nodes.OutputStream: Stream with global options applied.
    """
    del name

    return ffmpeg.global_args(stream, *GlobalOptions(**kwargs).ffmpeg_arguments)
