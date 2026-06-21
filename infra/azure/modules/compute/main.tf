# Compute module for the XRIQ Azure staging-devnet.
#
# A single small Linux VM to run the XRIQ node/API/indexer for staging. It has no
# public IP (private subnet only); operator access is via the network's optional
# SSH rule plus a bastion/VPN added later. Admin auth is SSH-public-key only;
# password auth is disabled. No secrets are stored here.

variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "vm_size" {
  type = string
}

variable "admin_username" {
  type = string
}

variable "ssh_public_key" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "azurerm_network_interface" "node" {
  name                = "${var.name_prefix}-node-nic"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags

  ip_configuration {
    name                          = "internal"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "node" {
  name                            = "${var.name_prefix}-node"
  resource_group_name             = var.resource_group_name
  location                        = var.location
  size                            = var.vm_size
  admin_username                  = var.admin_username
  network_interface_ids           = [azurerm_network_interface.node.id]
  disable_password_authentication = true
  tags                            = var.tags

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }
}

output "vm_id" {
  value = azurerm_linux_virtual_machine.node.id
}

output "private_ip_address" {
  value = azurerm_network_interface.node.private_ip_address
}
