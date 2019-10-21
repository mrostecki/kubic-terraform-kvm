#!/usr/bin/python3
import argparse
import hashlib
import os
import string
import sys
from functools import reduce
from urllib.request import urlretrieve, urlopen

DEFAULT_REPOSITORY = "openSUSE_Tumbleweed"
DEFAULT_IMAGE = 'openSUSE-MicroOS.x86_64-Kubic-kubeadm-kvm-and-xen.qcow2'

def image_url(repository: str, image: str) -> str:
    return f"https://download.opensuse.org/repositories/devel:/kubic:/images/{repository}/{image}"

def download_file(url: str) -> str:
    with urlopen(url) as f:
        return f.read().decode('utf-8')

def local_sha256(filename: str) -> str:
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        reduce(lambda _, c: sha256.update(c), iter(lambda: f.read(sha256.block_size * 128), b''), None)
    return sha256.hexdigest()

def remote_sha256(url: str) -> str:
    data = download_file(url + '.sha256')
    return [l for l in data.splitlines() if '.qcow2' in l][0].split()[0]

def download_image(url: str, dst: str):
    last_percent_reported = 0

    def reporthook(count, blockSize, totalSize):
        nonlocal last_percent_reported
        percent = int(count * blockSize * 100 / totalSize)
        progress = int(count * blockSize * 50 / totalSize)

        if last_percent_reported == percent:
            return

        sys.stdout.write("\r[%s%s] %d%%" % ('=' * progress, ' ' * (50-progress), percent))
        sys.stdout.flush()

        last_percent_reported = percent

    print("downloading " + url)

    urlretrieve(url, dst, reporthook=reporthook)
    print()

def cloudinit_config(ssh_pub_key_path: str):
    ssh_pub_key = None
    try:
        with open(os.path.expanduser("~/.ssh/id_rsa.pub"), "r") as f:
            ssh_pub_key = f.read().rstrip()
    except FileNotFoundError:
        print("Could not find a public SSH key. Please generate it with "
              "ssh-keygen command.", file=sys.stderr)
        exit(1)

    tmpl = None
    with open("commoninit.cfg.in", "r") as f:
        tmpl = string.Template(f.read())
    cfg = tmpl.substitute({"ssh_pub_key": ssh_pub_key})
    with open("commoninit.cfg", "w") as f:
        f.write(cfg)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--repository", action="store", type=str,
                        dest="repository", default=DEFAULT_REPOSITORY,
                        help="OBS repository to download the image from "
                        f"(default: {DEFAULT_REPOSITORY})")
    parser.add_argument("-i", "--image", action="store", type=str,
                        dest="image", default=DEFAULT_IMAGE,
                        help=f"Image name (default: {DEFAULT_IMAGE}")
    parser.add_argument("-s", "--ssh-pub-key", action="store", type=str,
                        dest="ssh_pub_key",
                        default=os.path.expanduser("~/.ssh/id_rsa.pub"),
                        help="Path to the SSH public key to inject into "
                        "nodes")
    args = parser.parse_args()
    dst = 'kubic.qcow2'
    url = image_url(args.repository, args.image)
    if os.path.isfile(dst) and local_sha256(dst) == remote_sha256(url):
        print('VM image already downloaded.')
    else:
        download_image(url, dst)
    print('Initializing cloudinit config.')
    cloudinit_config(args.ssh_pub_key)
