import time
import re
from pathlib import Path
import shutil
from plumbum import local
from plumbum.commands.processes import ProcessExecutionError
import paramiko
import stat


# Helper function to execute vmrun commands
def vmrun(cmd):
    """Execute a vmrun command and return the output."""
    return local["vmrun"](*cmd)


# Helper function to check if the path to the VM exists
def check_vmx_exists(vmx_path):
    """Check if the VMX path exists."""
    return vmx_path.exists()


# SSH Connection to VM
def ssh_to_vm_cmd(ip, command):
    """SSH into the VM and run a command."""
    username = "ubuntu"
    password = "ubuntu"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password)

    # Run the command and fetch output
    stdin, stdout, stderr = client.exec_command(command)
    result = stdout.read().decode("utf-8")
    if stderr:
        err = stderr.read().decode("utf-8")
        if err != "":
            result += f"### STDERR data: ###\n{err}"
    client.close()

    return result


def ssh_to_vm(ip, local_script_path, remote_script_path="/tmp/script.sh"):
    """SSH into the VM, transfer a local script to the VM, and run the command."""
    username = "ubuntu"
    password = "ubuntu"

    # Create SSH client and connect
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password)

    # Step 1: Transfer the script file to the VM
    sftp = client.open_sftp()
    sftp.put(local_script_path, remote_script_path)  # Copy file from local to remote
    sftp.close()

    # Step 2: Make the script executable
    chmod_command = f"chmod +x {remote_script_path}"
    client.exec_command(chmod_command)

    # Step 3: Run the command on the remote VM
    stdin, stdout, stderr = client.exec_command(f"bash {remote_script_path}")
    result = stdout.read().decode("utf-8")

    # Optional: check for errors in stderr
    error = stderr.read().decode("utf-8")
    if error:
        print(f"Error: {error}")

    client.close()

    return result


# Helper function to SCP files from the VM to the local system
def scp_from_vm(ip, remote_path, local_path):
    """Copy files from the VM to the local system using SCP."""
    username = "ubuntu"
    password = "ubuntu"

    # Create SSH client and connect
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password)

    # Use SFTP to transfer files
    sftp = client.open_sftp()
    sftp.get(remote_path, local_path)  # Copy file from remote to local
    sftp.close()
    client.close()


# Helper function to recursively copy files from a directory on the VM to the local system
def scp_from_vm_dir(ip, remote_dir, local_dir):
    """Copy an entire directory from the VM to the local system using SCP/SFTP."""
    username = "ubuntu"
    password = "ubuntu"

    # Create SSH client and connect
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip, username=username, password=password)

    # Use SFTP to transfer files recursively
    sftp = client.open_sftp()
    _recursive_scp(sftp, remote_dir, local_dir)
    sftp.close()
    client.close()


# Helper function to recursively copy a folder via SFTP
def _recursive_scp(sftp, remote_dir, local_dir):
    """Helper function to walk through a remote directory and copy all files and subdirectories."""
    if not Path(local_dir).exists():
        Path(local_dir).mkdir(parents=True, exist_ok=True)

    for entry in sftp.listdir_attr(remote_dir):
        remote_path = f"{remote_dir}/{entry.filename}"
        local_path = f"{local_dir}/{entry.filename}"

        if stat.S_ISDIR(entry.st_mode):
            _recursive_scp(
                sftp, remote_path, local_path
            )  # Recursively copy subdirectories
        else:
            sftp.get(remote_path, local_path)  # Copy files


# Get the IP address of the VM using vmrun's getGuestIPAddress
def get_vm_ip(clone_vmx, timeout=900, poll_interval=5):
    """
    Poll vmrun to get the IP address of the cloned VM.
    Stops when the IP is retrieved or timeout is reached.
    
    Args:
        clone_vmx (str): Path to the VMX file.
        timeout (int): Maximum time in seconds to wait for an IP.
        poll_interval (int): How often to check for the IP (seconds).
    
    Returns:
        str: The IP address if retrieved.
    
    Raises:
        TimeoutError: If the IP address is not retrieved in time.
    """
    print(f"Fetching IP address for VM {clone_vmx}...")

    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            output = vmrun(["getGuestIPAddress", str(clone_vmx)])
            ip_address = output.strip()

            if ip_address and ip_address.lower() != "unknown":
                return ip_address
        except Exception as e:
            # You can log or ignore this depending on how vmrun behaves
            pass

        time.sleep(poll_interval)

    raise TimeoutError(f"Timed out after {timeout} seconds waiting for VM IP.")


# Main script to create, manage and delete VM clone
def manage_vm_clone(original_vmx, clone_name, script_path_input="./scripts/signal.sh"):
    # Check if the original VMX file exists
    if not check_vmx_exists(original_vmx):
        print(f"Error: Original VM {original_vmx} does not exist.")
        return

    # Step 1: Create the linked clone and put it in the ./clones folder
    clone_folder = original_vmx.parent / "clones"
    clone_folder.mkdir(parents=True, exist_ok=True)
    clone_vmx = clone_folder / f"{clone_name}.vmx"

    # Create the linked clone
    print(f"Creating linked clone at {clone_vmx}...")
    vmrun(["-T", "ws", "clone", str(original_vmx), str(clone_vmx), "linked"])

    # After clone creation, edit the displayname in the clone_vmx file
    print(f"Updating displayname for {clone_name} in the VMX file...")
    clone_vmx.write_text(
        re.sub(
            r"^displayname = .+",
            f'displayname = "{clone_name}"',
            clone_vmx.read_text(),
            flags=re.M,
        )
    )

    # Step 2: Start the VM
    print("Starting the cloned VM...")
    vmrun(["-T", "ws", "start", str(clone_vmx)])

    # Step 3: Wait for SSH access (assuming SSH is enabled and running on the cloned VM)
    print(f"Waiting for SSH access to {clone_name}...")

    # Give the VM some time to boot up (adjust time as needed)
    print("Waiting a bit...")

    ip_address = get_vm_ip(clone_vmx)
    print(f"Cloned VM's IP address: {ip_address}")

    # Attempt SSH connection and run a sample command
    try:
        result = ssh_to_vm_cmd(ip_address, "uptime")
        print(f"SSH Connection successful. Output:\n{result}")
    except Exception as e:
        print(f"Error during SSH connection: {e}")
        return

    # Step 4: Run some scripts (adjust the script name and path)
    result = ssh_to_vm_cmd(ip_address, "uptime")

    result = ssh_to_vm_cmd(ip_address, "sudo mkdir -p /signal")
    result = ssh_to_vm_cmd(ip_address, "sudo chown $USER:$USER /signal")

    # script_path_input = "./scripts/signal.sh"
    if not script_path_input:
        script_path_input = input(
            "Enter the path to the script you want to run on the VM: "
        )
    script_path = Path(script_path_input).resolve()  # Resolve the path

    if not script_path.is_file():
        print(
            f"Error: The file at {script_path} does not exist or is not a valid file."
        )
        return

    # # print(f"[DEBUG:] Contents of the script {script_path}:\n")
    # with script_path.open("r") as file:
    #     print(file.read())  # Print the content of the script

    print(f"Started script {script_path} on ubuntu@{ip_address}")
    result = ssh_to_vm(ip_address, str(script_path))
    print(f"Script output:\n{result}")

    # Step 5: Copy files from VM to local results folder
    remote_dir = "/signal/reproducible-tests/results/"
    local_results_dir = Path(f"results/{clone_name}")
    local_results_dir.mkdir(parents=True, exist_ok=True)

    # Assuming the VM has generated files in the above directory
    print(f"Copying results from the VM to {local_results_dir}...")
    # scp_from_vm(ip_address, remote_dir, str(local_results_dir / "results.tar.gz"))
    scp_from_vm_dir(ip_address, remote_dir, str(local_results_dir))

    print("Files copied successfully.")

    time.sleep(10)
    # Step 6: User confirmation for shutdown and cleanup
    # confirm = input(f"Do you want to shut down and delete {clone_name}? (y/n): ").strip().lower()
    confirm = "y"
    if confirm == "y":
        # Step 6a: List and delete snapshots
        for target_name, target_vmx in [
            (clone_name, clone_vmx),
            ("original_vm", original_vmx),
        ]:
            print(f"Listing snapshots for {target_name}...")
            snapshots = vmrun(["-T", "ws", "listSnapshots", str(target_vmx)])
            if snapshots:
                print(snapshots.split("\n")[0])
                for snapshot in snapshots.splitlines()[1:]:
                    print(f"Deleting snapshot {snapshot}...")
                    try:
                        vmrun(["-T", "ws", "deleteSnapshot", str(target_vmx), snapshot])
                    except ProcessExecutionError as e:
                        print("Failed to delete snapshot: {e}")
            # print(f"Listing snapshots for {clone_name}...")
            # snapshots = vmrun(["-T", "ws","listSnapshots", str(clone_vmx)])
            # if snapshots:
            #     print(snapshots.split("\n")[0])
            #     for snapshot in snapshots.splitlines()[1:]:
            #         print(f"Deleting snapshot {snapshot}...")
            #         vmrun(["-T", "ws","deleteSnapshot", str(clone_vmx), snapshot])

        # Step 6b: Shut down the clone VM
        print(f"Shutting down {clone_name}...")
        vmrun(["-T", "ws", "stop", str(clone_vmx)])

        # Step 7: Delete the clone folder
        print(f"Removing clone folder {clone_folder}...")
        clone_vmx.unlink()  # Remove the VMX file
        try:
            shutil.rmtree(
                clone_folder
            )  # Recursively remove the folder and all its contents
        except Exception as e:
            print(e)
        print("Clone VM and associated files have been removed.")
    else:
        print(f"{clone_name} was not removed.")


# Hardcoded path to the original VMX
original_vmx = Path("./output-vmware-ubuntu/ubuntu-24.04-vm.vmx")  # Adjust this path

# Example usage of the script
from tqdm import tqdm

if __name__ == "__main__":
    # clone_names = [f"signal_7_41_3__dfs-sort__run_{i}" for i in range(8,10)]
    clone_names = [f"signal_7_36_0__dfs-ctime_sort__run_{i}" for i in range(1, 3)]

    for clone_name in tqdm(clone_names):
        manage_vm_clone(original_vmx, clone_name)
        time.sleep(3)

    # clone_name = input("Enter the name for the clone: ").strip()
    # manage_vm_clone(original_vmx, clone_name)
