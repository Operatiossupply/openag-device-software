# Import python modules
import subprocess
import socket
import json
import os
import platform
import time
import urllib.request
import uuid

from app.viewers import UpgradeViewer
from device.state import State


class UpgradeUtils:
    """ Utilities to upgrade this apt package. """

    # class variable to hold a reference to the state.upgrade dict
    ref_state = State()

    # --------------------------------------------------------------------------
    # Saves a reference to the state as a static class var.
    @staticmethod
    def save_state(state):
        UpgradeUtils.ref_state = state

    # --------------------------------------------------------------------------
    # Return a dict of all the fields we display on the Django Upgrade tab.
    @staticmethod
    def get_status():
        return UpgradeUtils.ref_state.upgrade

    # ------------------------------------------------------------------------
    # Update our dict with the software versions.
    # Only call once a day, this will take a few minutes to execute.
    @staticmethod
    def update_dict():
        """
        sudo apt-get update
        apt-cache policy openagbrain
        openagbrain:
          Installed: (none)
          Candidate: 0.1-2
        """
        try:
            UpgradeUtils.ref_state.upgrade['status'] = \
                'Checking for upgrades...'

            # update this machines list of available packages
            cmd = ['sudo', 'apt-get', 'update']
            subprocess.run(cmd)

            # command and list of args as list of strings
            cmd = ['apt-cache', 'policy', 'openagbrain']
            with subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE) as proc1:
                output = proc1.stdout.read().decode("utf-8")
                output += proc1.stderr.read().decode("utf-8")
                lines = output.splitlines()
                installed = ''
                candidate = ''
                for line in lines:
                    tokens = line.split()
                    for token in tokens:
                        if token.startswith('Installed:'):
                            installed = tokens[1]
                            break
                        elif token.startswith('Candidate:'):
                            candidate = tokens[1]
                            break

                UpgradeUtils.ref_state.upgrade['current_version'] = installed
                UpgradeUtils.ref_state.upgrade['upgrade_version'] = candidate
                # very simple upgrade logic, trust debian package logic
                if '(none)' == installed or \
                        installed != candidate:
                    UpgradeUtils.ref_state.upgrade['show_upgrade'] = True

            UpgradeUtils.ref_state.upgrade['status'] = 'Up to date.'
            if UpgradeUtils.ref_state.upgrade.get('show_upgrade', False):
                UpgradeUtils.ref_state.upgrade['status'] = \
                    'Software upgrade is available.'

        except:
            return False
        return True



    # ------------------------------------------------------------------------
    # Update our debian package with the latest version available.
    @staticmethod
    def update_software():
        """
        If we call 'sudo apt-get install -y openagbrain' here, inside django,
        we will create a deadlock where apt can't complete the install because
        it is run as a child of the process it has to terminate.

        So, let's get creative:

        0. This logic assumes django is being run as root with sudo or 
           from the rc.local service.  It also assumes that 'apt-get update'
           has already been run and we know there is an update available.

        1. Write file /tmp/openagbrain-at-commands with contents:
            systemctl stop rc.local
            apt-get install -y openagbrain

        2. Create an 'at' job which runs the above commands in a minute:
            at -f /tmp/openagbrain-at-commands now + 1 minute
        """
        try:
            fn = '/tmp/openagbrain-at-commands'
            f = open(fn, 'w')
            f.write('systemctl stop rc.local\n')
            f.write('apt-get install -y openagbrain\n')
            f.close()

            # update our debian package
            cmd = ['at', '-f', '/tmp/openagbrain-at-commands', \
                   'now', '+', '1', 'minute']
            subprocess.Popen(cmd)

            UpgradeUtils.ref_state.upgrade['status'] = \
                'Upgrading, will restart in 2 minutes...'
            UpgradeUtils.ref_state.upgrade['show_upgrade'] = False

        except Exception as e:
            UpgradeUtils.ref_state.upgrade['error'] = e

        return UpgradeUtils.ref_state.upgrade


    # ------------------------------------------------------------------------
    # Check for updates
    @staticmethod
    def check():
        UpgradeUtils.update_dict()
        return UpgradeUtils.get_status()

