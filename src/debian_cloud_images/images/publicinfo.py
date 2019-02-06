import enum


@enum.unique
class ImagePublicType(enum.Enum):
    dev = {
        'vendor_family': 'debian-{release_id}-{arch}-dev-{build_id}',
        'vendor_description': 'Debian {release_id} (development build {build_id}-{version})',
    }
    daily = {
        'vendor_family': 'debian-{release_id}-{arch}-daily',
        'vendor_description': 'Debian {release_id} (daily build {version})',
    }
    release = {
        'vendor_family': 'debian-{release_id}-{arch}',
        'vendor_description': 'Debian {release_id} ({version})',
    }


class ImagePublicInfo:
    class ImagePublicInfoApplied:
        def __init__(self, public_type, info):
            self.__public_type, self.__info = public_type, info

        def __getattr__(self, key):
            if not key.startswith('_'):
                return self.__public_type.value[key].format(**self.__info)
            raise KeyError(key)

        @property
        def vendor_name(self):
            return '{}-{}'.format(self.vendor_family, self.__info['version'])

        @property
        def vendor_gce_family(self):
            " Return vendor family limited to 63 characters for GCE "
            return self.vendor_family[:63]

        @property
        def vendor_gce_name(self):
            " Return vendor name limited to 63 characters for GCE "
            version = self.__info['version']
            family = self.vendor_gce_family[:63 - 1 - len(version)]
            return '{}-{}'.format(family, version)

    def __init__(
        self,
        *,
        override_info={},
        public_type=ImagePublicType.dev,
    ):
        self.__override_info = override_info
        self.public_type = public_type

    def _generate_info(self, info):
        ret = info.copy()
        ret.update(self.__override_info)
        return ret

    def apply(self, info):
        return self.ImagePublicInfoApplied(self.public_type, self._generate_info(info))
