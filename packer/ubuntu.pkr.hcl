packer {
  required_plugins {
    vmware = {
      source  = "github.com/hashicorp/vmware"
      version = "~> 1" # Ensure the plugin version is compatible
    }
  }
}

# Define the Packer source (Ubuntu image)
source "vmware-iso" "ubuntu-24_04" {
  iso_url          = "https://releases.ubuntu.com/24.04/ubuntu-24.04.2-live-server-amd64.iso"
  iso_checksum     = "sha256:d6dab0c3a657988501b4bd76f1297c053df710e06e0c3aece60dead24f270b4d"
  vm_name          = "ubuntu-24.04-vm"
  disk_size        = 40960 # 30GB disk size
  memory           = 14336  # Set RAM to 14GB (14336MB)
  cpus             = 4     # Set the number of CPUs (adjust as needed)
  guest_os_type    = "ubuntu-64"
  ssh_username     = "ubuntu"
  ssh_password     = "ubuntu"
  ssh_handshake_attempts = 100
  ssh_wait_timeout = "90m"
  shutdown_command = "shutdown now"
  # tools_upload_flavor = "linux"
  output_directory = "output-vmware-ubuntu"
  format           = "ova"
  # Use vmx_data for VMware-specific options
  vmx_data = {
    floppy            = "FALSE"   # Disable floppy drive
    "svga.autodetect" = "TRUE"    # Enable SVGA (for VM graphics)
    "vnc.enable"      = "TRUE"    # Enable VNC
    "vnc.password"    = "vncpass" # Set VNC password
    "vnc.address"     = "0.0.0.0" # Bind to all IP addresses
  }

  http_directory = "http"
  boot_wait      = "12s"
  boot_command = [
    "<esc><wait5>", # Interrupt default boot (stops countdown)

    "c", "<wait3s>",
    "linux /casper/vmlinuz --- autoinstall ds=\"nocloud-net;seedfrom=http://{{ .HTTPIP }}:{{ .HTTPPort }}/\"<enter><wait>",
    "initrd /casper/initrd<enter><wait>", "boot<enter>", "<enter><f10><wait>"
  ]
}

# Define a provisioner to configure the VM
build {
  sources = ["source.vmware-iso.ubuntu-24_04"]

  provisioner "shell" {
    script = "scripts/setup.sh"
  }

  # provisioner "shell" {
  #   inline = [
  #     "echo 'Disabling cloud-init for reproducibility...'",
  #     "sudo touch /etc/cloud/cloud-init.disabled",
  #     "echo 'Disabling SSH key generation on first boot...'",
  #     "sudo rm -rf /etc/ssh/ssh_host_*", # Prevent new SSH keys from being generated
  #     "echo 'Disabling timestamps in logs...'",
  #     "sudo sed -i 's/^#\\?LogLevel.*/LogLevel QUIET/' /etc/ssh/sshd_config",
  #     "sudo sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config"
  #   ]
  # }
}
