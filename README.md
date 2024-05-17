/opt Python
===========

Note: this project is on indefinite hiatus, so if you need something along these lines,
https://github.com/indygreg/python-build-standalone is a better option to consider.

Helpers to build and install an optimised CPython build
using a recent OpenSSL version under `/opt/$VARIANT_NAME`

To customise the target installation path: TBD

The playbook attempts to be generic across at least Debian and Fedora.

The build process
-----------------

Clone the repo, then do:

    $ pipenv sync
    $ pipenv run ansible-playbook --connection=local -i localhost, -v ./configure-build-system.yaml
    $ pipenv run ansible-playbook --connection=local -i localhost, -v ./make-opt-python.yaml

The build system configuration playbook needs passwordless sudo access to install
build dependencies.

The make & install playbook currently needs passwordless sudo access in order
to install into the destination directory. (This should be fixed, so it doesn't
try to escalate privileges if the target is writable for the current user)

Default installation target: `/opt/$USER-python` (e.g. `/opt/ncoghlan-python`)

To use a different target name under `/opt`, override the `VARIANT_NAME`
variable in the make and install playbook:

    $ pipenv run ansible-playbook --connection=local -i localhost, -v ./make-opt-python.yaml \
        --extra-vars "VARIANT_NAME=my-custom-python"


Checking submodule versions
---------------------------

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
