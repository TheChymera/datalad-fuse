"""DataLad FUSE extension"""

__docformat__ = 'restructuredtext'

from os.path import curdir
from os.path import abspath

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.support.param import Parameter
from datalad.distribution.dataset import datasetmethod
from datalad.interface.utils import eval_results
from datalad.support.constraints import EnsureChoice

from datalad.interface.results import get_status_dict

# defines a datalad command suite
# this symbold must be indentified as a setuptools entrypoint
# to be found by datalad
command_suite = (
    # description of the command suite, displayed in cmdline help
    "DataLad FUSE command suite",
    [
        # specification of a command, any number of commands can be defined
        (
            # importable module that contains the command implementation
            'datalad_fuse',
            # name of the command class implementation in above module
            'FuseFS',
            # optional name of the command in the cmdline API
            'fusefs',
            # optional name of the command in the Python API
            'fusefs'
        ),
        ("datalad_fuse.fsspec_head", "FsspecHead", "fsspec-head", "fsspec_head"),
    ]
)


# decoration auto-generates standard help
@build_doc
# all commands must be derived from Interface
class FuseFS(Interface):
    # first docstring line is used a short description in the cmdline help
    # the rest is put in the verbose help and manpage
    """FUSE File system providing transparent access to files under DataLad control

    """

    # parameters of the command, must be exhaustive
    _params_ = dict(
    )

    @staticmethod
    # decorator binds the command to the Dataset class as a method
    #@datasetmethod(name='fusefs')
    # generic handling of command results (logging, rendering, filtering, ...)
    @eval_results
    # signature must match parameter list above
    # additional generic arguments are added by decorators
    def __call__():

        # commands should be implemented as generators and should
        # report any results by yielding status dictionaries
        yield get_status_dict(
            # an action label must be defined, the command name make a good
            # default
            action='fusefs',
            # most results will be about something associated with a dataset
            # (component), reported paths MUST be absolute
            path=abspath(curdir),
            # status labels are used to identify how a result will be reported
            # and can be used for filtering
            status='ok',
            # arbitrary result message, can be a str or tuple. in the latter
            # case string expansion with arguments is delayed until the
            # message actually needs to be rendered (analog to exception messages)
            message=msg)


from datalad import setup_package
from datalad import teardown_package

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
