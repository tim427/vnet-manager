from logging import getLogger
from yaml import safe_dump
from pylxd.exceptions import NotFound
from os.path import isfile, isdir, join, basename
from os import listdir
from sys import modules

from vnet_manager.providers.lxc import get_lxd_client
from vnet_manager.conf import settings

logger = getLogger(__name__)


def put_files_on_machine(config):
    for name, data in config["machines"].items():
        if "files" in data:
            provider = settings.MACHINE_TYPE_PROVIDER_MAPPING[data["type"]]
            logger.info("Putting requested files on machine {}".format(name))
            select_files_and_put_on_machine(name, data["files"], provider)


def select_files_and_put_on_machine(machine, files, provider):
    """
    Checks if the requested files are files or a dict and calls the provider file place function for each file
    :param str machine: The machine to put the files on
    :param dict files: The machines file dict from the config
    :param str provider: The provider of the machine
    """
    # Get the files
    for host_path, guest_path in files.items():
        if isdir(host_path):
            logger.debug("Getting files from file dir {}".format(host_path))
            files = [join(host_path, f) for f in listdir(host_path)]
            for file_path in files:
                # Place the file on the machine
                getattr(modules[__name__], "place_file_on_{}_machine".format(provider))(
                    machine, file_path, join(guest_path, basename(file_path))
                )
        elif isfile(host_path):
            getattr(modules[__name__], "place_file_on_{}_machine".format(provider))(machine, host_path, guest_path)
        else:
            logger.error("Tried to select file {} for copying, but it is neither a file nor a directory".format(host_path))


def place_file_on_lxc_machine(container, host_file_path, guest_file_path):
    """
    Places a local file on a LXC container
    :param str container: The container to place the file on
    :param str host_file_path: The file to copy to the guest
    :param str guest_file_path: The path to copy the file to
    """
    # Some sanity checks
    try:
        machine = get_lxd_client().containers.get(container)
    except NotFound:
        logger.warning("Tried to copy {} to LXC container {}, but the container doesn't exists".format(host_file_path, container))
        return
    if not isfile(host_file_path):
        logger.error("Tried to copy {} to LXC container {}, but the file doesn't exists".format(host_file_path, container))
        return

    # Get the file contents
    with open(host_file_path, "r") as fh:
        file_data = fh.read()
    # Place the file content
    logger.debug("Copying {} to container {} at path {}".format(host_file_path, container, guest_file_path))
    machine.files.put(guest_file_path, file_data)


def place_lxc_interface_configuration_on_container(config, container):
    """
    Places the interfaces configuration on the LXC container
    :param dict config: The config generated by get_config()
    :param str container: The name of the container to place the interfaces configuration on
    """
    logger.debug("Generating network config for LXC container {}".format(container))
    network_conf = {"network": {"version": 2, "renderer": "networkd", "ethernets": {},}}
    for int_name, int_data in config["machines"][container]["interfaces"].items():
        addresses = []
        if "ipv4" in int_data:
            addresses.append(int_data["ipv4"])
        if "ipv6" in int_data:
            addresses.append(int_data["ipv6"])
        network_conf["network"]["ethernets"][int_name] = {
            "dhcp4": "no",
            "dhcp6": "no",
            "match": {"macaddress": int_data["mac"],},
            "set-name": int_name,
            "addresses": addresses,
        }
    logger.info("Placing network config on LXC container {}".format(container))
    machine = get_lxd_client().containers.get(container)
    machine.files.put("/etc/netplan/10-vnet-config.yaml", safe_dump(network_conf))


def generate_vnet_hosts_file(config):
    """
    Generates the machines /etc/hosts file based on the info in the config
    The generated file is placed on disk
    :param dict config: The config generated by get_config()
    """
    logger.info("Generating VNet hosts file")
    vnet_hosts = []
    for machine_name, machine_data in config["machines"].items():
        for int_data in machine_data["interfaces"].values():
            if "ipv4" in int_data:
                vnet_hosts.append("{}   {}".format(int_data["ipv4"].split("/")[0], machine_name))
            if "ipv6" in int_data:
                vnet_hosts.append("{}   {}".format(int_data["ipv6"].split("/")[0], machine_name))
    vnet_etc_hosts_data = settings.VNET_STATIC_HOSTS_FILE_PART + "\n".join(vnet_hosts)
    with open(settings.VNET_ETC_HOSTS_FILE_PATH, "w") as fh:
        fh.write(vnet_etc_hosts_data)


def place_vnet_hosts_file_on_machines(config):
    """
    Places the generated /etc/hosts file on all VNet machines defined in the config
    :param dict config: The config generated by get_config()
    """
    logger.info("Placing VNet /etc/hosts file on machines")
    for name, data in config["machines"].items():
        provider = settings.MACHINE_TYPE_PROVIDER_MAPPING[data["type"]]
        select_files_and_put_on_machine(name, {settings.VNET_ETC_HOSTS_FILE_PATH: "/etc/hosts"}, provider)
