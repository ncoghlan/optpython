/opt Python
===========

Helpers to build and install an optimised CPython build
using a recent OpenSSL version under /opt/<name>

Default installation target: /opt/custom-python
To customise the target installation path: TBD

The playbook attempts to be generic across at least Debian and Fedora.

The build process
-----------------

Clone the repo, then do:

    $ pipenv sync
    $ pipenv run ansible-playbook -i localhost, -v ./configure-build-system.yaml
    $ pipenv run ansible-playbook -i localhost, -v ./make-opt-python.yaml

The build system configuration playbook needs passwordless sudo access to install
build dependencies.


Checking submodule status
-------------------------

    $ git submodule status


Updating a submodule to a newer tag
-----------------------------------

Updating CPython example:

    $ cd sources/cpython
    $ git fetch
    $ git checkout v3.7.3
    $ cd ..
    $ git add cpython
    $ git commit -m "Update CPython submodule to 3.7.3"

Updating OpenSSL is similar, just using `sources/openssl` instead.
