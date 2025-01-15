"""Module for handling system dependency installation."""

import os
import platform
import subprocess
import logging


def ensure_build_dependencies():
    """Ensure all required build dependencies are installed on the system."""

    print("ensure_build_dependencies()")
    def is_package_installed(package: str) -> bool:
        try:
            subprocess.run(
                ["pacman", "-Qi", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def install_from_aur(package: str):
        """Install a package from AUR using yay."""
        try:
            # First check if yay is installed
            subprocess.run(["which", "yay"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("Installing yay (AUR helper)...")
            subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "yay"], check=True)

        print(f"Installing {package} from AUR...")
        subprocess.run(["yay", "-S", "--noconfirm", package], check=True)

    if platform.system() == "Linux":
        print(f"system={platform.system}")
        if os.path.exists("/etc/arch-release"):  # Arch-based systems
            print("os.path exists")
            required_packages = [
                "base-devel",
                "openssl",
                "openssl-1.1",
                "zlib",
                "xz",
                "tk",
                "libffi",
                "bzip2",
                "sqlite",
                "ncurses",
                "readline",
                "gdbm",
                "db",
                "expat",
                "mpdecimal",
                "libxcrypt",
                "libxcrypt-compat",
            ]

            missing_packages = [
                pkg for pkg in required_packages if not is_package_installed(pkg)
            ]

            if missing_packages:
                print(
                    f"Installing missing build dependencies: {', '.join(missing_packages)}"
                )
                try:
                    subprocess.run(
                        ["sudo", "pacman", "-Sy", "--noconfirm"] + missing_packages,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to install build dependencies: {e}")

            # Install gcc10 from AUR if not already installed
            if not is_package_installed("gcc10"):
                print('gcc10 not installed')
                try:
                    install_from_aur("gcc10")
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(f"Failed to install gcc10 from AUR: {e}")


    def ensure_python_version(version: str) -> str:
        """
        Ensure specific Python version is installed using pyenv.
        Returns the python command to use.
        """
        try:
            subprocess.run(
                [f"python{version}", "--version"], check=True, capture_output=True
            )
            return f"python{version}"
        except (subprocess.SubprocessError, FileNotFoundError):
            print(f"Python {version} not found, attempting to install via pyenv...")
            try:
                # ensure_build_dependencies()

                pyenv_root = subprocess.run(
                    ["pyenv", "root"], check=True, capture_output=True, text=True
                ).stdout.strip()

                list_output = subprocess.run(
                    ["pyenv", "install", "--list"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout

                # Find latest compatible version (e.g. 3.6.15 for version 3.6)
                available_versions = [
                    v.strip()
                    for v in list_output.split("\n")
                    if v.strip().startswith(f"{version}.")
                ]
                if not available_versions:
                    raise RuntimeError(f"No available Python {version}.x versions found")

                full_version = sorted(available_versions)[-1]  # Get latest patch version

                logging.info(f"Installing Python {full_version} using pyenv...")

                # Install Python version using pyenv with verbose output
                install_result = subprocess.run(
                    ["pyenv", "install", "--skip-existing", "-v", full_version],
                    capture_output=True,
                    text=True,
                )

                if install_result.returncode != 0:
                    logging.error(f"Python installation failed:\n{install_result.stderr}")
                    raise RuntimeError(f"Failed to install Python {full_version}")

                subprocess.run(["pyenv", "rehash"], check=True)
                python_path = f"{pyenv_root}/versions/{full_version}/bin/python"
                subprocess.run([python_path, "--version"], check=True)

                return python_path

            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Failed to install Python {version} using pyenv: {e}")
