from unittest.mock import Mock
from pylxd.exceptions import NotFound

from vnet_manager.tests import VNetTestCase
from vnet_manager.conf import settings
from vnet_manager.operations.machine import show_status, check_if_lxc_machine_exists, get_lxc_machine_status


class TestShowStatus(VNetTestCase):
    def setUp(self) -> None:
        self.tabulate = self.set_up_patch("vnet_manager.operations.machine.tabulate")
        self.get_lxc_machine_status = self.set_up_patch("vnet_manager.operations.machine.get_lxc_machine_status")
        self.get_lxc_machine_status.return_value = ["router", "up", "LXC"]
        self.config = settings.CONFIG
        # Only 1 machine for less output
        self.config["machines"].pop("router101", None)
        self.config["machines"].pop("router102", None)

    def test_show_status_call_get_lxc_machine_status(self):
        show_status(self.config)
        self.get_lxc_machine_status.assert_called_once_with("router100")

    def test_show_status_makes_correct_tabulate_call(self):
        show_status(self.config)
        self.tabulate.assert_called_once_with(
            [self.get_lxc_machine_status.return_value], headers=["Name", "Status", "Provider"], tablefmt="pretty"
        )


class TestCheckIfLXCMachineExists(VNetTestCase):
    def setUp(self) -> None:
        self.machine = Mock()
        self.lxd_client = self.set_up_patch("vnet_manager.operations.machine.get_lxd_client")
        self.lxd_client.return_value = self.machine

    def test_check_if_lxc_machine_exists_calls_exists_method(self):
        check_if_lxc_machine_exists("test")
        self.machine.containers.exists.assert_called_once_with("test")

    def test_check_if_lxc_machine_exists_returns_value_of_exists_method(self):
        self.machine.containers.exists.return_value = False
        self.assertFalse(check_if_lxc_machine_exists("test"))


class TestGetLXCMachineStatus(VNetTestCase):
    def setUp(self) -> None:
        self.machine = Mock()
        self.lxd_client = self.set_up_patch("vnet_manager.operations.machine.get_lxd_client")
        self.lxd_client.return_value = self.machine

    def test_get_lxc_machine_calls_lxd_client(self):
        get_lxc_machine_status("test")
        self.lxd_client.assert_called_once_with()

    def test_get_lxc_machine_status_calls_get_method(self):
        get_lxc_machine_status("test")
        self.machine.containers.get.assert_called_once_with("test")

    def test_get_lxc_machine_status_returns_list_with_status_of_container(self):
        self.machine.containers.get.return_value.status = "banaan"
        self.assertEqual(get_lxc_machine_status("test"), ["test", "banaan", "LXC"])

    def test_get_lxc_machine_status_returns_na_on_not_found_exception(self):
        self.machine.containers.get.side_effect = NotFound(response="blaap")
        self.assertEqual(get_lxc_machine_status("test"), ["test", "NA", "LXC"])
