# Network module for the XRIQ Azure staging-devnet.
#
# Private virtual network with an application subnet, a delegated subnet for the
# PostgreSQL Flexible Server, and a network security group. Internal services
# stay private; inbound SSH is only opened when operator_allowed_cidr is set.

variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "operator_allowed_cidr" {
  type    = string
  default = null
}

variable "tags" {
  type = map(string)
}

resource "azurerm_virtual_network" "main" {
  name                = "${var.name_prefix}-vnet"
  resource_group_name = var.resource_group_name
  location            = var.location
  address_space       = ["10.42.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "app" {
  name                 = "app"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.42.1.0/24"]
}

resource "azurerm_subnet" "database" {
  name                 = "database"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.42.2.0/24"]

  delegation {
    name = "postgresql-flexible"
    service_delegation {
      name    = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_network_security_group" "app" {
  name                = "${var.name_prefix}-app-nsg"
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
}

# Optional inbound SSH, only when an operator CIDR is provided.
resource "azurerm_network_security_rule" "ssh" {
  count                       = var.operator_allowed_cidr == null ? 0 : 1
  name                        = "allow-operator-ssh"
  priority                    = 1000
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.operator_allowed_cidr
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.app.name
}

resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}

output "vnet_id" {
  value = azurerm_virtual_network.main.id
}

output "vnet_name" {
  value = azurerm_virtual_network.main.name
}

output "app_subnet_id" {
  value = azurerm_subnet.app.id
}

output "database_subnet_id" {
  value = azurerm_subnet.database.id
}

output "app_nsg_id" {
  value = azurerm_network_security_group.app.id
}
