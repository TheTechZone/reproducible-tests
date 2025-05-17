#!/bin/bash

# Update and upgrade the system (ensure the system is up-to-date but deterministic)
sudo apt-get update
# sudo apt-get -y upgrade

# Install fixed versions of any required packages (pin versions)
# sudo apt-get -y install nginx=1.24.0-1ubuntu1  # Replace with actual package and version you need
# sudo apt-get -y install curl=7.81.0-1ubuntu1   # Another example package pinning
sudo apt-get -yyq install git=1:2.43.0-1ubuntu7.2 git-lfs=3.4.1-1ubuntu0.2
sudo apt-get -yyq install curl=8.5.0-2ubuntu10.6
sudo apt-get -yyq install build-essential=12.10ubuntu1
sudo apt-get -yyq install open-vm-tools=2:12.4.5-1~ubuntu0.24.04.2

# Add Docker's official GPG key:
sudo apt-get install -yyq ca-certificates=20240203
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

VERSION_STRING="5:28.1.1-1~ubuntu.24.04~noble"
sudo apt-get install -yyq docker-ce=$VERSION_STRING docker-ce-cli=$VERSION_STRING containerd.io docker-buildx-plugin docker-compose-plugin

sudo groupadd docker
sudo usermod -aG docker $USER


# Example of pinning package versions to prevent upgrades on future builds
sudo cat <<EOF > /etc/apt/preferences.d/pin-versions
Package: git
Pin: version 1:2.43.0-1ubuntu7.2
Pin-Priority: 1001

Package: curl
Pin: version 8.5.0-2ubuntu10.6
Pin-Priority: 1001

Package: docker-ce
Pin: version $VERSION_STRING
Pin-Priority: 1001
EOF

# Disable any dynamic elements
echo "Disabling dynamic hostname generation..."
sudo echo "127.0.0.1 localhost" > /etc/hosts

# Remove temporary files
echo "Cleaning up temporary files..."
sudo rm -rf /tmp/* /var/tmp/*

# Ensure fixed SSH keys are used (or reuse keys from another source if necessary)
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
    sudo ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N ''
fi

# Final cleanup (remove history, logs, etc.)
echo "Final cleanup..."
history -c
sudo rm -rf /var/log/*

# Optionally disable cloud-init if not already disabled
if [ ! -f /etc/cloud/cloud-init.disabled ]; then
    sudo touch /etc/cloud/cloud-init.disabled
fi

echo 'Disabling cloud-init for reproducibility...'
sudo touch /etc/cloud/cloud-init.disabled
# echo 'Disabling SSH key generation on first boot...'
# sudo rm -rf /etc/ssh/ssh_host_* # Prevent new SSH keys from being generated
echo 'Disabling timestamps in logs...'
sudo sed -i 's/^#\\?LogLevel.*/LogLevel QUIET/' /etc/ssh/sshd_config
sudo sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config

echo 'Creating SWAP'
sudo fallocate -l 10G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
sudo swapon --show

# Make the system shutdown gracefully at the end of the build
sudo shutdown now
