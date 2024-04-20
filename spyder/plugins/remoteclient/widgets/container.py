# -*- coding: utf-8 -*-
#
# Copyright © Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (see spyder/__init__.py for details)

"""Remote client container."""

import json

from qtpy.QtCore import Signal

from spyder.api.translations import _
from spyder.api.widgets.main_container import PluginMainContainer
from spyder.plugins.ipythonconsole.utils.kernel_handler import KernelHandler
from spyder.plugins.remoteclient.api import (
    RemoteClientActions,
    RemoteClientMenus,
    RemoteConsolesMenuSections,
)
from spyder.plugins.remoteclient.api.protocol import ConnectionInfo
from spyder.plugins.remoteclient.widgets import AuthenticationMethod
from spyder.plugins.remoteclient.widgets.connectiondialog import (
    ConnectionDialog,
)


class RemoteClientContainer(PluginMainContainer):

    sig_start_server_requested = Signal(str)
    """
    This signal is used to request starting a remote server.

    Parameters
    ----------
    id: str
        Id of the server that will be started.
    """

    sig_stop_server_requested = Signal(str)
    """
    This signal is used to request stopping a remote server.

    Parameters
    ----------
    id: str
        Id of the server that will be stopped.
    """

    sig_connection_status_changed = Signal(dict)
    """
    This signal is used to update the status of a given connection.

    Parameters
    ----------
    info: ConnectionInfo
        Dictionary with the necessary info to update the status of a
        connection.
    """

    sig_create_ipyclient_requested = Signal(str)
    """
    This signal is used to request starting an IPython console client for a
    remote server.

    Parameters
    ----------
    id: str
        Id of the server for which a client will be created.
    """

    # ---- PluginMainContainer API
    # -------------------------------------------------------------------------
    def setup(self):

        self.create_action(
            RemoteClientActions.ManageConnections,
            _('Manage remote connections...'),
            icon=self._plugin.get_icon(),
            triggered=self._show_connection_dialog,
        )

        self.sig_connection_status_changed.connect(
            self._on_connection_status_changed
        )

    def update_actions(self):
        pass

    # ---- Public API
    # -------------------------------------------------------------------------
    def create_remote_consoles_submenu(self):
        """Create the remote consoles submenu in the Consoles app one."""
        remote_consoles_menu = self.create_menu(
            RemoteClientMenus.RemoteConsoles,
            _("New console in remote server")
        )

        self.add_item_to_menu(
            self.get_action(RemoteClientActions.ManageConnections),
            menu=remote_consoles_menu,
            section=RemoteConsolesMenuSections.ManagerSection
        )

        servers = self.get_conf("servers", {})
        for config_id in servers:
            auth_method = self.get_conf(f"{config_id}/auth_method")
            name = self.get_conf(f"{config_id}/{auth_method}/name")

            action = self.create_action(
                name=config_id,
                text=f"New console in {name} server",
                icon=self.create_icon('ipython_console'),
                triggered=(
                    lambda checked, config_id=config_id:
                    self.sig_create_ipyclient_requested.emit(config_id)
                ),
                overwrite=True
            )
            self.add_item_to_menu(
                action,
                menu=remote_consoles_menu,
                section=RemoteConsolesMenuSections.ConsolesSection
            )

    def connect_kernel_to_ipyclient(self, ipyclient, kernel_info):
        """Connect an IPython console client to a remote kernel."""
        config_id = ipyclient.server_id

        # Get authentication method
        auth_method = self.get_conf(f"{config_id}/auth_method")

        # Set hostname in the format expected by KernelHandler
        address = self.get_conf(f"{config_id}/{auth_method}/address")
        username = self.get_conf(f"{config_id}/{auth_method}/username")
        port = self.get_conf(f"{config_id}/{auth_method}/port")
        hostname = f"{username}@{address}:{port}"

        # Get password or keyfile/passphrase
        if auth_method == AuthenticationMethod.Password:
            password = self.get_conf(f"{config_id}/password", secure=True)
            sshkey = None
        elif auth_method == AuthenticationMethod.KeyFile:
            sshkey = self.get_conf(f"{config_id}/{auth_method}/keyfile")
            passpharse = self.get_conf(f"{config_id}/passpharse", secure=True)
            if passpharse:
                password = passpharse
            else:
                password = None
        else:
            # TODO: Handle the ConfigFile method here
            pass

        # Generate local connection file from kernel info
        connection_file = KernelHandler.new_connection_file()
        with open(connection_file, "w") as f:
            json.dump(kernel_info["connection_info"], f)

        # Create KernelHandler
        try:
            kernel_handler = KernelHandler.from_connection_file(
                connection_file, hostname, sshkey, password
            )
        except Exception as e:
            ipyclient.show_kernel_error(e)
            return

        # Connect to the kernel
        ipyclient.connect_kernel(kernel_handler)

    # ---- Private API
    # -------------------------------------------------------------------------
    def _show_connection_dialog(self):
        connection_dialog = ConnectionDialog(self)

        connection_dialog.sig_start_server_requested.connect(
            self.sig_start_server_requested
        )
        connection_dialog.sig_stop_server_requested.connect(
            self.sig_stop_server_requested
        )

        self.sig_connection_status_changed.connect(
            connection_dialog.sig_connection_status_changed
        )

        connection_dialog.show()

    def _on_connection_status_changed(self, info: ConnectionInfo):
        """Handle changes in connection status."""
        host_id = info["id"]
        status = info["status"]
        message = info["message"]

        # We need to save this info so that we can show the current status in
        # the connection dialog when it's closed and opened again.
        self.set_conf(f"{host_id}/status", status)
        self.set_conf(f"{host_id}/status_message", message)
