/* Prepared bootstrap, not a setuid program, installer or admission authority.
 * A trusted host owns the original cgroup, immutable runtime, clean exec
 * environment, exclusive lease, external deadline and cleanup before exec.
 * No Python/runtime callback executes between clone3 and the fixed execve.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/magic.h>
#include <linux/sched.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#define PYTHON "/opt/cashlessiq-agent/venv/bin/python"
static const char error[] = "single_call_launch_unavailable\n";

_Noreturn static void deny(void) {
    ssize_t ignored = write(STDERR_FILENO, error, sizeof(error) - 1);
    (void)ignored;
    _exit(125);
}

static int protected_group(int fd) {
    struct stat info;
    struct statfs filesystem;
    return fstat(fd, &info) == 0 && S_ISDIR(info.st_mode) && info.st_uid == 0
        && !(info.st_mode & 0022) && fstatfs(fd, &filesystem) == 0
        && filesystem.f_type == CGROUP2_SUPER_MAGIC;
}

static int kernel_text(int group, const char *name, const char *expected) {
    char buffer[128];
    struct stat info;
    struct statfs filesystem;
    int fd = openat(group, name, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0) return 0;
    int valid = fstat(fd, &info) == 0 && S_ISREG(info.st_mode) && info.st_uid == 0
        && !(info.st_mode & 0022) && fstatfs(fd, &filesystem) == 0
        && filesystem.f_type == CGROUP2_SUPER_MAGIC;
    ssize_t length = valid ? read(fd, buffer, sizeof(buffer)) : -1;
    (void)close(fd);
    return length == (ssize_t)strlen(expected)
        && memcmp(buffer, expected, (size_t)length) == 0;
}

static int resource_policy(int group, const char *role) {
    /* Independent readback of the fixed Python reservation policy. Never
     * repair/adopt a mismatched group, enable controllers or accept selectors.
     */
    const char *memory = strcmp(role, "receipt") == 0 ? "134217728\n" : "268435456\n";
    return kernel_text(group, "memory.max", memory)
        && kernel_text(group, "memory.swap.max", "0\n")
        && kernel_text(group, "memory.oom.group", "1\n")
        && kernel_text(group, "pids.max", "32\n")
        && kernel_text(group, "cpu.max", "50000 100000\n");
}

int main(int argc, char **argv, char **envp) {
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    struct stat input, null, output, diagnostic;
    struct rlimit core = {0, 0};
    struct sched_param normal = {.sched_priority = 0};
    if (argc != 3 || (strcmp(argv[1], "receipt") && strcmp(argv[1], "provider")
                     && strcmp(argv[1], "custody"))) deny();
    /* Only a descriptor already owned by the host, never a path or PID. */
    if (!argv[2][0] || strlen(argv[2]) > 4) deny();
    for (const char *p = argv[2]; *p; ++p) if (*p < '0' || *p > '9') deny();
    long selected = strtol(argv[2], NULL, 10);
    if (selected < 3 || selected > 1023) deny();
    int group = (int)selected;
    for (char **p = envp; *p; ++p) {
        if (strcmp(*p, "LANG=C.UTF-8") && strcmp(*p, "LC_CTYPE=C.UTF-8")) deny();
    }
    if (getresuid(&real_uid, &effective_uid, &saved_uid)
        || getresgid(&real_gid, &effective_gid, &saved_gid)
        || real_uid || effective_uid || saved_uid || real_gid || effective_gid || saved_gid
        || fstat(0, &input) || stat("/dev/null", &null) || !S_ISCHR(input.st_mode)
        || input.st_rdev != null.st_rdev || fstat(1, &output) || !S_ISFIFO(output.st_mode)
        || fstat(2, &diagnostic) || !S_ISFIFO(diagnostic.st_mode)
        || (output.st_dev == diagnostic.st_dev && output.st_ino == diagnostic.st_ino)
        || !protected_group(group) || !kernel_text(group, "cgroup.type", "domain\n")
        || !kernel_text(group, "cgroup.events", "populated 0\nfrozen 0\n")
        || !resource_policy(group, argv[1])
        || setrlimit(RLIMIT_CORE, &core) || setrlimit(RLIMIT_RTPRIO, &core)
        || setrlimit(RLIMIT_MEMLOCK, &core)
        || sched_setscheduler(0, SCHED_OTHER, &normal) || chdir("/")) deny();
    umask(0077);
    /* Normalize only the retained kernel handle, then close every other extra
     * descriptor. close_range/clone3 failure is terminal: no fork/move fallback.
     */
    if ((group != 3 && dup3(group, 3, O_CLOEXEC) < 0)
        || fcntl(3, F_SETFD, FD_CLOEXEC) < 0
        || syscall(SYS_close_range, 4U, UINT_MAX, 0U) != 0) deny();
    for (int fd = 0; fd < 3; ++fd) if (fcntl(fd, F_SETFD, 0) < 0) deny();
    /* Reset inherited signal dispositions/mask before allocating a child. */
    struct sigaction action = {.sa_handler = SIG_DFL};
    if (sigemptyset(&action.sa_mask)) deny();
    for (int sig = 1; sig < NSIG; ++sig) {
        if (sig != SIGKILL && sig != SIGSTOP && sigaction(sig, &action, NULL)
            && errno != EINVAL) deny();
    }
    if (sigprocmask(SIG_SETMASK, &action.sa_mask, NULL)) deny();
    int pidfd = -1;
    pid_t parent = getpid();
    struct clone_args args = {
        .flags = CLONE_INTO_CGROUP | CLONE_PIDFD,
        .pidfd = (uint64_t)(uintptr_t)&pidfd,
        .exit_signal = SIGCHLD,
        .cgroup = 3,
    };
    long child = syscall(SYS_clone3, &args, sizeof(args));
    if (child < 0) deny(); /* In particular ENOSYS, EPERM, EBUSY: never downgrade. */
    if (child == 0) {
        /* Parent-death protection covers this privileged bootstrap interval.
         * Linux clears it at identity loss; whole-group cleanup remains required.
         */
        if (prctl(PR_SET_PDEATHSIG, SIGKILL, 0, 0, 0) || getppid() != parent
            || setsid() < 0 || close(3)) deny();
        char *const command[] = {PYTHON, "-I", "-B", "-m",
                                "ciq_api.agent_single_call_identity", argv[1], NULL};
        char *const environment[] = {"LANG=C.UTF-8", NULL};
        execve(PYTHON, command, environment);
        deny();
    }
    /* This fixed root waiter runs outside the application cgroup. The trusted
     * host must retain/reap it separately, including after uncertain start ACK.
     * No PID is exported or accepted for signaling; waitid uses the original fd.
     */
    if (pidfd < 0) deny();
    siginfo_t result = {0};
    int waited;
    do { waited = waitid(P_PIDFD, (id_t)pidfd, &result, WEXITED); }
    while (waited < 0 && errno == EINTR);
    (void)close(pidfd);
    (void)close(3);
    if (waited || result.si_pid != child) deny();
    if (result.si_code == CLD_EXITED) return result.si_status;
    if (result.si_code == CLD_KILLED || result.si_code == CLD_DUMPED)
        return 128 + result.si_status;
    deny();
}
