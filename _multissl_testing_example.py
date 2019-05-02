#!/usr/bin/python3
"""Build an optimized Python in a /opt directory

The script uses the cpython and openssl git submodules under sources to:

1. Build OpenSSL under the specified target directory
2. Build an optimised Python under the specified target directory

The script can be run from anywhere, and always builds the directory
containing it.

The script uses LD_RUN_PATH, LD_LIBRARY_PATH, CPPFLAGS and LDFLAGS to bend
search paths for header files and shared libraries. It's known to work on
Linux with GCC.

(c) 2019 Nick Coghlan <ncoghlan@gmail.com>

Derived from https://github.com/python/cpython/blob/master/Tools/ssl/multissltests.py

(which is (c) 2013-2017 Christian Heimes <christian@python.org>)
"""
from __future__ import print_function

import argparse
from datetime import datetime
import getpass
import logging
import os
import subprocess
import shutil
import sys
import tarfile


log = logging.getLogger(__name__)

# Build relative to the current directory
_HERE = os.path.dirname(os.path.abspath(__file__))

# By default install into /opt/$USER
_DEFAULT_PREFIX = "/opt/" + getpass.getuser()

parser = argparse.ArgumentParser(
    prog='makeoptpython',
    description=(
        "Build Python with a recent OpenSSL under /opt/<NAME>."
    )
)
parser.add_argument(
    '--debug',
    action='store_true',
    help="Enable debug logging",
)
parser.add_argument(
    '--prefix',
    default=_DEFAULT_PREFIX,
    help="Default install directory"
)


class AbstractBuilder(object):
    library = None
    url_template = None
    src_template = None
    build_template = None
    install_target = 'install'

    module_files = ("Modules/_ssl.c",
                    "Modules/_hashopenssl.c")
    module_libs = ("_ssl", "_hashlib")

    def __init__(self, version, args):
        self.version = version
        self.args = args
        # installation directory
        self.install_dir = os.path.join(
            os.path.join(args.base_directory, self.library.lower()), version
        )
        # source file
        self.src_dir = os.path.join(args.base_directory, 'src')
        self.src_file = os.path.join(
            self.src_dir, self.src_template.format(version))
        # build directory (removed after install)
        self.build_dir = os.path.join(
            self.src_dir, self.build_template.format(version))
        self.system = args.system

    def __str__(self):
        return "<{0.__class__.__name__} for {0.version}>".format(self)

    def __eq__(self, other):
        if not isinstance(other, AbstractBuilder):
            return NotImplemented
        return (
            self.library == other.library
            and self.version == other.version
        )

    def __hash__(self):
        return hash((self.library, self.version))

    @property
    def openssl_cli(self):
        """openssl CLI binary"""
        return os.path.join(self.install_dir, "bin", "openssl")

    @property
    def openssl_version(self):
        """output of 'bin/openssl version'"""
        cmd = [self.openssl_cli, "version"]
        return self._subprocess_output(cmd)

    @property
    def pyssl_version(self):
        """Value of ssl.OPENSSL_VERSION"""
        cmd = [
            sys.executable,
            '-c', 'import ssl; print(ssl.OPENSSL_VERSION)'
        ]
        return self._subprocess_output(cmd)

    @property
    def include_dir(self):
        return os.path.join(self.install_dir, "include")

    @property
    def lib_dir(self):
        return os.path.join(self.install_dir, "lib")

    @property
    def has_openssl(self):
        return os.path.isfile(self.openssl_cli)

    @property
    def has_src(self):
        return os.path.isfile(self.src_file)

    def _subprocess_call(self, cmd, env=None, **kwargs):
        log.debug("Call '{}'".format(" ".join(cmd)))
        return subprocess.check_call(cmd, env=env, **kwargs)

    def _subprocess_output(self, cmd, env=None, **kwargs):
        log.debug("Call '{}'".format(" ".join(cmd)))
        if env is None:
            env = os.environ.copy()
            env["LD_LIBRARY_PATH"] = self.lib_dir
        out = subprocess.check_output(cmd, env=env, **kwargs)
        return out.strip().decode("utf-8")

    def _download_src(self):
        """Download sources"""
        src_dir = os.path.dirname(self.src_file)
        if not os.path.isdir(src_dir):
            os.makedirs(src_dir)
        url = self.url_template.format(self.version)
        log.info("Downloading from {}".format(url))
        req = urlopen(url)
        # KISS, read all, write all
        data = req.read()
        log.info("Storing {}".format(self.src_file))
        with open(self.src_file, "wb") as f:
            f.write(data)

    def _unpack_src(self):
        """Unpack tar.gz bundle"""
        # cleanup
        if os.path.isdir(self.build_dir):
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir)

        tf = tarfile.open(self.src_file)
        name = self.build_template.format(self.version)
        base = name + '/'
        # force extraction into build dir
        members = tf.getmembers()
        for member in list(members):
            if member.name == name:
                members.remove(member)
            elif not member.name.startswith(base):
                raise ValueError(member.name, base)
            member.name = member.name[len(base):].lstrip('/')
        log.info("Unpacking files to {}".format(self.build_dir))
        tf.extractall(self.build_dir, members)

    def _build_src(self):
        """Now build openssl"""
        log.info("Running build in {}".format(self.build_dir))
        cwd = self.build_dir
        cmd = [
            "./config",
            "shared", "--debug",
            "--prefix={}".format(self.install_dir)
        ]
        env = os.environ.copy()
        # set rpath
        env["LD_RUN_PATH"] = self.lib_dir
        if self.system:
            env['SYSTEM'] = self.system
        self._subprocess_call(cmd, cwd=cwd, env=env)
        # Old OpenSSL versions do not support parallel builds.
        self._subprocess_call(["make", "-j1"], cwd=cwd, env=env)

    def _make_install(self):
        self._subprocess_call(
            ["make", "-j1", self.install_target],
            cwd=self.build_dir
        )
        if not self.args.keep_sources:
            shutil.rmtree(self.build_dir)

    def install(self):
        log.info(self.openssl_cli)
        if not self.has_openssl or self.args.force:
            if not self.has_src:
                self._download_src()
            else:
                log.debug("Already has src {}".format(self.src_file))
            self._unpack_src()
            self._build_src()
            self._make_install()
        else:
            log.info("Already has installation {}".format(self.install_dir))
        # validate installation
        version = self.openssl_version
        if self.version not in version:
            raise ValueError(version)

    def recompile_pymods(self):
        log.warning("Using build from {}".format(self.build_dir))
        # force a rebuild of all modules that use OpenSSL APIs
        for fname in self.module_files:
            os.utime(fname, None)
        # remove all build artefacts
        for root, dirs, files in os.walk('build'):
            for filename in files:
                if filename.startswith(self.module_libs):
                    os.unlink(os.path.join(root, filename))

        # overwrite header and library search paths
        env = os.environ.copy()
        env["CPPFLAGS"] = "-I{}".format(self.include_dir)
        env["LDFLAGS"] = "-L{}".format(self.lib_dir)
        # set rpath
        env["LD_RUN_PATH"] = self.lib_dir

        log.info("Rebuilding Python modules")
        cmd = [sys.executable, "setup.py", "build"]
        self._subprocess_call(cmd, env=env)
        self.check_imports()

    def check_imports(self):
        cmd = [sys.executable, "-c", "import _ssl; import _hashlib"]
        self._subprocess_call(cmd)

    def check_pyssl(self):
        version = self.pyssl_version
        if self.version not in version:
            raise ValueError(version)

    def run_python_tests(self, tests, network=True):
        if not tests:
            cmd = [sys.executable, 'Lib/test/ssltests.py', '-j0']
        elif sys.version_info < (3, 3):
            cmd = [sys.executable, '-m', 'test.regrtest']
        else:
            cmd = [sys.executable, '-m', 'test', '-j0']
        if network:
            cmd.extend(['-u', 'network', '-u', 'urlfetch'])
        cmd.extend(['-w', '-r'])
        cmd.extend(tests)
        self._subprocess_call(cmd, stdout=None)


class BuildOpenSSL(AbstractBuilder):
    library = "OpenSSL"
    url_template = "https://www.openssl.org/source/openssl-{}.tar.gz"
    src_template = "openssl-{}.tar.gz"
    build_template = "openssl-{}"
    # only install software, skip docs
    install_target = 'install_sw'


class BuildLibreSSL(AbstractBuilder):
    library = "LibreSSL"
    url_template = (
        "https://ftp.openbsd.org/pub/OpenBSD/LibreSSL/libressl-{}.tar.gz")
    src_template = "libressl-{}.tar.gz"
    build_template = "libressl-{}"


def configure_make():
    if not os.path.isfile('Makefile'):
        log.info('Running ./configure')
        subprocess.check_call([
            './configure', '--config-cache', '--quiet',
            '--with-pydebug'
        ])

    log.info('Running make')
    subprocess.check_call(['make', '--quiet'])


def main():
    args = parser.parse_args()
    if not args.openssl and not args.libressl:
        args.openssl = list(OPENSSL_RECENT_VERSIONS)
        args.libressl = list(LIBRESSL_RECENT_VERSIONS)
        if not args.disable_ancient:
            args.openssl.extend(OPENSSL_OLD_VERSIONS)
            args.libressl.extend(LIBRESSL_OLD_VERSIONS)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="*** %(levelname)s %(message)s"
    )

    start = datetime.now()

    if args.steps in {'modules', 'tests'}:
        for name in ['setup.py', 'Modules/_ssl.c']:
            if not os.path.isfile(os.path.join(PYTHONROOT, name)):
                parser.error(
                    "Must be executed from CPython build dir"
                )
        if not os.path.samefile('python', sys.executable):
            parser.error(
                "Must be executed with ./python from CPython build dir"
            )
        # check for configure and run make
        configure_make()

    # download and register builder
    builds = []

    for version in args.openssl:
        build = BuildOpenSSL(
            version,
            args
        )
        build.install()
        builds.append(build)

    for version in args.libressl:
        build = BuildLibreSSL(
            version,
            args
        )
        build.install()
        builds.append(build)

    if args.steps in {'modules', 'tests'}:
        for build in builds:
            try:
                build.recompile_pymods()
                build.check_pyssl()
                if args.steps == 'tests':
                    build.run_python_tests(
                        tests=args.tests,
                        network=args.network,
                    )
            except Exception as e:
                log.exception("%s failed", build)
                print("{} failed: {}".format(build, e), file=sys.stderr)
                sys.exit(2)

    log.info("\n{} finished in {}".format(
            args.steps.capitalize(),
            datetime.now() - start
        ))
    print('Python: ', sys.version)
    if args.steps == 'tests':
        if args.tests:
            print('Executed Tests:', ' '.join(args.tests))
        else:
            print('Executed all SSL tests.')

    print('OpenSSL / LibreSSL versions:')
    for build in builds:
        print("    * {0.library} {0.version}".format(build))


if __name__ == "__main__":
    main()
