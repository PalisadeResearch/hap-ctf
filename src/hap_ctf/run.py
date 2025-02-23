import importlib.abc
import importlib.util
import io
import os
import sys
import zipfile

import seccomp


class MemoryLoader(importlib.abc.Loader):
    """Custom loader that loads modules from in-memory source code."""

    def __init__(self, source_code):
        self.source_code = source_code

    def exec_module(self, module):
        exec(self.source_code, module.__dict__)


class MemoryFinder(importlib.abc.MetaPathFinder):
    """Custom finder that handles in-memory modules."""

    def __init__(self, package_name, modules):
        self.package_name = package_name
        self.modules = modules  # Dict of relative_path -> source_code

    def find_spec(self, fullname, path, target=None):
        # Only handle modules under our package
        if not fullname.startswith(self.package_name):
            return None

        # Get the relative path within the package
        relative_name = (
            fullname[len(self.package_name) + 1 :]
            if len(fullname) > len(self.package_name)
            else ""
        )
        relative_path = (
            relative_name.replace(".", "/") + ".py" if relative_name else "__init__.py"
        )

        if relative_path in self.modules:
            source_code = self.modules[relative_path]
            loader = MemoryLoader(source_code)
            return importlib.util.spec_from_loader(
                fullname, loader, is_package=relative_path == "__init__.py"
            )
        return None


def setup_seccomp():
    """Set up a restrictive seccomp filter that only allows necessary syscalls."""
    filter = seccomp.SyscallFilter(seccomp.KILL_PROCESS)
    syscalls = [
        "access",
        "arch_prctl",
        "brk",
        "clone3",
        "close",
        "epoll_create1",
        "epoll_ctl",
        "epoll_wait",
        "execve",
        "exit_group",
        "fcntl",
        "fstat",
        "futex",
        "getcwd",
        "getdents64",
        "getpid",
        "getrandom",
        "getsockname",
        "gettid",
        "ioctl",
        "lseek",
        "mmap",
        "mprotect",
        "munmap",
        "newfstatat",
        "open",
        "openat",
        "prctl",
        "pread64",
        "prlimit64",
        "read",
        "readlink",
        "rseq",
        "rt_sigaction",
        "rt_sigprocmask",
        "sched_getaffinity",
        "seccomp",
        "set_robust_list",
        "set_tid_address",
        "socketpair",
        "write",
        "uname",
        "pipe2",
        "dup2",
        "exit",
        "wait4",
        "sendto",
        "recvfrom",
        "socket",
        "connect",
        "setsockopt",
        "getsockopt",
        "getpeername",
        "sendmmsg",
        "madvise",
        "vfork",
        "close_range",
        "poll",
        "bind",
        "recvmsg",
    ]
    for syscall in syscalls:
        filter.add_rule(seccomp.ALLOW, syscall)
    filter.load()


def drop_privileges():
    """Drop privileges by setting uid/gid to nobody."""
    nobody_uid = 65534
    nobody_gid = 65534

    os.setgroups([])
    os.setgid(nobody_gid)
    os.setuid(nobody_uid)

    if os.getuid() != nobody_uid or os.getgid() != nobody_gid:
        raise RuntimeError("Failed to drop privileges")


def load_zip_to_memory(zip_path):
    """Load all Python files from zip into memory."""
    modules = {}

    with open(zip_path, "rb") as f:
        zip_data = io.BytesIO(f.read())

    with zipfile.ZipFile(zip_data) as zip_ref:
        # Verify __init__.py exists
        if "__init__.py" not in zip_ref.namelist():
            raise ValueError("__init__.py not found in zip file")

        # Load all Python files
        for filename in zip_ref.namelist():
            if filename.endswith(".py"):
                source_code = zip_ref.read(filename).decode("utf-8")
                modules[filename] = source_code

    return modules


def run_sandboxed_code(zip_path, package_name="untrusted"):
    """Run untrusted code in a sandboxed environment."""
    # Load zip contents into memory first
    modules = load_zip_to_memory(zip_path)

    # Drop privileges
    # drop_privileges()

    # Set up seccomp filter
    setup_seccomp()

    # Set up the memory-based import system
    finder = MemoryFinder(package_name, modules)
    sys.meta_path.insert(0, finder)

    try:
        # Import the package
        module = importlib.import_module(package_name)

        # Check for and call main()
        if not hasattr(module, "main"):
            raise ValueError("No main() function found in __init__.py")
        return module.main()
    except Exception as e:
        return f"Error running sandboxed code: {str(e)}"
    finally:
        # Clean up the import system
        sys.meta_path.remove(finder)


def main():
    if len(sys.argv) != 2:
        print("Usage: python sandbox.py <path_to_zip>")
        sys.exit(1)

    result = run_sandboxed_code(sys.argv[1])
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
