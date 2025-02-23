import importlib.abc
import importlib.util
import io
import sys
import zipfile

import pyprctl
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
    syscalls_allow = [
        "access",
        "arch_prctl",
        "brk",
        "clone3",
        "close",
        "epoll_create1",
        "epoll_ctl",
        "epoll_wait",
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
        "sendto",
        "recvfrom",
        "socket",
        "connect",
        "setsockopt",
        "getsockopt",
        "getpeername",
        "sendmmsg",
        "madvise",
        "close_range",
        "poll",
        "bind",
        "recvmsg",
    ]
    for syscall in syscalls_allow:
        filter.add_rule(seccomp.ALLOW, syscall)

    syscalls_errno = [
        "clone",
        "clone3",
        "execve",
        "vfork",
        "wait4",
    ]
    for syscall in syscalls_errno:
        filter.add_rule(seccomp.ERRNO(1), syscall)

    filter.load()
    pyprctl.set_no_new_privs()


def load_zip_to_memory(zip_ref: zipfile.ZipFile):
    """Load all Python files from zip into memory."""
    modules = {}

    # Verify __init__.py exists
    if "__init__.py" not in zip_ref.namelist():
        raise ValueError("__init__.py not found in zip file")

    # Load all Python files
    for filename in zip_ref.namelist():
        if filename.endswith(".py"):
            source_code = zip_ref.read(filename).decode("utf-8")
            modules[filename] = source_code

    return modules


def run_sandboxed_code(modules: dict, package_name="untrusted"):
    """Run untrusted code in a sandboxed environment."""
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

    with open(sys.argv[1], "rb") as f:
        zip_data = io.BytesIO(f.read())

    with zipfile.ZipFile(zip_data) as zip_ref:
        modules = load_zip_to_memory(zip_ref)

    result = run_sandboxed_code(modules)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
