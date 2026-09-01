from langchain_core.documents import Document

SYSTEM_PROMPT = (
    "You are an assistant that turns plain-English requests into detailed "
    "virtual machine configuration descriptions for cybersecurity training "
    "environments. Describe the OS, installed packages, running services, "
    "network settings, and any deliberately introduced misconfigurations or "
    "vulnerabilities implied by the request."
)


def build_prompt(spec: str) -> str:
    """Week-1 prompt: no retrieval, free-text prose output.

    Kept unchanged (and unused by default) so ungrounded output can still be
    compared against the RAG path for the dissertation's evaluation chapter.
    """
    return f"{SYSTEM_PROMPT}\n\nRequest: {spec}\n\nVM configuration:"


RAG_SYSTEM_PROMPT = (
    "You are an assistant that turns plain-English requests into Ansible task "
    "lists for provisioning cybersecurity training VMs. You are given reference "
    "snippets retrieved from a curated knowledge base of real sshd_config "
    "directives, Ansible task examples, and known misconfiguration patterns. "
    "Ground every directive, module, and vulnerability claim in the request or "
    "the snippets - do not invent settings the snippets don't support, and never "
    "invent a module name that isn't one of the ones listed below or given in a "
    "reference snippet, even if no snippet covers what you need - omit the task "
    "rather than guess at a module that might not exist.\n\n"
    "Respond in two parts:\n"
    "1. A YAML list of Ansible tasks (each with a `name` and a module such as "
    "`ansible.builtin.package`, `ansible.builtin.lineinfile`, "
    "`ansible.builtin.copy` (with an inline `content:`, not a `src:` file), "
    "`ansible.builtin.service`, `ansible.builtin.user`, `ansible.builtin.file`, or "
    "`community.general.ufw` for firewall rules) inside a ```yaml code block. "
    "Every task must be fully self-contained: never use "
    "`ansible.builtin.template` or any module that reads a file from the "
    "Ansible controller (e.g. `copy`'s `src:`), since no such file exists - "
    "only the tasks you write here get created, nothing else. Never use `notify:` "
    "either - no handlers file exists for it to reference, so it always fails; if a "
    "service needs restarting after a config change, add an explicit "
    "`ansible.builtin.service` task with `state: restarted` instead. Never run an "
    "interactive command (e.g. `mysql_secure_installation`) via "
    "`ansible.builtin.shell`/`ansible.builtin.command` - there is no terminal to answer "
    "its prompts, so it hangs forever; use a module built for the task instead (e.g. "
    "`community.mysql.mysql_user` to set a database password directly).\n"
    "2. An 'Applied misconfigurations' section: one line per deliberate "
    "weakness introduced, naming which snippet it came from and why it's a "
    "real vulnerability. Quote the exact directive/line you set in "
    "backticks (e.g. `PermitRootLogin yes`) so each claim can be checked "
    "against the config file automatically."
)


def _format_snippets(snippets: list[Document]) -> str:
    return "\n\n".join(
        f"[{i}] (source: {doc.metadata.get('source', 'unknown')})\n{doc.page_content}"
        for i, doc in enumerate(snippets, start=1)
    )


def build_rag_prompt(spec: str, snippets: list[Document]) -> str:
    return (
        f"{RAG_SYSTEM_PROMPT}\n\n"
        f"Reference snippets:\n{_format_snippets(snippets)}\n\n"
        f"Request: {spec}\n\n"
        f"Response:"
    )
