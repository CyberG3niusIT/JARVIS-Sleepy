"""
Developer Tools — Safety Module

Three-tier command allowlist with validation and output sanitization.
"""

import re
import shlex
from typing import Tuple

# Tier 1: Always allowed (read-only)
TIER1_ALLOWED = {
    # File inspection
    'cat', 'head', 'tail', 'less', 'wc', 'file', 'stat',
    # Search
    'grep', 'rg', 'find', 'locate', 'which', 'whereis',
    # Listing
    'ls', 'tree', 'du', 'df',
    # Git read-only
    'git status', 'git log', 'git diff', 'git branch', 'git show',
    'git remote', 'git tag', 'git stash list',
    # System info
    'ps', 'top', 'htop', 'free', 'uptime', 'uname', 'lsb_release',
    'lscpu', 'lsblk', 'lsusb', 'lspci', 'hostname', 'whoami', 'id',
    'nproc', 'arch',
    # Network info
    'ip', 'ifconfig', 'ping', 'dig', 'nslookup', 'host', 'ss', 'netstat',
    'curl', 'wget',
    # Service status
    'systemctl status', 'systemctl is-active', 'systemctl list-units',
    'journalctl', 'service --status-all',
    # Package info
    'pip list', 'pip show', 'pip freeze',
    'dpkg -l', 'dpkg -s', 'apt list',
    'python3 --version', 'python --version', 'node --version',
    'npm list', 'ffmpeg -version',
    # Docker read-only
    'docker ps', 'docker images', 'docker logs',
    # Misc
    'date', 'cal', 'env', 'printenv',
}

# Tier 2: Safe writes (non-destructive)
TIER2_SAFE_WRITES = {
    'cp', 'mkdir', 'touch',
    'git add', 'git commit', 'git stash', 'git stash pop',
    'tee', 'chmod', 'chown',
}

# Tier 3: Confirmation required (destructive)
TIER3_CONFIRMATION = {
    'rm', 'rmdir', 'mv', 'kill', 'killall', 'pkill',
    'systemctl stop', 'systemctl restart', 'systemctl start',
    'git reset', 'git clean', 'git checkout', 'git revert',
    'pip install', 'pip uninstall',
    'apt install', 'apt remove', 'apt purge',
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

# Blocked patterns (regex)
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
# & (not part of &&). Found by an agentic-system audit (session #7):
# classify_command() only ever inspected parts[0]/the first two words, so
# "git status ; cat /etc/shadow" or "git log && rm important_file.txt"
# classified as 'allowed'/Tier-1 (matching "git status"/"git log") while
# _run_cmd() (core/tools/developer_tools.py) executes the ENTIRE string
# via subprocess.run(..., shell=True) — the chained command actually ran,
# completely bypassing the tier system. This is deliberately a coarse,
# conservative detector rather than a full shell parser: a false
# positive (e.g. a `;` that's actually inside a quoted argument) just
# means a simple command gets asked for confirmation instead of
# auto-allowed — a safe degradation, not a functionality break — whereas
# a false negative here is an actual security hole. Does NOT match a
# bare `|` (pipe) — piping Tier-1 command output through another command
# for filtering, e.g. "ps aux | grep foo", is ordinary intended usage;
# pipe-to-a-shell specifically is still caught by BLOCKED_PATTERNS below
# regardless of this chaining check.
_CHAIN_OPERATOR_RE = re.compile(r';|&&|\|\||\n|(?<!&)&(?!&)')

_TIER_SEVERITY = {'allowed': 0, 'safe_write': 1, 'confirmation': 2, 'blocked': 3}


def _classify_single_command(command: str) -> Tuple[str, str]:
    """Classify ONE simple (non-chained) command. Extracted from the old
    classify_command() body — see classify_command()'s docstring for why
    chained commands are handled separately, never falling through to
    this function's 'allowed'/'safe_write' results directly."""
    stripped = command.strip()

    # Extract the base command (first word or first two words for compound commands)
    parts = stripped.split()
    if not parts:
        return ('blocked', 'Empty command')

    base_cmd = parts[0]
    two_word = f"{parts[0]} {parts[1]}" if len(parts) > 1 else ""

    # Check blocked commands
    if base_cmd in BLOCKED_COMMANDS:
        return ('blocked', f'Command "{base_cmd}" is never allowed')

    # Check tier 1 (always allowed) — check two-word first for compound commands
    if two_word in TIER1_ALLOWED:
        return ('allowed', f'Read-only command: {two_word}')
    if base_cmd in TIER1_ALLOWED:
        return ('allowed', f'Read-only command: {base_cmd}')

    # Check tier 2 (safe writes)
    if two_word in TIER2_SAFE_WRITES:
        return ('safe_write', f'Safe write operation: {two_word}')
    if base_cmd in TIER2_SAFE_WRITES:
        return ('safe_write', f'Safe write operation: {base_cmd}')

    # Check tier 3 (confirmation required)
    if two_word in TIER3_CONFIRMATION:
        return ('confirmation', f'Destructive operation requires confirmation: {two_word}')
    if base_cmd in TIER3_CONFIRMATION:
        return ('confirmation', f'Destructive operation requires confirmation: {base_cmd}')

    # Unknown command — treat as confirmation required for safety
    return ('confirmation', f'Unknown command "{base_cmd}" — requires confirmation')


def classify_command(command: str) -> Tuple[str, str]:
    """
    Classify a command into a safety tier.

    Returns:
        Tuple of (tier, reason) where tier is one of:
        'allowed', 'safe_write', 'confirmation', 'blocked'
    """
    stripped = command.strip()

    # Check blocked patterns first — against the FULL string, so this
    # still catches e.g. pipe-to-bash regardless of chaining below.
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, stripped):
            return ('blocked', f'Blocked pattern detected: {pattern}')

    if not stripped:
        return ('blocked', 'Empty command')

    if _CHAIN_OPERATOR_RE.search(stripped):
        # Chained/compound command: classify every segment independently
        # and never report anything better than 'confirmation' for the
        # whole thing, regardless of what any individual segment's own
        # classification would have been — a chain of all-Tier-1 reads
        # is almost certainly harmless, but this function's job is to be
        # the safety boundary, not to prove harmlessness perfectly.
        segments = [s.strip() for s in _CHAIN_OPERATOR_RE.split(stripped) if s.strip()]
        segment_results = [_classify_single_command(seg) for seg in segments] or [
            ('confirmation', 'Unparseable chained command')
        ]
        worst = max(segment_results, key=lambda r: _TIER_SEVERITY[r[0]])
        if worst[0] == 'blocked':
            return ('blocked', f'Chained command contains a blocked segment: {worst[1]}')
        return (
            'confirmation',
            f'Chained/compound command requires confirmation (worst segment: {worst[1]})',
        )

    return _classify_single_command(stripped)


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
