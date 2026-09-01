"""Repairs for known, recurring shapes of broken LLM output.

This project found a growing list of distinct, reproducible generation
bugs by actually provisioning real specs (see docs/METHODOLOGY.md): a
YAML nested-quote failure (with a backslash-escaping variant), an
`ansible.builtin.lineinfile` `line:` value using a regex backreference
(which that parameter doesn't support - it's written literally), an
`ansible.builtin.user` task misusing `path:` (a `file`-module parameter),
a `notify:` key with nowhere to resolve (no `handlers/main.yml` ever
gets written), and a whole trailing `handlers:` block appended after the
task list (which isn't valid as one YAML document at all, and has the
same "nowhere to resolve" problem even if it were). None are one-off
typos worth patching by hand in a generated role; each is a *pattern*
the LLM produces repeatably given a similar prompt. This module
recognizes each pattern generically (by shape, not by matching the exact
broken text first seen) and repairs it, rather than leaving every future
occurrence to fail the same way. Every repair is recorded in the string
list each function returns, never applied silently - see
write_ansible_role()'s use of these. A single generation can trigger more
than one of these at once (confirmed live: a nested-quote issue and a
trailing handlers: block in the same output) - parse_tasks() retries
through its repair list in a bounded loop, not just once, for exactly
this reason.

This is deliberately a short, closed list of specific, well-understood
patterns - not a general "ask the LLM to fix its own YAML" loop (which
would trade one unreliable generation step for two) and not an attempt to
catch every possible mistake. A pattern not on this list still fails the
same way it did before, with the raw output attached to the error, same
as always.
"""

import copy
import re

import yaml

_QUOTE_REPAIR_LINE = re.compile(r"^(\s*(?:line|regexp)\s*:\s*)'(.*)'\s*$")
_BACKREF = re.compile(r"\\(\d+)")
_ALTERNATION = re.compile(r"\(([\w.]+(?:\|[\w.]+)+)\)")
_TOP_LEVEL_HANDLERS_LINE = re.compile(r"^handlers:\s*$")


def repair_trailing_handlers_block(yaml_text: str, error: yaml.YAMLError) -> tuple[str | None, str | None]:
    """Strip a top-level `handlers:` block the LLM appended after the
    task-list sequence, which YAML can't parse as a single document at
    all (a top-level sequence can't be followed by a top-level mapping
    key in the same node - PyYAML fails immediately at the `handlers:`
    line with "expected <block end>, but found '?'").

    Real example: a web-app-misconfig generation emitted a normal task
    list, then appended a full `handlers:` section directly at the end
    (rather than a `notify:` key on individual tasks - see
    repair_dangling_notify(), which handles that variant once parsing
    succeeds). Since this pipeline has nowhere to put a handlers/main.yml
    anyway (write_ansible_role() never writes one - see
    repair_dangling_notify()'s own docstring for why that's true even
    when the YAML parses fine), the block is removed rather than
    reconstructed - the tasks before it are already a complete, valid
    list on their own once it's gone.
    """
    mark = getattr(error, "problem_mark", None)
    if mark is None:
        return None, None

    lines = yaml_text.splitlines()
    for line_no in (mark.line, mark.line - 1):
        if not (0 <= line_no < len(lines)):
            continue
        if _TOP_LEVEL_HANDLERS_LINE.match(lines[line_no]):
            truncated = "\n".join(lines[:line_no]).rstrip()
            return truncated, (
                f"removed a trailing top-level handlers: block starting at line "
                f"{line_no + 1} (no handlers file exists for it to belong to)"
            )
    return None, None


def repair_yaml_text(yaml_text: str, error: yaml.YAMLError) -> tuple[str | None, str | None]:
    """Try to fix a YAML parse failure caused by an unescaped `'` nested
    inside a single-quoted `line:`/`regexp:` scalar (e.g.
    `line: 'listen_addresses = '*''`, which YAML reads as the scalar
    ending after the second `'`, leaving `*''` as trailing garbage).

    Real example this week: a Postgres spec asked to set
    `listen_addresses = '*'`, and the LLM wrote that literal 4-character
    sequence straight into an already single-quoted YAML value without
    escaping the inner quotes (YAML's own rule: double them, `''`, or use
    a double-quoted scalar instead). Reproduced identically on a second,
    independent generation of the same spec - a pattern, not a fluke.

    Fixed by finding the line PyYAML's own error points at, and - if it
    matches the `key: '...'` shape - re-emitting that value as a properly
    escaped double-quoted YAML string via yaml.safe_dump(), which handles
    arbitrary embedded quotes correctly regardless of what the specific
    content is (not hardcoded to `'*'`). Returns (repaired_text, note) on
    success, (None, None) if the failure doesn't match this shape.
    """
    mark = getattr(error, "problem_mark", None)
    if mark is None:
        return None, None

    lines = yaml_text.splitlines()
    # PyYAML's problem_mark sometimes points at the line the scalar
    # *starts* on and sometimes at where parsing actually gave up
    # shortly after - both were seen across the two real failures this
    # week, so both are tried.
    for line_no in (mark.line, mark.line - 1):
        if not (0 <= line_no < len(lines)):
            continue
        match = _QUOTE_REPAIR_LINE.match(lines[line_no])
        if match is None:
            continue
        prefix, content = match.groups()
        # Single-quoted YAML scalars have no backslash-escape syntax at all
        # (only doubling a quote, '', escapes one) - a `\'` or `\"` inside
        # one is never valid YAML, so it can only be the LLM applying
        # Python/JS-style escaping it doesn't need. Confirmed against a
        # second, independent real failure (`line: 'listen_addresses =
        # \'localhost\''`): without this normalization, the earlier fix
        # produced YAML that parsed fine but carried the literal, bogus
        # backslashes straight into the config value written to the VM -
        # syntactically valid YAML, semantically wrong for the config file
        # it's writing to. See docs/METHODOLOGY.md.
        content = content.replace("\\'", "'").replace('\\"', '"')
        repaired_value = yaml.safe_dump(content, default_style='"').strip()
        lines[line_no] = f"{prefix}{repaired_value}"
        return "\n".join(lines), (
            f"repaired an unescaped-quote YAML error on line {line_no + 1} "
            f"by re-quoting its value"
        )

    return None, None


def repair_lineinfile_backreferences(tasks: list[dict]) -> tuple[list[dict], list[str]]:
    """Split a lineinfile task whose `line:` uses a regex backreference
    (`\\1`) that its `regexp:` alternation was meant to feed, into one
    task per alternative with the backreference resolved to a literal.

    `ansible.builtin.lineinfile`'s `line:` is written to the file
    literally - it is not a regex replacement template, so a backreference
    there is never valid, regardless of what `regexp:` captures. Real
    example this week: `regexp: '^#*(PermitRootLogin|PasswordAuthentication)
    [a-zA-Z]*'` paired with `line: '\\1 yes'` - applied for real, this
    would write the literal string `\\1 yes` into sshd_config, not
    `PermitRootLogin yes` / `PasswordAuthentication yes`, silently failing
    the task's own stated purpose. Repaired by reading the alternation out
    of `regexp:` and emitting one task per alternative, each with a
    narrowed `regexp:` and the backreference in `line:` resolved to that
    alternative's own literal name.
    """
    repaired: list[dict] = []
    notes: list[str] = []

    for task in tasks:
        args = task.get("ansible.builtin.lineinfile")
        if not isinstance(args, dict):
            repaired.append(task)
            continue

        line = str(args.get("line", ""))
        regexp = str(args.get("regexp", ""))
        backref_match = _BACKREF.search(line)
        alt_match = _ALTERNATION.search(regexp)
        if not (backref_match and alt_match):
            repaired.append(task)
            continue

        alternatives = alt_match.group(1).split("|")
        suffix = _BACKREF.sub("", line, count=1).strip()
        base_name = str(task.get("name", "")) or "Set directive"
        for alternative in alternatives:
            new_task = copy.deepcopy(task)
            new_task["name"] = f"{base_name} ({alternative})"
            new_task["ansible.builtin.lineinfile"] = {
                **args,
                "regexp": regexp.replace(alt_match.group(0), alternative),
                "line": f"{alternative} {suffix}".strip(),
            }
            repaired.append(new_task)
        notes.append(
            f"split lineinfile task {base_name!r} (line: {line!r} referenced a "
            f"regex backreference lineinfile's line: parameter doesn't support) "
            f"into {len(alternatives)} tasks, one per alternative"
        )

    return repaired, notes


def repair_user_module_path_misuse(tasks: list[dict]) -> tuple[list[dict], list[str]]:
    """Rewrite an `ansible.builtin.user` task that was given a `path:`
    parameter into the `ansible.builtin.file` task it was actually trying
    to express.

    `ansible.builtin.user` has no `path:` parameter at all (confirmed
    against a real failure this week: "Unsupported parameters for
    (ansible.builtin.user) module: path"). The task's own intent - set
    ownership on an existing filesystem path - is exactly what
    `ansible.builtin.file` with `owner:`/`group:`/`state: directory` does;
    the LLM appears to have reached for the wrong module for an
    ownership-only change. Repaired by carrying `name:` over as `owner:`
    and `group:` over as `group:` on a new `ansible.builtin.file` task.
    """
    repaired: list[dict] = []
    notes: list[str] = []

    for task in tasks:
        args = task.get("ansible.builtin.user")
        if not isinstance(args, dict) or "path" not in args:
            repaired.append(task)
            continue

        new_args = {"path": args["path"], "state": "directory"}
        if "name" in args:
            new_args["owner"] = args["name"]
        if "group" in args:
            new_args["group"] = args["group"]

        new_task = {k: v for k, v in task.items() if k != "ansible.builtin.user"}
        new_task["ansible.builtin.file"] = new_args
        repaired.append(new_task)
        notes.append(
            f"rewrote task {task.get('name', '')!r} from ansible.builtin.user "
            f"(which has no path: parameter) to ansible.builtin.file"
        )

    return repaired, notes


def repair_dangling_notify(tasks: list[dict]) -> tuple[list[dict], list[str]]:
    """Strip any `notify:` key referencing a handler, since this pipeline
    never writes a handlers/main.yml for one to exist in.

    write_ansible_role() only ever creates tasks/main.yml and meta/main.yml
    - there is no role file a `notify:` could ever resolve against, so any
    task using it fails the whole play immediately with "The requested
    handler '...' was not found" (confirmed live: a web-app-misconfig
    role's `notify: restart apache` failed exactly this way, ~10 minutes
    into a live boot). Safe to simply remove rather than reject the whole
    generation, unlike the template/copy-src case (repair.py's other
    external-file rejections, over in ansible_writer.py): removing a
    `notify:` key changes nothing about what config gets written - the
    lineinfile/copy tasks it was attached to still run and still apply
    the claimed misconfiguration - it only removes a handler trigger that
    was always going to crash the play. Every real generation seen using
    `notify:` this way also included its own explicit, unconditional
    `ansible.builtin.service: state: restarted` task later in the same
    role (as if the LLM added a manual fallback the handler was meant to
    cover too) - stripping the broken notify still leaves the service
    genuinely restarted by that explicit task.
    """
    repaired: list[dict] = []
    notes: list[str] = []

    for task in tasks:
        if "notify" not in task:
            repaired.append(task)
            continue
        new_task = {k: v for k, v in task.items() if k != "notify"}
        repaired.append(new_task)
        notes.append(
            f"removed notify: from task {task.get('name', '')!r} - no handlers file "
            f"exists for it to reference, so it always fails the play"
        )

    return repaired, notes
