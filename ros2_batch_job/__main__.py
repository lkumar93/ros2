# Copyright 2015 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
import platform
import sys

# Make sure we're using Python3
assert sys.version.startswith('3'), "This script is only meant to work with Python3"

# Make sure to get osrf_pycommon from the vendor folder
vendor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor'))
sys.path.insert(0, os.path.join(vendor_path, 'osrf_pycommon'))
import osrf_pycommon
# Assert that we got it from the right place
assert osrf_pycommon.__file__.startswith(vendor_path), \
    ("osrf_pycommon imported from '{0}' which is not in the vendor folder '{1}'"
     .format(osrf_pycommon.__file__, vendor_path))
from osrf_pycommon.cli_utils.common import extract_argument_group

from .util import change_directory
from .util import clean_workspace
from .util import force_color
from .util import generated_venv_vars
from .util import info
from .util import log
from .util import UnbufferedIO

# Enforce unbuffered output
sys.stdout = UnbufferedIO(sys.stdout)
sys.stderr = UnbufferedIO(sys.stderr)

pip_dependencies = [
    'nose',
    'pep8',
    'pyflakes',
    'flake8',
    'mock',
    'coverage',
    'EmPy',
    'vcstool',
]


def main(sysargv=None):
    args = get_args(sysargv=sysargv)
    return run(args, build_and_test)


def get_args(sysargv=None, skip_white_space_in=False, skip_connext=False, add_ros1=False):
    parser = argparse.ArgumentParser(
        description="Builds the ROS2 repositories as a single batch job")
    parser.add_argument(
        '--repo-file-url',
        default='https://raw.githubusercontent.com/ros2/ros2/master/ros2.repos',
        help="url of the ros2.repos file to fetch and use for the basis of the batch job")
    parser.add_argument(
        '--test-branch', default=None,
        help="branch to attempt to checkout before doing batch job")
    if not skip_white_space_in:
        parser.add_argument(
            '--white-space-in', nargs='*', default=None,
            choices=['sourcespace', 'buildspace', 'installspace', 'workspace'],
            help="which folder structures in which white space should be added")
    parser.add_argument(
        '--do-venv', default=False, action='store_true',
        help="create and use a virtual env in the build process")
    parser.add_argument(
        '--os', default=None, choices=['linux', 'osx', 'windows'])
    if not skip_connext:
        parser.add_argument(
            '--connext', default=False, action='store_true',
            help="try to build with connext")
    parser.add_argument(
        '--isolated', default=False, action='store_true',
        help="build and install each package a separate folders")
    parser.add_argument(
        '--force-ansi-color', default=False, action='store_true',
        help="forces this program to output ansi color")
    if add_ros1:
        parser.add_argument(
            '--ros1-path', default=None,
            help="path of ROS 1 workspace to be sourced")
    parser.add_argument(
        '--ament-args', default=None,
        help='arguments passed to ament')

    argv = sysargv[1:] if sysargv is not None else sys.argv[1:]
    argv, ament_args = extract_argument_group(argv, '--ament-args')
    args = parser.parse_args(argv)
    args.ament_args = ament_args
    if skip_white_space_in:
        args.white_space_in = None
    if skip_connext:
        args.connext = False
    if not add_ros1:
        args.ros1_path = None
    return args


def build_and_test(args, job):
    ament_py = '"%s"' % os.path.join(
        '.', args.sourcespace, 'ament', 'ament_tools', 'scripts', 'ament.py'
    )
    # Now run ament build
    job.run([
        '"%s"' % job.python, '-u', ament_py, 'build', '--build-tests',
        '--build-space', '"%s"' % args.buildspace,
        '--install-space', '"%s"' % args.installspace,
        '"%s"' % args.sourcespace
    ] + (['--isolated'] if args.isolated else []) + args.ament_args, shell=True)
    # Run tests
    ret_test = job.run([
        '"%s"' % job.python, '-u', ament_py, 'test',
        '--build-space', '"%s"' % args.buildspace,
        '--install-space', '"%s"' % args.installspace,
        # Skip building and installing, since we just did that successfully.
        '--skip-build', '--skip-install',
        '"%s"' % args.sourcespace
    ] + (['--isolated'] if args.isolated else []) + args.ament_args,
        exit_on_error=False, shell=True)
    info("ament.py test returned: '{0}'".format(ret_test))
    # Collect the test results
    ret_test_results = job.run(
        ['"%s"' % job.python, '-u', ament_py, 'test_results', '"%s"' % args.buildspace],
        exit_on_error=False, shell=True
    )
    info("ament.py test_results returned: '{0}'".format(ret_test_results))
    # Uncomment this line to failing tests a failrue of this command.
    # return 0 if ret_test == 0 and ret_testr == 0 else 1
    return 0


def run(args, build_function):
    if args.force_ansi_color:
        force_color()

    info("run_ros2_batch called with args:")
    for arg in vars(args):
        info("  - {0}={1}".format(arg, getattr(args, arg)))

    job = None

    args.white_space_in = args.white_space_in or []
    args.workspace = 'work space' if 'workspace' in args.white_space_in else 'workspace'
    args.sourcespace = 'source space' if 'sourcespace' in args.white_space_in else 'src'
    args.buildspace = 'build space' if 'buildspace' in args.white_space_in else 'build'
    args.installspace = 'install space' if 'installspace' in args.white_space_in else 'install'

    platform_name = platform.platform().lower()
    if args.os == 'linux' or platform_name.startswith('linux'):
        args.os = 'linux'
        from .linux_batch import LinuxBatchJob
        job = LinuxBatchJob(args)
    elif args.os == 'osx' or platform_name.startswith('darwin'):
        args.os = 'osx'
        from .osx_batch import OSXBatchJob
        job = OSXBatchJob(args)
    elif args.os == 'windows' or platform_name.startswith('windows'):
        args.os = 'windows'
        from .windows_batch import WindowsBatchJob
        job = WindowsBatchJob(args)

    if args.do_venv and args.os == 'windows':
        sys.exit("--do-venv is not supported on windows")

    # Set the TERM env variable to coerce the output of Make to be colored.
    os.environ['TERM'] = os.environ.get('TERM', 'xterm-256color')
    if args.os == 'windows':
        # Set the ConEmuANSI env variable to trick some programs (vcs) into
        # printing ANSI color codes on Windows.
        os.environ['ConEmuANSI'] = 'ON'

    info("Using workspace: @!{0}", fargs=(args.workspace,))
    clean_workspace(args.workspace)

    # Allow batch job to do OS specific stuff
    job.pre()
    # Check the env
    job.show_env()
    # Make sure virtual env is installed
    if args.os != 'linux':
        # Do not try this on Linux, as elevated privileges are needed.
        # Also there is no good way to get elevated privileges.
        # So the Linux host or Docker vm will need to ensure a modern
        # version of virtualenv is available.
        job.run([sys.executable, '-m', 'pip', 'install', '-U', 'virtualenv'])
    # Now inside of the workspace...
    with change_directory(args.workspace):
        # Enter a venv if asked to
        if args.do_venv:
            job.run([sys.executable, '-m', 'virtualenv', '-p', sys.executable, 'venv'])
            venv_path = os.path.abspath(os.path.join(os.getcwd(), 'venv'))
            venv, venv_python = generated_venv_vars(venv_path)
            job.push_run(venv)  # job.run is now venv
            job.push_python(venv_python)  # job.python is now venv_python
            job.show_env()
        # Update setuptools
        job.run(['"%s"' % job.python, '-m', 'pip', 'install', '-U', 'pip', 'setuptools'],
                shell=True)
        # Print setuptools version
        job.run(['"%s"' % job.python, '-c', '"import setuptools; print(setuptools.__version__)"'],
                shell=True)
        # Print the pip version
        job.run(['"%s"' % job.python, '-m', 'pip', '--version'], shell=True)
        # Install pip dependencies
        job.run(['"%s"' % job.python, '-m', 'pip', 'install', '-U'] + pip_dependencies, shell=True)
        # Get the repositories
        job.run(['curl', '-sk', args.repo_file_url, '-o', 'ros2.repos'])
        # Show the contents
        log("@{bf}==>@| Contents of `ros2.repos`:")
        with open('ros2.repos', 'r') as f:
            print(f.read())
        # Use the repository listing and vcstool to fetch repositories
        if not os.path.exists(args.sourcespace):
            os.makedirs(args.sourcespace)
        # OS X can't invoke a file which has a space in the shebang line
        # therefore invoking vcs explicitly through Python
        if args.do_venv:
            vcs_cmd = ['"%s"' % job.python, '"%s"' % os.path.join(venv_path, 'bin', 'vcs')]
        else:
            vcs_cmd = ['vcs']
        job.run(vcs_cmd + ['import', '"%s"' % args.sourcespace, '--input', 'ros2.repos'],
                shell=True)
        if args.test_branch is not None:
            # Store current branch as well-known branch name for later rebasing
            info("Attempting to create a well known branch name for all the default branches")
            job.run(vcs_cmd + ['custom', '.', '--git', '--args', 'checkout', '-b', '__ci_default'],
                    shell=True)

            # Attempt to switch all the repositories to a given branch
            info("Attempting to switch all repositories to the '{0}' branch"
                 .format(args.test_branch))
            vcs_custom_cmd = vcs_cmd + ['custom', '.', '--args', 'checkout', args.test_branch]
            ret = job.run(vcs_custom_cmd, exit_on_error=False)
            info("'{0}' returned exit code '{1}'", fargs=(" ".join(vcs_custom_cmd), ret))
            print()

            # Attempt to rebase all the repositories to the __ci_default branch
            info("Attempting to rebase all repositories to the '__ci_default' branch")
            vcs_custom_cmd = vcs_cmd + ['custom', '.', '--git', '--args', 'rebase', '__ci_default']
            ret = job.run(vcs_custom_cmd)
            info("'{0}' returned exit code '{1}'", fargs=(" ".join(vcs_custom_cmd), ret))
            print()
        # Show the latest commit log on each repository (includes the commit hash).
        job.run(vcs_cmd + ['log', '-l1', '"%s"' % args.sourcespace], shell=True)
        # Allow the batch job to push custom sourcing onto the run command
        job.setup_env()

        return build_function(args, job)

if __name__ == '__main__':
    sys.exit(main())
