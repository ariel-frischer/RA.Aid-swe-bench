"""Module for handling system dependency installation."""

import os
import platform
import subprocess


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
