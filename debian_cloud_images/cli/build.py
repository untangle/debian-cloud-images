import collections.abc
import logging
import os
import re
import subprocess

from .base import BaseCommand


logger = logging.getLogger()


class Arch:
    pass


class ArchAmd64(Arch):
    NAME = 'amd64'
    FAI_CLASSES = ('AMD64', 'GRUB_PC')


class ArchAmd64Efi(Arch):
    NAME = 'amd64-efi'
    FAI_CLASSES = ('AMD64', 'GRUB_EFI_AMD64')


class ArchArm64(Arch):
    NAME = 'arm64'
    FAI_CLASSES = ('ARM64', 'GRUB_EFI_ARM64')


class ArchPpc64El(Arch):
    NAME = 'ppc64el'
    FAI_CLASSES = ('PPC64EL', 'GRUB_IEEE1275')


class Release:
    SUPPORTS_LINUX_IMAGE_CLOUD = False


class ReleaseStretch(Release):
    NAME = 'stretch'
    ID = '9'
    FAI_CLASSES = ('STRETCH', 'BACKPORTS')


class ReleaseStretchBackports(Release):
    NAME = 'stretch-backports'
    ID = '9-backports'
    FAI_CLASSES = ('STRETCH', 'BACKPORTS', 'BACKPORTS_LINUX')
    SUPPORTS_LINUX_IMAGE_CLOUD = True


class ReleaseBuster(Release):
    NAME = 'buster'
    ID = '10'
    FAI_CLASSES = ('BUSTER', )
    SUPPORTS_LINUX_IMAGE_CLOUD = True


class ReleaseSid(Release):
    NAME = 'sid'
    ID = 'sid'
    FAI_CLASSES = ('SID', )
    SUPPORTS_LINUX_IMAGE_CLOUD = True


class ImageType:
    def convert_image(self, basename):
        pass


class ImageTypeRaw(ImageType):
    NAME = 'raw'

    def convert_image(self, basename, noop):
        cmd = (
            'tar', '-cS',
            '-f', '{}.tar'.format(basename),
            '--transform', 'flags=r;s|.*\.raw|disk.raw|',
            '{}.raw'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)


class ImageTypeVhd(ImageType):
    NAME = 'vhd'

    def convert_image(self, basename, noop):
        cmd = (
            'qemu-img', 'convert',
            '-f', 'raw', '-o', 'subformat=fixed,force_size', '-O', 'vpc',
            '{}.raw'.format(basename), '{}.vhd'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)

        cmd = (
            'tar', '-cS',
            '-f', '{}.tar'.format(basename),
            '--transform', 'flags=r;s|.*\.vhd|disk.vhd|',
            '{}.vhd'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)


class ImageTypeQcow2(ImageType):
    NAME = 'qcow2'

    def convert_image(self, basename, noop):
        cmd = (
            'qemu-img', 'convert',
            '-f', 'raw', '{}.raw'.format(basename),
            '-o', 'compat=0.10',
            '-O', 'qcow2', '{}.qcow2'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)

        cmd = (
            'tar', '-cS',
            '-f', '{}.tar'.format(basename),
            '--transform', 'flags=r;s|.*\.qcow2|disk.qcow2|',
            '{}.qcow2'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)


class ImageTypeVmdk(ImageType):
    NAME = 'vmdk'

    def convert_image(self, basename, noop):
        cmd = (
            'qemu-img', 'convert',
            '-f', 'raw', '-O', 'vmdk', '-o', 'subformat=streamOptimized',
            '{}.raw'.format(basename), '{}.vmdk'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)

        cmd = (
            'tar', '-cS',
            '-f', '{}.tar'.format(basename),
            '--transform', 'flags=r;s|.*\.vmdk|disk.vmdk|',
            '{}.vmdk'.format(basename),
        )
        logging.info('Running: %s', ' '.join(cmd))

        if not noop:
            subprocess.check_call(cmd)


class Vendor:
    FAI_SIZE = '8G'
    USE_LINUX_IMAGE_CLOUD = False


class VendorNo(Vendor):
    NAME = "nocloud"
    FAI_CLASSES = ('NOCLOUD', )

    image = ImageTypeRaw()


class VendorAzure(Vendor):
    NAME = 'azure'
    FAI_CLASSES = ('AZURE', )
    FAI_SIZE = '30G'
    USE_LINUX_IMAGE_CLOUD = True

    image = ImageTypeVhd()


class VendorEc2(Vendor):
    NAME = 'ec2'
    FAI_CLASSES = ('EC2', )
    FAI_SIZE = '8G'

    image = ImageTypeVmdk()


class VendorOpenstack(Vendor):
    NAME = 'openstack'
    FAI_CLASSES = ('OPENSTACK', )
    FAI_SIZE = '2G'

    image = ImageTypeQcow2()


class VendorGce(Vendor):
    NAME = 'gce'
    FAI_CLASSES = ('GCE', )
    FAI_SIZE = '10G'

    image = ImageTypeRaw()


class Version:
    re = re.compile(r"(?P<release>^(?P<release_base>\d{8})(?P<release_extra>[a-z])?$)|(^dev)")

    def __init__(self, s):
        r = self.re.match(s)

        self.release = r.group('release')
        self.release_base = r.group('release_base')
        self.release_extra = r.group('release_extra')


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


arches = { i.NAME: i for i in Arch.__subclasses__() }
releases = { i.NAME: i for i in Release.__subclasses__() }
vendors = { i.NAME: i for i in Vendor.__subclasses__() }


class Check:
    def __init__(self):
        self.classes = Classes()
        self.classes.add('DEBIAN')
        self.classes.add('CLOUD')
        self.env = {}

    def set_release(self, release):
        self.release = releases[release]()
        self.env['CLOUD_BUILD_INFO_RELEASE'] = self.release.NAME
        self.env['CLOUD_BUILD_INFO_RELEASE_ID'] = self.release.ID
        self.classes |= self.release.FAI_CLASSES

    def set_vendor(self, vendor):
        self.vendor = vendors[vendor]()
        self.env['CLOUD_BUILD_INFO_VENDOR'] = self.vendor.NAME
        self.env['CLOUD_BUILD_INFO_IMAGE_TYPE'] = self.vendor.image.NAME
        self.classes |= self.vendor.FAI_CLASSES

    def set_arch(self, arch):
        self.arch = arches[arch]()
        self.env['CLOUD_BUILD_INFO_ARCH'] = self.arch.NAME
        self.classes |= self.arch.FAI_CLASSES

    def set_version(self, version):
        if version.release:
            self.env['CLOUD_RELEASE_VERSION'] = version.release

    def check(self):
        if self.release.SUPPORTS_LINUX_IMAGE_CLOUD and self.vendor.USE_LINUX_IMAGE_CLOUD:
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

        parser.add_argument('release', metavar='RELEASE', choices=sorted(releases.keys()))
        parser.add_argument('vendor', metavar='VENDOR', choices=sorted(vendors.keys()))
        parser.add_argument('arch', metavar='ARCH', choices=sorted(arches.keys()))
        parser.add_argument('name', metavar='NAME')
        parser.add_argument('version', metavar='VERSION', type=Version)
        parser.add_argument('--noop', action='store_true')

    def __init__(self, *, release=None, vendor=None, arch=None, version=None, name=None, noop=False, **kw):
        super().__init__(**kw)

        self.name = name
        self.noop = noop

        self.c = Check()
        self.c.set_release(release)
        self.c.set_vendor(vendor)
        self.c.set_arch(arch)
        self.c.set_version(version)
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
            '--size', self.c.vendor.FAI_SIZE,
            '--cspace', config_space_folder,
            name + '.raw',
        )

    def __call__(self):
        logging.info('Running: %s', ' '.join(self.cmd))

        if not self.noop:
            subprocess.check_call(self.cmd, env=self.env)

        self.c.vendor.image.convert_image(self.name, self.noop)


if __name__ == '__main__':
    parser = BuildCommand._argparse_init_base()

    args = parser.parse_args()
    BuildCommand(**vars(args))()
