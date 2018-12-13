import collections.abc
import enum
import logging
import os
import re
import subprocess

from .base import BaseCommand

from ..utils import argparse_ext


logger = logging.getLogger()


class Arch:
    def __init__(self, kw):
        def init(*, fai_classes):
            self.fai_classes = fai_classes
        init(**kw)


class Release:
    def __init__(self, kw):
        def init(*, id, fai_classes, supports_linux_image_cloud=False):
            self.id = id
            self.fai_classes = fai_classes
            self.supports_linux_image_cloud = supports_linux_image_cloud
        init(**kw)


class Vendor:
    def __init__(self, kw):
        def init(*, fai_size, fai_classes, use_linux_image_cloud=False):
            self.fai_size = fai_size
            self.fai_classes = fai_classes
            self.use_linux_image_cloud = use_linux_image_cloud
        init(**kw)


ArchEnum = enum.Enum(
    'ArchEnum',
    {
        'amd64': {
            'fai_classes': ('AMD64', 'GRUB_PC'),
        },
        'amd64-efi': {
            'fai_classes': ('AMD64', 'GRUB_EFI_AMD64'),
        },
        'arm64': {
            'fai_classes': ('ARM64', 'GRUB_EFI_ARM64'),
        },
        'ppc64el': {
            'fai_classes': ('PPC64EL', 'GRUB_IEEE1275'),
        },
    },
    type=Arch,
)


ReleaseEnum = enum.Enum(
    'ReleaseEnum',
    {
        'stretch': {
            'id': '9',
            'fai_classes': ('STRETCH', 'BACKPORTS'),
        },
        'stretch-backports': {
            'id': '9-backports',
            'fai_classes': ('STRETCH', 'BACKPORTS', 'BACKPORTS_LINUX'),
            'supports_linux_image_cloud': True,
        },
        'buster': {
            'id': '10',
            'fai_classes': ('BUSTER', ),
            'supports_linux_image_cloud': True,
        },
        'sid': {
            'id': 'sid',
            'fai_classes': ('SID', ),
            'supports_linux_image_cloud': True,
        },
    },
    type=Release,
)


VendorEnum = enum.Enum(
    'VendorEnum',
    {
        'azure': {
            'fai_size': '30G',
            'fai_classes': ('AZURE', ),
            'use_linux_image_cloud': True,
        },
        'ec2': {
            'fai_size': '8G',
            'fai_classes': ('EC2', ),
        },
        'gce': {
            'fai_size': '10G',
            'fai_classes': ('GCE', ),
        },
        'nocloud': {
            'fai_size': '8G',
            'fai_classes': ('NOCLOUD', ),
        },
        'openstack': {
            'fai_size': '2G',
            'fai_classes': ('OPENSTACK', ),
        },
    },
    type=Vendor,
)


class BuildId:
    re = re.compile(r"^\d{8}|[a-z][a-z0-9-]+$")

    def __init__(self, s):
        r = self.re.match(s)

        if not r:
            raise ValueError('invalid build id value')

        self.id = r.group(0)


class Classes(collections.abc.MutableSet):
    def __init__(self):
        self.__data = []

    def __contains__(self, v):
        return v in self.__data

    def __iter__(self):
        return iter(self.__data)

    def __len__(self):
        return len(self.__data)

    def add(self, v):
        logger.info('Adding class %s', v)
        self.__data.append(v)

    def discard(self, v):
        logger.info('Removing class %s', v)
        self.__data.remove(v)


class Check:
    def __init__(self):
        self.classes = Classes()
        self.classes.add('DEBIAN')
        self.classes.add('CLOUD')
        self.env = {}

    def set_release(self, release):
        self.release = release
        self.env['CLOUD_BUILD_INFO_RELEASE'] = self.release.name
        self.env['CLOUD_BUILD_INFO_RELEASE_ID'] = self.release.id
        self.classes |= self.release.fai_classes

    def set_vendor(self, vendor):
        self.vendor = vendor
        self.env['CLOUD_BUILD_INFO_VENDOR'] = self.vendor.name
        self.classes |= self.vendor.fai_classes

    def set_arch(self, arch):
        self.arch = arch
        self.env['CLOUD_BUILD_INFO_ARCH'] = self.arch.name
        self.classes |= self.arch.fai_classes

    def set_version(self, build_id, ci_pipeline_iid):
        self.env['CLOUD_RELEASE_VERSION'] = '{!s}-{!s}'.format(build_id.id, ci_pipeline_iid)

    def check(self):
        if self.release.supports_linux_image_cloud and self.vendor.use_linux_image_cloud:
            self.classes.add('LINUX_IMAGE_CLOUD')
        else:
            self.classes.add('LINUX_IMAGE_BASE')
        self.classes.add('LAST')


class BuildCommand(BaseCommand):
    argparser_name = 'build'
    argparser_help = 'build Debian images'
    argparser_usage = '%(prog)s'

    @classmethod
    def _argparse_register(cls, parser):
        super()._argparse_register(parser)

        parser.add_argument(
            'release',
            action=argparse_ext.ActionEnum,
            enum=ReleaseEnum,
            help='Debian release to build',
            metavar='RELEASE',
        )
        parser.add_argument(
            'vendor',
            action=argparse_ext.ActionEnum,
            enum=VendorEnum,
            help='Vendor to build image for',
            metavar='VENDOR',
        )
        parser.add_argument(
            'arch',
            action=argparse_ext.ActionEnum,
            enum=ArchEnum,
            help='Architecture or sub-architecture to build image for',
            metavar='ARCH',
        )
        parser.add_argument('name', metavar='NAME')
        parser.add_argument(
            '--build-id',
            metavar='ID',
            required=True,
            type=BuildId,
        )
        parser.add_argument(
            '--ci-pipeline-iid',
            action=argparse_ext.ActionEnv,
            env='CI_PIPELINE_IID',
            metavar='ID',
            type=int,
        )
        parser.add_argument('--noop', action='store_true')

    def __init__(self, *, release=None, vendor=None, arch=None, build_id=None, ci_pipeline_iid=None, name=None, noop=False, **kw):
        super().__init__(**kw)

        self.name = name
        self.noop = noop

        self.c = Check()
        self.c.set_release(release)
        self.c.set_vendor(vendor)
        self.c.set_arch(arch)
        self.c.set_version(build_id, ci_pipeline_iid)
        self.c.check()

        self.env = os.environ.copy()
        self.env.update(self.c.env)
        self.env['CLOUD_BUILD_NAME'] = name
        self.env['CLOUD_BUILD_OUTPUT_DIR'] = os.getcwd()

        if os.path.isdir(os.path.join(os.getcwd(), 'config_space')):
            config_space_folder = os.path.join(os.getcwd(), 'config_space')
        else:
            config_space_folder = '/usr/share/debian-cloud-images/config_space'

        self.cmd = (
            'fai-diskimage',
            '--verbose',
            '--hostname', 'debian',
            '--class', ','.join(self.c.classes),
            '--size', self.c.vendor.fai_size,
            '--cspace', config_space_folder,
            name + '.raw',
        )

        self.cmd_tar = (
            'tar',
            '-cS',
            '-f', '{}.tar'.format(name),
            '--transform', r'flags=r;s|.*\.raw|disk.raw|',
            '{}.raw'.format(name),
        )

    def __call__(self):
        logging.info('Running: %s; %s', ' '.join(self.cmd), ' '.join(self.cmd_tar))

        if not self.noop:
            subprocess.check_call(self.cmd, env=self.env)
            subprocess.check_call(self.cmd_tar)


if __name__ == '__main__':
    parser = BuildCommand._argparse_init_base()

    args = parser.parse_args()
    BuildCommand(**vars(args))()
