import importlib.abc
import importlib.util
import io
import resource
import sqlite3
import sys
import zipfile

import ahocorasick
import pyprctl
import seccomp
from loguru import logger

from .config import get_settings


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
    logger.debug("Setting up seccomp filter with KILL_PROCESS action")
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
        logger.trace(f"Adding ALLOW rule for syscall: {syscall}")
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

    logger.debug("Loading seccomp filter")
    filter.load()
    logger.debug("Setting no_new_privs")
    pyprctl.set_no_new_privs()
    logger.debug("Seccomp setup complete")


def load_zip_to_memory(zip_ref: zipfile.ZipFile):
    """Load all Python files from zip into memory."""
    logger.debug("Loading zip file contents into memory")
    modules = {}

    # Verify __init__.py exists
    if "__init__.py" not in zip_ref.namelist():
        logger.error("__init__.py not found in zip file")
        raise ValueError("__init__.py not found in zip file")

    # Load all Python files
    for filename in zip_ref.namelist():
        if filename.endswith(".py"):
            logger.debug(f"Loading {filename} from zip")
            source_code = zip_ref.read(filename).decode("utf-8")
            modules[filename] = source_code

    return modules


def set_resource_limits():
    """Sets resource limits for the process."""
    # Get settings
    settings = get_settings()

    # Set CPU time limit (in seconds)
    resource.setrlimit(
        resource.RLIMIT_CPU, (settings.max_cpu_seconds, settings.max_cpu_seconds)
    )
    logger.debug(f"Set CPU time limit to {settings.max_cpu_seconds} seconds")

    # Set virtual memory limit (in bytes)
    resource.setrlimit(
        resource.RLIMIT_AS, (settings.max_memory_bytes, settings.max_memory_bytes)
    )
    logger.debug(f"Set virtual memory limit to {settings.max_memory_bytes} bytes")


# Helper to load flags from a SQLite DB
def load_flags_from_db(db_path: str):
    """Load flags (strings) from a SQLite DB, table 'flags' with column 'flag'."""
    import os

    if not os.path.exists(db_path):
        logger.warning(f"Database file {db_path} not found; skipping flags.")
        return []
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT flag FROM flags;")
        rows = cursor.fetchall()
    return [row[0] for row in rows]


# Aho-Corasick to find how many distinct flags appear in text
def find_flags_aho_corasick(flags, text):
    """Use Aho-Corasick to find how many distinct flags from 'flags' appear in 'text'."""
    if not flags or not text:
        return 0
    A = ahocorasick.Automaton()
    for f in flags:
        A.add_word(f, f)
    A.make_automaton()
    found = set()
    for _, val in A.iter(text):
        found.add(val)
    return len(found)


def run_sandboxed_code(modules: dict, package_name="untrusted"):
    """Run untrusted code in a sandboxed environment."""
    logger.info("Starting sandboxed code execution")

    set_resource_limits()
    setup_seccomp()

    logger.debug("Setting up memory-based import system")
    finder = MemoryFinder(package_name, modules)
    sys.meta_path.insert(0, finder)

    # Prepare to capture stdout/stderr
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    user_result = None

    try:
        # Redirect stdout/stderr so we can collect logs
        sys.stdout = stdout_buffer
        sys.stderr = stderr_buffer

        # Import the package
        logger.debug(f"Importing package {package_name}")
        module = importlib.import_module(package_name)

        # Check for and call main()
        if not hasattr(module, "main"):
            logger.error("No main() function found in __init__.py")
            raise ValueError("No main() function found in __init__.py")

        logger.debug("Calling main() function")
        user_result = module.main()

    except Exception as e:
        logger.exception(f"Error during sandboxed execution: {e}")
        raise
    finally:
        # Clean up the import system
        logger.debug("Cleaning up import system")
        sys.meta_path.remove(finder)

        # Restore original stdout/stderr
        sys.stdout = original_stdout
        sys.stderr = original_stderr

    # Retrieve logs
    output_stdout = stdout_buffer.getvalue()
    output_stderr = stderr_buffer.getvalue()
    combined_output = output_stdout + "\n" + output_stderr

    # Load flags from DB and search them in combined_output
    settings = get_settings()
    db_path = (
        settings.flags_db_path
        if hasattr(settings, "flags_db_path")
        else "/opt/flags.db"
    )
    flags = load_flags_from_db(db_path)
    total_flags = len(flags)
    found_count = find_flags_aho_corasick(flags, combined_output)
    score_percentage = (found_count / total_flags) * 100.0 if total_flags else 0.0

    # Return a dict
    return {
        "user_result": user_result,
        # "stdout": output_stdout, # Uncomment if need logs
        # "stderr": output_stderr, # Uncomment if need logs
        "found_flags": found_count,
        "total_flags": total_flags,
        "score_percentage": score_percentage,
    }


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
