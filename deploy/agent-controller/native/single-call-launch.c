/* Prepared bootstrap, not a setuid program, installer or admission authority.
 * A trusted host owns the original cgroup, immutable runtime, clean exec
 * environment, exclusive lease, external deadline and cleanup before exec.
 * No Python/runtime callback executes between clone3 and the fixed execve.
 */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/bpf.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <linux/magic.h>
#include <linux/mount.h>
#include <linux/sched.h>
#include <poll.h>
#include <sched.h>
#include <signal.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/mount.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/socket.h>
#include <sys/timerfd.h>
#include <time.h>
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


/* Fixed writable leaves only. The host must stage and pin their private layout
 * under its exclusive lease. No directory, path or mount option comes from IPC.
 */
static int private_directory(const char *path, uid_t owner, mode_t mode) {
    char copy[PATH_MAX];
    if (strlen(path) >= sizeof(copy)) deny();
    memcpy(copy, path, strlen(path) + 1);
    int fd = open("/", O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) deny();
    char *state = NULL;
    struct stat info;
    for (char *part = strtok_r(copy, "/", &state); part; part = strtok_r(NULL, "/", &state)) {
        int next = openat(fd, part, O_PATH | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        (void)close(fd);
        if (next < 0) deny();
        fd = next;
        if (fstat(fd, &info) || !S_ISDIR(info.st_mode)
            || (info.st_uid != 0 && info.st_uid != owner) || (info.st_mode & 0022)) deny();
    }
    if (fstat(fd, &info) || info.st_uid != owner || (info.st_mode & 07777) != mode) deny();
    return fd;
}

static void filesystem_policy(const char *role) {
    /* clone3 already made a distinct mount namespace. First disconnect every
     * propagation relationship, so these mounts never change the host view.
     */
    if (mount(NULL, "/", NULL, MS_REC | MS_PRIVATE, NULL)) deny();
    const char *paths[2] = {NULL, NULL};
    mode_t modes[2] = {0755, 0700};
    uid_t owner = 0;
    int count = 0;
    if (strcmp(role, "receipt") == 0) {
        paths[0] = "/run/ciq-agent-single-call/ipc";
        paths[1] = "/var/lib/cashlessiq-agent/single-call/retained";
        owner = 53003;
        count = 2;
    } else if (strcmp(role, "provider") == 0) {
        paths[0] = "/run/ciq-agent-provider/ipc";
        owner = 53004;
        count = 1;
    }
    int writable[2] = {-1, -1};
    for (int i = 0; i < count; ++i) {
        int original = private_directory(paths[i], owner, modes[i]);
        struct stat before, after;
        if (fstat(original, &before) || mount(paths[i], paths[i], NULL, MS_BIND, NULL)) deny();
        writable[i] = private_directory(paths[i], owner, modes[i]);
        if (fstat(writable[i], &after) || before.st_dev != after.st_dev
            || before.st_ino != after.st_ino || close(original)) deny();
    }
    struct mount_attr readonly = {.attr_set = MOUNT_ATTR_RDONLY | MOUNT_ATTR_NOSUID};
    if (syscall(SYS_mount_setattr, AT_FDCWD, "/", AT_RECURSIVE, &readonly, sizeof(readonly)))
        deny();
    struct mount_attr leaf = {.attr_set = MOUNT_ATTR_NOSUID | MOUNT_ATTR_NODEV | MOUNT_ATTR_NOEXEC,
                             .attr_clr = MOUNT_ATTR_RDONLY};
    for (int i = 0; i < count; ++i) {
        if (syscall(SYS_mount_setattr, writable[i], "", AT_EMPTY_PATH, &leaf, sizeof(leaf))
            || close(writable[i])) deny();
    }
}

#define LOAD_CONTEXT(structure, member) \
    {.code = BPF_LDX | BPF_MEM | BPF_W, .dst_reg = BPF_REG_2, .src_reg = BPF_REG_1, \
     .off = (short)offsetof(structure, member)}
#define NOT_EQUAL(value, distance) \
    {.code = BPF_JMP | BPF_JNE | BPF_K, .dst_reg = BPF_REG_2, .off = distance, .imm = value}
#define RETURN_VALUE(value) {.code = BPF_ALU64 | BPF_MOV | BPF_K, .dst_reg = BPF_REG_0, .imm = value}
#define RETURN_NOW {.code = BPF_JMP | BPF_EXIT}

static void attach_policy(int group, enum bpf_prog_type type, enum bpf_attach_type attach,
                          const struct bpf_insn *instructions, unsigned int count) {
    /* Fresh group only. Never replace, detach, override or repair old policy.
     * Legacy cgroup attachment retains the program after this fd/process exits;
     * it does not disappear if the root waiter is unexpectedly killed.
     */
    union bpf_attr query = {0};
    query.query.target_fd = (unsigned int)group;
    query.query.attach_type = attach;
    if (syscall(SYS_bpf, BPF_PROG_QUERY, &query, sizeof(query)) || query.query.prog_cnt) deny();
    static const char license[] = "GPL";
    union bpf_attr load = {0};
    load.prog_type = type;
    load.expected_attach_type = attach;
    load.insn_cnt = count;
    load.insns = (uint64_t)(uintptr_t)instructions;
    load.license = (uint64_t)(uintptr_t)license;
    int program = (int)syscall(SYS_bpf, BPF_PROG_LOAD, &load, sizeof(load));
    if (program < 0) deny();
    struct bpf_prog_info info = {0};
    union bpf_attr metadata = {0};
    metadata.info.bpf_fd = (unsigned int)program;
    metadata.info.info_len = sizeof(info);
    metadata.info.info = (uint64_t)(uintptr_t)&info;
    if (syscall(SYS_bpf, BPF_OBJ_GET_INFO_BY_FD, &metadata, sizeof(metadata)) || !info.id)
        deny();
    union bpf_attr binding = {0};
    binding.target_fd = (unsigned int)group;
    binding.attach_bpf_fd = (unsigned int)program;
    binding.attach_type = attach;
    int attached = (int)syscall(SYS_bpf, BPF_PROG_ATTACH, &binding, sizeof(binding));
    (void)close(program);
    if (attached) deny();
    query.query.prog_cnt = 0;
    /* A count-only query returns ENOSPC for nonempty attachments. Use one fixed
     * ID slot to require exactly the just-installed policy and no substitution.
     */
    unsigned int id = 0;
    query.query.prog_cnt = 1;
    query.query.prog_ids = (uint64_t)(uintptr_t)&id;
    if (syscall(SYS_bpf, BPF_PROG_QUERY, &query, sizeof(query))
        || query.query.prog_cnt != 1 || id != info.id || query.query.attach_flags) deny();
}

static void custody_network(int group, const char *role) {
    if (strcmp(role, "custody") != 0) return;
    const struct bpf_insn creation[] = {
        LOAD_CONTEXT(struct bpf_sock, family), NOT_EQUAL(AF_INET, 6),
        LOAD_CONTEXT(struct bpf_sock, type), NOT_EQUAL(SOCK_STREAM, 4),
        LOAD_CONTEXT(struct bpf_sock, protocol), NOT_EQUAL(IPPROTO_TCP, 2),
        RETURN_VALUE(1), RETURN_NOW, RETURN_VALUE(0), RETURN_NOW,
    };
    const struct bpf_insn connection[] = {
        LOAD_CONTEXT(struct bpf_sock_addr, user_family), NOT_EQUAL(AF_INET, 6),
        LOAD_CONTEXT(struct bpf_sock_addr, user_ip4), NOT_EQUAL((int)htonl(INADDR_LOOPBACK), 4),
        LOAD_CONTEXT(struct bpf_sock_addr, user_port), NOT_EQUAL((int)htons(5432), 2),
        RETURN_VALUE(1), RETURN_NOW, RETURN_VALUE(0), RETURN_NOW,
    };
    attach_policy(group, BPF_PROG_TYPE_CGROUP_SOCK, BPF_CGROUP_INET_SOCK_CREATE,
                  creation, sizeof(creation) / sizeof(creation[0]));
    attach_policy(group, BPF_PROG_TYPE_CGROUP_SOCK_ADDR, BPF_CGROUP_INET4_CONNECT,
                  connection, sizeof(connection) / sizeof(connection[0]));
    /* Custody is a client only. Block inbound/listener paths, including implicit
     * autobind by listen(), with a permanent syscall filter inherited by children.
     * This native release targets only reviewed Linux x86-64; x32/other ABIs deny.
     */
    const struct sock_filter rules[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, AUDIT_ARCH_X86_64, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        BPF_JUMP(BPF_JMP | BPF_JSET | BPF_K, 0x40000000U, 5, 0),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_bind, 4, 0),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_listen, 3, 0),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_accept, 2, 0),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, SYS_accept4, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
    };
    const struct sock_fprog filter = {.len = sizeof(rules) / sizeof(rules[0]),
                                     .filter = (struct sock_filter *)rules};
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        || prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &filter)) deny();
}

static int descriptor(const char *raw) {
    if (!raw[0] || strlen(raw) > 4) deny();
    for (const char *p = raw; *p; ++p) if (*p < '0' || *p > '9') deny();
    long value = strtol(raw, NULL, 10);
    if (value < 3 || value > 1023) deny();
    return (int)value;
}

static int gate_valid(int gate) {
    int domain = 0, type = 0;
    struct ucred peer;
    socklen_t size = sizeof(domain);
    if (getsockopt(gate, SOL_SOCKET, SO_DOMAIN, &domain, &size) || domain != AF_UNIX)
        return 0;
    size = sizeof(type);
    if (getsockopt(gate, SOL_SOCKET, SO_TYPE, &type, &size) || type != SOCK_SEQPACKET)
        return 0;
    size = sizeof(peer);
    return !getsockopt(gate, SOL_SOCKET, SO_PEERCRED, &peer, &size)
        && size == sizeof(peer) && peer.pid == getppid() && peer.uid == 0 && peer.gid == 0;
}

/* Transfer the ORIGINAL waiter's kernel handle before the only role allocation.
 * The host retains its socket before spawning us and never sends START until
 * receipt/validation of this handle. No start ACK is required to retain it.
 */
static void handoff(int gate, int timer) {
    static char ready[] = "single_call_waiter_ready\n";
    static const char start[] = "single_call_start\n";
    int own = (int)syscall(SYS_pidfd_open, getpid(), 0U);
    if (own < 0) deny();
    union { struct cmsghdr align; char bytes[CMSG_SPACE(sizeof(int))]; } control = {0};
    struct iovec data = {.iov_base = ready, .iov_len = sizeof(ready) - 1};
    struct msghdr message = {.msg_iov = &data, .msg_iovlen = 1,
        .msg_control = control.bytes, .msg_controllen = sizeof(control.bytes)};
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    header->cmsg_level = SOL_SOCKET;
    header->cmsg_type = SCM_RIGHTS;
    header->cmsg_len = CMSG_LEN(sizeof(int));
    memcpy(CMSG_DATA(header), &own, sizeof(own));
    ssize_t sent = sendmsg(gate, &message, MSG_DONTWAIT | MSG_NOSIGNAL);
    (void)close(own);
    if (sent != (ssize_t)(sizeof(ready) - 1)) deny();
    struct pollfd descriptors[] = {{.fd = gate, .events = POLLIN},
                                  {.fd = timer, .events = POLLIN}};
    /* EINTR, disconnect, unexpected packet/ancillary data and timeout all deny.
     * recvmsg without a control buffer discards/closes any supplied descriptors;
     * MSG_CTRUNC still makes the command invalid.
     */
    if (poll(descriptors, 2, 3000) != 1 || descriptors[0].revents != POLLIN
        || descriptors[1].revents) deny();
    char packet[sizeof(start)];
    struct iovec command = {.iov_base = packet, .iov_len = sizeof(packet)};
    struct msghdr received = {.msg_iov = &command, .msg_iovlen = 1};
    ssize_t count = recvmsg(gate, &received, MSG_DONTWAIT | MSG_CMSG_CLOEXEC);
    if ((received.msg_flags & ~MSG_CMSG_CLOEXEC) || count != (ssize_t)(sizeof(start) - 1)
        || memcmp(packet, start, sizeof(start) - 1)) deny();
}

static int retire(int group) {
    int kill = openat(group, "cgroup.kill", O_WRONLY | O_CLOEXEC | O_NOFOLLOW);
    if (kill < 0) return 0;
    struct stat info;
    struct statfs fs;
    int valid = !fstat(kill, &info) && S_ISREG(info.st_mode) && info.st_uid == 0
        && !(info.st_mode & 0022) && !fstatfs(kill, &fs) && fs.f_type == CGROUP2_SUPER_MAGIC;
    ssize_t written = valid ? write(kill, "1\n", 2) : -1;
    (void)close(kill);
    if (written != 2) return 0;
    /* Fixed observation ceiling; caller still owns independent original cleanup.
     * Never remove the group or retry an uncertain kill write.
     */
    for (int attempt = 0; attempt < 100; ++attempt) {
        if (kernel_text(group, "cgroup.events", "populated 0\nfrozen 0\n")) return 1;
        struct timespec pause = {.tv_sec = 0, .tv_nsec = 10000000};
        if (nanosleep(&pause, NULL)) return 0;
    }
    return 0;
}

int main(int argc, char **argv, char **envp) {
    struct timespec origin;
    if (clock_gettime(CLOCK_MONOTONIC, &origin)) deny();
    uid_t real_uid, effective_uid, saved_uid;
    gid_t real_gid, effective_gid, saved_gid;
    struct stat input, null, output, diagnostic;
    struct rlimit core = {0, 0};
    struct sched_param normal = {.sched_priority = 0};
    if (argc != 4 || (strcmp(argv[1], "receipt") && strcmp(argv[1], "provider")
                     && strcmp(argv[1], "custody"))) deny();
    /* Only inherited original handles, never a path, PID or command selector. */
    int group = descriptor(argv[2]);
    int gate = descriptor(argv[3]);
    if (gate == group || !gate_valid(gate)) deny();
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
    int saved_group = fcntl(group, F_DUPFD_CLOEXEC, 5);
    int saved_gate = fcntl(gate, F_DUPFD_CLOEXEC, 5);
    if (saved_group < 0 || saved_gate < 0 || dup3(saved_group, 3, O_CLOEXEC) < 0
        || dup3(saved_gate, 4, O_CLOEXEC) < 0
        || syscall(SYS_close_range, 5U, UINT_MAX, 0U) != 0) deny();
    for (int fd = 0; fd < 3; ++fd) if (fcntl(fd, F_SETFD, 0) < 0) deny();
    /* Reset inherited signal dispositions/mask before allocating a child. */
    struct sigaction action = {.sa_handler = SIG_DFL};
    if (sigemptyset(&action.sa_mask)) deny();
    for (int sig = 1; sig < NSIG; ++sig) {
        if (sig != SIGKILL && sig != SIGSTOP && sigaction(sig, &action, NULL)
            && errno != EINVAL) deny();
    }
    if (sigprocmask(SIG_SETMASK, &action.sa_mask, NULL)) deny();
    int timer = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC | TFD_NONBLOCK);
    struct itimerspec expiry = {.it_value = origin};
    expiry.it_value.tv_sec += 3;
    if (timer < 0 || timerfd_settime(timer, TFD_TIMER_ABSTIME, &expiry, NULL)) deny();
    handoff(4, timer);
    expiry.it_value = origin;
    expiry.it_value.tv_sec += 30;
    if (timerfd_settime(timer, TFD_TIMER_ABSTIME, &expiry, NULL)
        || !kernel_text(3, "cgroup.events", "populated 0\nfrozen 0\n")
        || !resource_policy(3, argv[1])) deny();
    int pidfd = -1;
    pid_t parent = getpid();
    struct clone_args args = {
        .flags = CLONE_INTO_CGROUP | CLONE_PIDFD | CLONE_NEWNS
            | (strcmp(argv[1], "receipt") == 0 ? CLONE_NEWNET : 0),
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
            || setsid() < 0 || close(4) || close(timer)) deny();
        filesystem_policy(argv[1]);
        custody_network(3, argv[1]);
        if (close(3)) deny();
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
    if (pidfd < 0) { (void)retire(3); deny(); }
    struct pollfd watched[] = {{.fd = pidfd, .events = POLLIN},
                               {.fd = 4, .events = POLLIN},
                               {.fd = timer, .events = POLLIN}};
    int observed = poll(watched, 3, 30000);
    int completed = observed > 0 && watched[0].revents == POLLIN
        && !watched[1].revents && !watched[2].revents;
    /* Disconnect, unsolicited packet, clock deadline and even normal main exit
     * retire ALL descendants before the root waiter can report success.
     */
    int clean = retire(3);
    struct pollfd exited = {.fd = pidfd, .events = POLLIN};
    if (poll(&exited, 1, 1000) != 1 || exited.revents != POLLIN) deny();
    siginfo_t result = {0};
    int waited = waitid(P_PIDFD, (id_t)pidfd, &result, WEXITED | WNOHANG);
    (void)close(pidfd);
    (void)close(timer);
    (void)close(4);
    (void)close(3);
    if (!completed || !clean || waited || result.si_pid != child) deny();
    if (result.si_code == CLD_EXITED) return result.si_status;
    if (result.si_code == CLD_KILLED || result.si_code == CLD_DUMPED)
        return 128 + result.si_status;
    deny();
}
