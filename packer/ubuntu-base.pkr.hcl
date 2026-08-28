packer {
  required_plugins {
    virtualbox = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/virtualbox"
    }
    vagrant = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/vagrant"
    }
  }
}

variable "iso_url" {
  type    = string
  default = "https://releases.ubuntu.com/20.04/ubuntu-20.04.6-live-server-amd64.iso"
}

# Keep in sync with the SHA256SUMS file published alongside iso_url above -
# Ubuntu point releases change this periodically.
variable "iso_checksum" {
  type    = string
  default = "file:https://releases.ubuntu.com/20.04/SHA256SUMS"
}

variable "vm_name" {
  type    = string
  default = "forensicforge-ubuntu-base"
}

source "virtualbox-iso" "ubuntu_base" {
  guest_os_type = "Ubuntu_64"
  vm_name       = var.vm_name

  iso_url      = var.iso_url
  iso_checksum = var.iso_checksum

  disk_size = 20000
  memory    = 2048
  cpus      = 2

  # Matches the "vagrant"/"vagrant" convention every stock Vagrant base box
  # uses - not a real secret, just the standard disposable-VM credential.
  ssh_username = "vagrant"
  ssh_password = "vagrant"
  ssh_timeout  = "30m"

  http_directory = "http"
  boot_command = [
    "<esc><wait>",
    "linux /casper/vmlinuz --- autoinstall ds=nocloud-net\\;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/ ",
    "<enter><wait>initrd /casper/initrd<enter><wait>boot<enter>",
  ]

  shutdown_command = "echo 'vagrant' | sudo -S shutdown -P now"

  guest_additions_mode = "upload"
}

build {
  sources = ["source.virtualbox-iso.ubuntu_base"]

  provisioner "shell" {
    inline = [
      "sudo apt-get update",
      "sudo apt-get -y upgrade",
      "sudo apt-get -y autoremove",
      "sudo rm -rf /var/lib/apt/lists/*",
    ]
  }

  post-processor "vagrant" {
    output = "builds/forensicforge-ubuntu-base.box"
  }
}
