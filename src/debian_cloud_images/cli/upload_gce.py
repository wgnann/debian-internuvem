import json
import logging
import zlib

from .upload_base import UploadBaseCommand
from ..api.cdo.upload import Upload
from ..api.wellknown import label_ucdo_provider, label_ucdo_type
from ..utils import argparse_ext

from libcloud.compute.types import Provider as ComputeProvider
from libcloud.compute.providers import get_driver as compute_driver
from libcloud.storage.types import Provider as StorageProvider
from libcloud.storage.providers import get_driver as storage_driver


class ImageUploaderGce:
    storage_cls = storage_driver(StorageProvider.GOOGLE_STORAGE)
    compute_cls = compute_driver(ComputeProvider.GCE)

    def __init__(self, output, project, bucket, auth):
        self.output = output
        self.project = project
        self.bucket = bucket
        self.auth = auth

        self.__compute = self.__storage = None

    @property
    def compute(self):
        compute = self.__compute
        if compute is None:
            compute = self.__compute = self.compute_cls(
                project=self.project,
                user_id=self.auth['client_email'],
                key=self.auth['private_key'],
            )
        return compute

    @property
    def storage(self):
        storage = self.__storage
        if storage is None:
            storage = self.__storage = self.storage_cls(
                key=self.auth['client_email'],
                secret=self.auth['private_key'],
            )
        return storage

    @property
    def storage_container(self):
        return self.storage.get_container(
            container_name=self.bucket,
        )

    def __call__(self, image, public_info):
        gce_family = public_info.vendor_gce_family
        gce_name = public_info.vendor_gce_name

        gce_family_url = f'projects/{self.project}/global/images/family/{gce_family}'
        gce_name_url = f'projects/{self.project}/global/images/{gce_name}'

        if self.check_image(image, gce_name):
            logging.warning('Image %s already exists, not uploading', gce_name)
            return

        gce_file = self.upload_file(image, gce_name)
        self.create_image(image, gce_name, gce_family, gce_file)

        metadata = image.build.metadata.copy()
        metadata.labels[label_ucdo_provider] = 'cloud.google.com'
        metadata.labels[label_ucdo_type] = public_info.public_type.name

        manifests = [Upload(
            metadata=metadata,
            provider='googleapis.com',
            ref=gce_name_url,
            family_ref=gce_family_url,
        )]

        image.write_manifests('upload-gce', manifests, output=self.output)

        self.delete_file(image, gce_file)

    def check_image(self, image, gce_name):
        """ Check if image already exists """
        from libcloud.common.google import ResourceNotFoundError
        try:
            self.compute.ex_get_image(gce_name, ex_project_list=self.project, ex_standard_projects=False)
            return True
        except ResourceNotFoundError:
            return False

    def create_image(self, image, gce_name, gce_family, gce_file):
        """ Create image for Google Compute Engine """
        url = 'https://storage.cloud.google.com/{}/{}'.format(gce_file.container.name, gce_file.name)
        logging.info('Create image %s', gce_name)

        return self.compute.ex_create_image(
            name=gce_name,
            family=gce_family,
            volume=url,
            guest_os_features=(
                'UEFI_COMPATIBLE',
                'VIRTIO_SCSI_MULTIQUEUE',
            ),
        )

    def delete_file(self, image, gce_file):
        """ Delete file from Storage """
        logging.info('Deleting file %s/%s', gce_file.container.name, gce_file.name)

        self.storage.delete_object(gce_file)

    def upload_file(self, image, gce_name):
        """ Upload file to Storage """
        file_out = '{}.tar.gz'.format(gce_name)

        logging.info('Uploading file to %s/%s', self.bucket, file_out)

        with image.open_tar() as tar:
            f = tar.fileobj
            f.seek(0)
            return self.storage.upload_object_via_stream(
                iterator=self.gzip_compress(f),
                container=self.storage_container,
                object_name=file_out,
                extra={'content_type': 'application/octet-stream'},
            )

    @staticmethod
    def gzip_compress(f):
        """ Transparent compress stream with gzip """
        c = zlib.compressobj(
            level=3,
            wbits=31,
        )

        while True:
            s = f.read(65536)
            if not s:
                break
            s = c.compress(s)
            if s:
                yield s

        yield c.flush()


class UploadGceCommand(UploadBaseCommand):
    argparser_name = 'upload-gce'
    argparser_help = 'upload Debian images to GCE'

    @classmethod
    def _argparse_register(cls, parser, config):
        super()._argparse_register(parser, config)

        parser.add_argument(
            '--project',
            help='create images in this Google Cloud project',
            metavar='PROJECT',
            required=True,
        )
        parser.add_argument(
            '--bucket',
            help='create temporary image file in this Google Storage bucket',
            metavar='BUCKET',
            required=True,
        )
        parser.add_argument(
            '--auth',
            action=argparse_ext.ActionEnv,
            env='GOOGLE_APPLICATION_CREDENTIALS',
            help='use file for service account credentials',
            metavar='FILE',
        )

    def __init__(self, *, project=None, bucket=None, auth=None, **kw):
        super().__init__(**kw)

        if auth:
            with open(auth, 'r') as f:
                auth = json.load(f)

        self.uploader = ImageUploaderGce(
            output=self.output,
            project=project,
            bucket=bucket,
            auth=auth,
        )


if __name__ == '__main__':
    UploadGceCommand._main()
