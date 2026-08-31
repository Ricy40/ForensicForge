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
    "the snippets - do not invent settings the snippets don't support.\n\n"
    "Respond in two parts:\n"
    "1. A YAML list of Ansible tasks (each with a `name` and a module such as "
    "`ansible.builtin.package`, `ansible.builtin.lineinfile`, "
    "`ansible.builtin.template`, `ansible.builtin.service`, or "
    "`ansible.builtin.user`) inside a ```yaml code block.\n"
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
