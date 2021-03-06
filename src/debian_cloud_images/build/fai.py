# SPDX-License-Identifier: GPL-2.0-or-later

import logging
import pathlib
import os.path
import subprocess

from typing import Dict, List


dci_path = os.path.join(os.path.dirname(__file__), '../..')
fai_config_path = os.path.join(os.path.dirname(__file__), 'fai_config')
logger = logging.getLogger(__name__)


class RunFAI:
    output_filenam: pathlib.Path
    classes: List[str]
    size_gb: int
    env: Dict[str, str]
    fai_filename: str

    def __init__(
            self, *,
            output_filename: pathlib.Path,
            classes: List[str],
            size_gb: int,
            env: Dict[str, str],
            fai_filename: str='fai-diskimage',  # noqa:E252
    ):
        self.output_filename = output_filename
        self.classes = classes
        self.size_gb = size_gb
        self.env = env
        self.fai_filename = fai_filename

    def __call__(self, run: bool, *, popen=subprocess.Popen, dci_path=dci_path) -> None:
        cmd = self.command(dci_path)

        if run:
            logger.info(f'Running FAI: {" ".join(cmd)}')

            try:
                process = popen(cmd)
                retcode = process.wait()
                if retcode:
                    raise subprocess.CalledProcessError(retcode, cmd)

            finally:
                process.kill()

        else:
            logger.info(f'Would run FAI: {" ".join(cmd)}')

    def command(self, dci_path: str) -> tuple:
        return (
            'sudo',
            'env',
            f'PYTHONPATH={dci_path}',
            'http_proxy=' + os.getenv('http_proxy', ''),
        ) + tuple(f'{k}={v}' for k, v in sorted(self.env.items())) + (
            self.fai_filename,
            '--verbose',
            '--hostname', 'debian',
            '--class', ','.join(self.classes),
            '--size', str(self.size_gb),
            '--cspace', fai_config_path,
            self.output_filename.as_posix(),
        )
