import re
import sys


def parse_strace_log(log_file):
    """
    Parses an strace log file and extracts the set of unique syscalls.

    Args:
        log_file (str): Path to the strace log file.

    Returns:
        set: A set containing the unique syscalls found in the log.
    """

    syscalls = set()
    try:
        with open(log_file) as f:
            for line in f:
                # Use regex to find syscalls at the beginning of the line
                match = re.match(r"([a-zA-Z0-9_]+)\(", line)
                if match:
                    syscall = match.group(1)
                    syscalls.add(syscall)
    except FileNotFoundError:
        print(f"Error: File not found: {log_file}")
        return None
    except Exception as e:
        print(f"Error processing the log file: {e}")
        return None

    return syscalls


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <strace_log_file>")
        sys.exit(1)

    log_file = sys.argv[1]
    syscalls = parse_strace_log(log_file)

    if syscalls:
        print("Unique syscalls used:")
        for syscall in sorted(syscalls):
            print(syscall)


if __name__ == "__main__":
    main()
