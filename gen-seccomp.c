#include <seccomp.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/socket.h>

#define ALLOW_RULE(call) { if (seccomp_rule_add (ctx, SCMP_ACT_ALLOW, SCMP_SYS(call), 0) < 0) goto out; }

int main(int argc, char *argv[])
{
    int rc = -1;
    scmp_filter_ctx ctx;
    int filter_fd;

    /* Initialize whitelist (default deny) */
    ctx = seccomp_init(SCMP_ACT_KILL);
    if (ctx == NULL)
        goto out;

    /* Essential syscalls for program execution */
    ALLOW_RULE(read);
    ALLOW_RULE(write);
    ALLOW_RULE(close);
    ALLOW_RULE(fstat);
    ALLOW_RULE(lstat);
    ALLOW_RULE(stat);
    ALLOW_RULE(openat);
    ALLOW_RULE(newfstatat);
    ALLOW_RULE(fcntl);
    ALLOW_RULE(ioctl);
    ALLOW_RULE(mmap);
    ALLOW_RULE(mprotect);
    ALLOW_RULE(munmap);
    ALLOW_RULE(brk);
    ALLOW_RULE(rt_sigaction);
    ALLOW_RULE(rt_sigreturn);
    ALLOW_RULE(rt_sigprocmask);
    ALLOW_RULE(pread64);
    ALLOW_RULE(pwrite64);
    ALLOW_RULE(readv);
    ALLOW_RULE(writev);
    ALLOW_RULE(access);
    ALLOW_RULE(sched_yield);
    ALLOW_RULE(clock_gettime);
    ALLOW_RULE(gettimeofday);
    ALLOW_RULE(getpid);
    ALLOW_RULE(exit_group);
    ALLOW_RULE(exit);
    ALLOW_RULE(arch_prctl);
    ALLOW_RULE(futex);
    ALLOW_RULE(getuid);
    ALLOW_RULE(getgid);
    ALLOW_RULE(geteuid);
    ALLOW_RULE(getegid);
    ALLOW_RULE(set_tid_address);
    ALLOW_RULE(set_robust_list);
    ALLOW_RULE(rseq);
    ALLOW_RULE(wait4);
    ALLOW_RULE(execve);
    ALLOW_RULE(prlimit64);
    ALLOW_RULE(getrandom);
    ALLOW_RULE(gettid);
    ALLOW_RULE(readlink);
    ALLOW_RULE(getdents64);
    ALLOW_RULE(lseek);
    
    /* Export the filter */
    filter_fd = open("build/seccomp.bpf", O_CREAT | O_WRONLY, 0644);
    if (filter_fd == -1) {
        rc = -errno;
        goto out;
    }

    rc = seccomp_export_bpf(ctx, filter_fd);
    if (rc < 0) {
        close(filter_fd);
        goto out;
    }
    close(filter_fd);

out:
    seccomp_release(ctx);
    return -rc;
}