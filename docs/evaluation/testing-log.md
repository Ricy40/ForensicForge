# Testing log: seven vulnerability-class scenarios

Working log for the dissertation's testing section. One section per
scenario, filled in as each `build-scenario` run and its manual
verification pass complete. Screenshots referenced here live in
`docs/evaluation/screenshots/` (not committed by this log itself - see
the README there for the naming convention).

For each scenario:
1. `build-scenario` generates the VM, verifies its claimed vulnerabilities
   live, builds a storyline, plants evidence, and exports a portable
   image - see that run's own `scenario.md` and `report.json` under
   `generated/<run-id>/` for the full machine-readable record.
2. A manual pass (`vagrant up` + `vagrant ssh`, or a client/browser from
   the host) re-confirms the same vulnerabilities by hand, for
   screenshots a `report.json` can't provide.

Once every scenario below is filled in, `docs/METHODOLOGY.md` gets a
consolidated evaluation-round section built from all seven together.

---

# Generate Run Commands

Venv
```powershell
cd C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge
.venv\Scripts\Activate.ps1
```

SSH Bastion
```powershell
forensicforge build-scenario "Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise" --name "ssh bastion"
```

FTP Anon Upload
```powershell
forensicforge build-scenario "Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise" --name "ftp anon upload"
```

Web App Misconfig
```powershell
forensicforge build-scenario "Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise" --name "web app misconfig"
```

Exposed Database
```powershell
forensicforge build-scenario "Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise" --name "exposed database"
```

Local Privesc
```powershell
forensicforge build-scenario "Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise" --name "local privesc"
```

Unpacthed OpenSSL
```powershell
forensicforge build-scenario "Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise" --name "unpatched openssl"
```

Disabled Logging
```powershell
forensicforge build-scenario "Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering" --name "disabled logging"
```


---

## 1. SSH bastion (weak SSH configuration)

**Spec:** `Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise`
**Run:** `20260901-204737-ssh bastion`

### build-scenario result

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-182742-exposed database> forensicforge build-scenario "Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise" --name "ssh bastion"
Generating a VM for: 'Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise' ...
  Retrieved 4 corpus snippet(s):
    - sshd_config/port.md
    - misconfigurations/weak_ssh_root_login.md
    - sshd_config/x11_forwarding.md
    - sshd_config/password_authentication.md
  Wrote run '20260901-204737-ssh bastion' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-204737-ssh bastion

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [TRUE] `Port 2222`: This sets the SSH port to a non-default value, which is not a security control on its own and makes it trivially discoverable by any port scan.
         TRUE on the live VM, and Ansible's own output confirms this run's role caused it
  [TRUE] `PermitRootLogin yes`: This allows an attacker to brute-force the root account directly over SSH without needing to compromise a lower-privileged user first and escalate.
         TRUE on the live VM, but the task reported 'ok' not 'changed' - it was already true before this run applied anything, NOT attributable to this role (the exact week 3 PermitRootLogin gap this command exists to catch)
  [TRUE] `PasswordAuthentication yes`: This enables password authentication, making it vulnerable to brute-force and credential-stuffing attacks.
         TRUE on the live VM, and Ansible's own output confirms this run's role caused it

Building a forensic storyline from what actually verified ...

Intrusion via a weakened SSH configuration
  Yu, Pratt and Berger, a small landscaping company, uses this machine to let staff remotely access the office server. Valerie Mccoy looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a weakened SSH configuration - specifically, 'Port 2222' (task: 'Set SSH port to 2222 (for simulation purposes)') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True

=== Scenario ready ===
Intrusion via a weakened SSH configuration
Yu, Pratt and Berger, a small landscaping company, uses this machine to let staff remotely access the office server. Valerie Mccoy looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu SSH bastion host intentionally misconfigured for a penetration testing exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a weakened SSH configuration - specifically, 'Port 2222' (task: 'Set SSH port to 2222 (for simulation purposes)') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-204737-ssh bastion\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-204737-ssh bastion\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.

Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-204737-ssh bastion\report.json
```

### Manual verification

```powershell
cd "generated\20260901-204737-ssh bastion"
vagrant up --provider=hyperv
vagrant ssh -c "hostname -I"
vagrant ssh
```

Inside the VM:

```bash
sudo cat /etc/ssh/sshd_config | grep -E 'Port|PermitRootLogin|PasswordAuthentication|X11Forwarding'
```

From the host, in a second terminal (tests the weak config as an
external attacker would):

```powershell
ssh -p 2222 root@<vm-ip>
```

It should prompt for a password rather than refusing outright - confirms
`PermitRootLogin yes` + `PasswordAuthentication yes` are both live.

Clean up:

```powershell
vagrant destroy -f
```

**Results, run `20260901-204737-ssh bastion` (recorded 2026-09-02):**

`sudo cat /etc/ssh/sshd_config | grep -E ...` confirmed all four claimed
directives present in the file (`Port 2222`, `PermitRootLogin yes`,
`PasswordAuthentication yes`, `X11Forwarding no`), matching what
`verify-vulnerabilities` already reported. `ssh -p 2222 root@<vm-ip>`
from the host, however, failed outright: `Connection refused`.

**Finding 1 - the generated role never restarts sshd.** This run's
`tasks/main.yml` is four `lineinfile` tasks against `/etc/ssh/sshd_config`
and nothing else - no restart, no `notify:`, nothing. Diagnosed live
before concluding anything: `sudo ss -tlnp | grep -E ':22 |:2222'` showed
`sshd` still listening only on port 22; `sudo systemctl status ssh` (and
`status sshd`, confirmed the same unit - Ubuntu aliases `sshd` to
`ssh.service` here, so that wasn't the cause) showed it had been running
continuously since boot, never restarted. `retrieval.json` for this run
shows why: all 4 retrieved snippets were per-directive reference docs
(`sshd_config/port.md`, `misconfigurations/weak_ssh_root_login.md`,
`sshd_config/x11_forwarding.md`, `sshd_config/password_authentication.md`)
- this spec touching four separate sshd directives filled every
retrieval slot (`k=4`) with docs explaining *why* each directive matters,
leaving no room for `ansible_tasks/restart_sshd_service.md` or
`deploy_sshd_config.md`, which model the restart step. Notably, this is
a different class of gap than the vsftpd finding in scenario 2: the
system prompt *always* includes an explicit, retrieval-independent
instruction ("if a service needs restarting after a config change, add
an explicit `ansible.builtin.service` task with `state: restarted`"),
present in every generation call regardless of what got retrieved - and
the model still didn't follow it here. That makes this a genuine LLM
output-reliability limitation, not (only) a corpus-grounding gap: the
instruction was there and wasn't reliably applied.

Restarting sshd by hand (`sudo systemctl restart ssh`) confirmed the
config itself is genuine: `ss -tlnp` immediately showed `sshd` listening
on 2222, and `ssh -p 2222 root@<vm-ip>` from the host reached a real
`root@<vm-ip>'s password:` prompt - `Port 2222`, `PermitRootLogin yes`,
and `PasswordAuthentication yes` are all correctly wired once the daemon
actually reloads them.

**Finding 2 - no credential is ever provisioned, so the login can't
actually be completed.** Password login for `root` was attempted and
rejected (`Permission denied`) - not because the config is wrong, but
because root has no password set on a stock Vagrant box, and this run's
role (confirmed via `tasks/main.yml` and `generation.md` - no
`ansible.builtin.user` task, no `password:` anywhere) never sets one.
Completed the demonstration on the live VM rather than stopping at the
diagnosis, since the screenshots for this scenario capture the full
sequence end-to-end. Two manual steps were performed, neither produced
by the generated role itself, and both are visible in the screenshots:

```bash
sudo systemctl restart ssh   # Finding 1's workaround, see above
sudo passwd root             # sets a password ForensicForge never sets
```

Followed by, from the host:

```powershell
ssh -p 2222 root@<vm-ip>
```

- which then succeeded with the password just set, giving a root shell
over the intentionally weakened config. **This last step is a manual
completion of the exercise, not a capability of the generated role or
of ForensicForge itself** - the screenshots document what a tester does
to finish exploiting the scenario as designed, not what a fresh
`build-scenario` run alone produces bootable and exploitable
out-of-the-box. The claim text ("allows an attacker to brute-force the
root account directly over SSH") implies a guessable/weak credential
exists to brute-force; nothing in this pipeline currently creates one,
so as generated, this scenario enables the *mechanism* for a
password-based attack but never supplies anything to attack - the same
shape of gap as the database class's `mysql_user` scope limitation
documented above, not something a trainee or instructor should be
expected to set up separately in a real deployment. Left open whether
to close this the way the vsftpd and unpatched-package gaps were closed
(a corpus doc modeling an explicit weak-root-password task for this
scenario class) or to document it as a standing limitation - not
decided as part of this testing pass.

**What this means for the evaluation:** two independent, real gaps for
this scenario class, evidenced live rather than assumed: (1) the
restart step, not covered by any retrieved snippet for this specific
spec and not reliably supplied by the always-present system-prompt
instruction either; (2) no task ever establishes an actual root
credential, so even a fully-restarted, correctly-configured instance of
this scenario isn't completely exploitable end-to-end as claimed. Both
were worked around manually on the VM to produce a genuine root-login
screenshot, but neither workaround is something `build-scenario`
performs on its own - a fresh run today still needs both done by hand
to reach that end state. `verify-vulnerabilities`'s `[TRUE]` findings
for all three attributable directives remain accurate for what they
check (file content, attribution) - both gaps are in what the
generated role does, not in the verification tooling.

**Screenshot(s):** restart + `passwd root` + successful `ssh -p 2222
root@<vm-ip>` login sequence.

---

## 2. Anonymous FTP upload (weak vsftpd configuration)

**Spec:** `Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise`
**Run:** _pending_

### build-scenario result

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge> forensicforge build-scenario "Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise" --name "ftp anon upload"
Generating a VM for: 'Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/unencrypted_telnet_service.md
    - ansible_tasks/manage_ufw_firewall_rule.md
    - misconfigurations/default_credentials.md
    - misconfigurations/open_firewall_allow_all.md                                                                        Wrot
e run '20260901-165051-ftp anon upload' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-165051-ftp anon upload
                                                                                                      Verifying claimed vulner
abilities (boots + destroys a VM) ...                                                             booted:    True
  booted:    True
  destroyed: True
  [TRUE] `anonymous_enable=YES`: This allows anonymous FTP uploads, which is a known security vulnerability as it can lead to unauthorized file access and data breaches.
         TRUE on the live VM, and Ansible's own output confirms this run's role caused it
  [SKIP] `admin` user with weak password: Using the default username 'admin' and a simple password like 'password123' exposes the system to well-known attacks.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
Building a forensic storyline from what actually verified ...
Intrusion via the FTP service, left open to anonymous access
  Garcia Inc, a small catering company, uses this machine to share files with clients and suppliers over FTP. Amanda Kelley looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise' was found accessed outside normal hours. This run's own generated role deliberately applied the FTP service, left open to anonymous access - specifically, 'anonymous_enable=YES' (task: 'Enable anonymous FTP uploads') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.
Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True
=== Scenario ready ===
Intrusion via the FTP service, left open to anonymous access
Garcia Inc, a small catering company, uses this machine to share files with clients and suppliers over FTP. Amanda Kelley looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server running vsftpd with anonymous FTP upload enabled and a weak default admin password, for a network security exercise' was found accessed outside normal hours. This run's own generated role deliberately applied the FTP service, left open to anonymous access - specifically, 'anonymous_enable=YES' (task: 'Enable anonymous FTP uploads') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.
Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-165051-ftp anon upload\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-165051-ftp anon upload\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.
Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-165051-ftp anon upload\report.json
```

### Manual verification

```powershell
cd "generated\20260901-165051-ftp anon upload"
vagrant up --provider=hyperv
vagrant ssh -c "hostname -I"
vagrant ssh
```

Inside the VM:

```bash
sudo cat /etc/vsftpd.conf | grep -i anonymous
```

From the host (tests it externally):

```powershell
ftp <vm-ip>
```

**Results, run `20260901-165051-ftp anon upload` (recorded 2026-09-02):**

First attempt, straight after boot, failed:

```
PS C:\Users\ricar> ftp 192.168.190.186
Connected to 192.168.190.186.
220 (vsFTPd 3.0.5)
User (192.168.190.186:(none)): anonymous
331 Please specify the password.
Password:
530 Login incorrect.
```

`sudo cat /etc/vsftpd.conf` on the VM confirmed `anonymous_enable=YES`
is genuinely present - matching what `verify-vulnerabilities` already
reported `[TRUE]` and attributed to this run. So the file was right,
but the live server was rejecting anonymous logins anyway. Diagnosed
live rather than accepted at face value:

- `id ftp` -> the `ftp` system account exists (uid 113), with its
  home/anon-root `/srv/ftp` present on disk - ruled out a missing
  account or directory.
- `sudo journalctl -u vsftpd --no-pager | tail -30` showed
  `pam_unix(vsftpd:auth): check pass; user unknown` /
  `authentication failure ... ruser=anonymous` for the rejected
  attempt - vsftpd was routing the login through PAM's normal
  Unix-account authentication instead of its own anonymous short-circuit.
- `cat /etc/pam.d/vsftpd` was the stock file, whose own comment reads
  *"Note: vsftpd handles anonymous logins on its own. Do not enable
  pam_ftp.so."* - confirming the PAM config wasn't the cause; vsftpd
  itself wasn't recognising the login as anonymous.

**Root cause:** this run's generated role (`tasks/main.yml`) writes
`anonymous_enable=YES` via `lineinfile` but never restarts or reloads
`vsftpd` afterward. `apt install vsftpd`'s postinst had already started
the service under the *original* (anonymous-disabled) config before the
lineinfile task ran, so the live daemon kept serving that original
config even after the file on disk was correctly rewritten - the same
"config text changed, but the running service never picked it up"
class of gap already documented for rsyslog in scenario 7, except here
it traces to a genuine, checkable corpus gap rather than a config-file
precedence subtlety: `knowledge/ansible_tasks/restart_sshd_service.md`
and `deploy_sshd_config.md` explicitly teach "restart after editing the
service's config," which is exactly why every SSH scenario in this
evaluation round reliably included that step - but there is no
equivalent instruction for vsftpd, and no vsftpd content in the corpus
at all (confirmed via `grep -ri vsftpd knowledge/` and
`grep -ri anonymous knowledge/`, both effectively empty). The
`disabled_audit_logging.md` doc, similarly, says nothing about
restarting rsyslog - that run's own restart task most likely came from
the model's general knowledge, not the corpus, which is consistent
with it being present in one generation and missing in another for the
structurally identical situation.

**Confirmed fixable at runtime, without touching the file:**

```bash
sudo systemctl restart vsftpd
```

```
PS C:\Users\ricar> ftp 192.168.190.186
Connected to 192.168.190.186.
220 (vsFTPd 3.0.5)
User (192.168.190.186:(none)): ftp
331 Please specify the password.
Password:
230 Login successful.
```

Login succeeded immediately after the restart, with no other change -
proving the vulnerability itself is real and exactly as claimed; the
only gap was the missing restart task in the generated role.

**What this means for the evaluation:** `verify-vulnerabilities`'s
`[TRUE]` + attributed finding for this claim is accurate as far as it
checks (directive text present in the right file, attributed to this
run's own provisioning) - the tool is not wrong. But, exactly as with
scenario 7's rsyslog finding, the claim's implied real-world effect
("this allows anonymous FTP uploads") did not hold at first boot,
because the generated role never restarted the affected service. This
is a genuine, closable corpus gap (no vsftpd content, no generic
"restart after config change" instruction) rather than an inherent
tool limitation - a candidate for the same kind of fix already applied
for the unpatched-package gap (scenario 6): add a knowledge doc
teaching the restart pattern generically or for vsftpd specifically,
rebuild `.chroma/`, and re-verify. Not yet applied - documented here so
the evaluation is honest about what a fresh run currently produces
without it.

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 3. Web application misconfiguration

**Spec:** `Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise`
**Run:** _pending_

### build-scenario result

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge> forensicforge build-scenario "Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise" --name "web app misconfig"
Generating a VM for: 'Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/default_credentials.md
    - misconfigurations/exposed_database_no_auth.md
    - ansible_tasks/manage_ufw_firewall_rule.md
    - ansible_tasks/install_openssh_server.md
  Auto-repaired 2 known issue(s) in the generated output:
    - removed notify: from task 'Create admin panel with default credentials' - no handlers file exists for it to reference, so it always fails the play
    - removed notify: from task 'Enable verbose error pages' - no handlers file exists for it to reference, so it always fails the play
  Wrote run '20260901-175454-web app misconfig' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-175454-web app misconfig
Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [TRUE] `Options Indexes FollowSymLinks` in `/etc/apache2/sites-available/000-default.conf`: This enables directory listing, which is a real vulnerability as it allows attackers to view the contents of directories without proper authorization.
         TRUE on the live VM, and Ansible's own output confirms this run's role caused it
  [SKIP] Default credentials (`<form action="/login" method="post">`) in `/var/www/html/admin.html`: This creates an admin panel with default login credentials (`admin`/`admin`), which is a real vulnerability as it exposes a known weak password.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
Building a forensic storyline from what actually verified ...
Intrusion via the web server, left with an exploitable misconfiguration
  Gonzales-Duncan, a small bakery, uses this machine to host their public-facing website. Michael Snyder MD looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise' was found accessed outside normal hours. This run's own generated role deliberately applied the web server, left with an exploitable misconfiguration - specifically, 'Options Indexes FollowSymLinks' (task: 'Enable directory listing in Apache') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.
Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True
=== Scenario ready ===
Intrusion via the web server, left with an exploitable misconfiguration
Gonzales-Duncan, a small bakery, uses this machine to host their public-facing website. Michael Snyder MD looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu web server running Apache with directory listing enabled, a default-credential admin panel, and verbose error pages exposing stack traces, for a web application security exercise' was found accessed outside normal hours. This run's own generated role deliberately applied the web server, left with an exploitable misconfiguration - specifically, 'Options Indexes FollowSymLinks' (task: 'Enable directory listing in Apache') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.
Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-175454-web app misconfig\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-175454-web app misconfig\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.
Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-175454-web app misconfig\report.json
```


### Manual verification

```powershell
cd generated\<run-id>
vagrant up --provider=hyperv
```

Note the VM's IP, then open it directly in a browser on the host -
`http://<vm-ip>/` - the most screenshot-friendly of the seven:

- Directory listing: browse to a path with no `index.html` and confirm
  Apache lists the directory contents.
- Default-credential admin panel: check `scenario.md`/`generation.md` in
  the run directory for whatever path/credential this generation
  actually claimed (varies per run), then log in with it.
- Verbose error pages: request a path likely to 404/500 and check
  whether the response includes a stack trace or internal path
  disclosure rather than a generic error page.

```powershell
vagrant ssh
```

```bash
sudo apache2ctl -S
sudo cat /etc/apache2/apache2.conf | grep -i indexes
```

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 4. Exposed database (MySQL)

**Spec (original):** `Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise`
**Spec (reworded, attempt 3):** `Ubuntu server running MySQL bound to 0.0.0.0 with a weak MySQL root credential and no firewall restricting external access, for a database security exercise`
**Runs:** `20260901-195711-exposed database`, `20260901-200152-exposed database`, `20260901-202403-exposed database` (attempts 1-3)

### build-scenario result: recorded as a limitation, not a bug

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-182742-exposed database> forensicforge build-scenario "Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise" --name "exposed database"
Generating a VM for: 'Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/exposed_database_no_auth.md
    - misconfigurations/weak_ssh_root_login.md
    - sshd_config/permit_root_login.md
    - misconfigurations/default_credentials.md
  Auto-repaired 4 known issue(s) in the generated output:
    - removed notify: from task 'Set up MySQL without authentication (for training purposes)' - no handlers file exists for it to reference, so it always fails the play
    - removed notify: from task 'Configure MySQL to listen on all interfaces' - no handlers file exists for it to reference, so it always fails the play
    - removed notify: from task 'Disable root login via SSH (for training purposes)' - no handlers file exists for it to reference, so it always fails the play
    - removed notify: from task 'Disable password authentication for SSH (for training purposes)' - no handlers file exists for it to reference, so it always fails the play
  Wrote run '20260901-195711-exposed database' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-195711-exposed database

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    False
  destroyed: False
  [SKIP] `PermitRootLogin yes` (`sshd_config/permit_root_login.md`): This allows direct root login with a password or key, removing the need to compromise a low-privileged account and then escalate.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  [SKIP] `PasswordAuthentication yes` (`misconfigurations/weak_ssh_root_login.md`): Combining this with `PermitRootLogin yes` allows an attacker to brute-force the root account directly over SSH.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  error: no claims matched a checkable task - nothing to boot for

Building a forensic storyline from what actually verified ...
Cannot build a storyline: no verified, attributable vulnerability claim found for this run - cannot build a storyline whose entry vector is actually true. Run `verify-vulnerabilities` first and check its findings.
The generated VM itself is still usable - see `forensicforge test-deploy C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-195711-exposed database`.


(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-182742-exposed database> forensicforge build-scenario "Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise" --name "exposed database"
Generating a VM for: 'Ubuntu server running MySQL bound to 0.0.0.0 with a weak root password and no firewall restricting external access, for a database security exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/exposed_database_no_auth.md
    - misconfigurations/weak_ssh_root_login.md
    - sshd_config/permit_root_login.md
    - misconfigurations/default_credentials.md
  Wrote run '20260901-200152-exposed database' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-200152-exposed database

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    False
  destroyed: False
  [SKIP] `PermitRootLogin yes` from [2] (source: misconfigurations/weak_ssh_root_login.md) – This setting allows an attacker to brute-force the root account directly over SSH, with no need to compromise a lower-privileged user first and escalate.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  [SKIP] `PasswordAuthentication yes` from [2] (source: misconfigurations/weak_ssh_root_login.md) – This setting combines with `PermitRootLogin yes` to allow an attacker to brute-force the root account directly over SSH.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  [SKIP] `bind-address = 0.0.0.0` from [1] (source: misconfigurations/exposed_database_no_auth.md) – Exposing a database service without authentication or proper firewall restrictions allows any network client to read or modify its contents directly, making it vulnerable to data exfiltration.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  [SKIP] `password=weakpassword123` from [4] (source: misconfigurations/default_credentials.md) – Using a weak password is one of the most common initial-access vectors, as default credential lists for almost every common device and application are publicly documented and built into automated scanning and exploitation tools.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  error: no claims matched a checkable task - nothing to boot for

Building a forensic storyline from what actually verified ...
Cannot build a storyline: no verified, attributable vulnerability claim found for this run - cannot build a storyline whose entry vector is actually true. Run `verify-vulnerabilities` first and check its findings.
The generated VM itself is still usable - see `forensicforge test-deploy C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-200152-exposed database`.


(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-182742-exposed database> forensicforge build-scenario "Ubuntu server running MySQL bound to 0.0.0.0 with a weak MySQL root credential and no firewall restricting external access, for a database security exercise" --name "exposed database"
Generating a VM for: 'Ubuntu server running MySQL bound to 0.0.0.0 with a weak MySQL root credential and no firewall restricting external access, for a database security exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/exposed_database_no_auth.md
    - misconfigurations/default_credentials.md
    - sshd_config/permit_root_login.md
    - misconfigurations/weak_ssh_root_login.md
  Wrote run '20260901-202403-exposed database' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-202403-exposed database

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    False
  destroyed: False
  [SKIP] `login_password: 'password123'` - Weak SSH configuration (root login + password auth) from [2]. This allows an attacker to brute-force the root account directly over SSH.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  [SKIP] `host: '%'` - Database service exposed without authentication from [1]. Leaving a MySQL database bound to all network interfaces with authentication disabled or left on default credentials allows any network client to read or modify its contents directly.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task in the generated role writes a line that appears anywhere in this claim's text
  error: no claims matched a checkable task - nothing to boot for

Building a forensic storyline from what actually verified ...
Cannot build a storyline: no verified, attributable vulnerability claim found for this run - cannot build a storyline whose entry vector is actually true. Run `verify-vulnerabilities` first and check its findings.
The generated VM itself is still usable - see `forensicforge test-deploy C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260901-202403-exposed database`.
```


Three attempts, two distinct honest findings - see docs/METHODOLOGY.md
("The database vulnerability class: a real, evidenced limitation, not a
bug to chase") for the full write-up. Summary for the dissertation:

- **Attempts 1-2** (original wording): retrieval deterministically pulled
  in two SSH-focused corpus snippets alongside the two database-focused
  ones (`weak_ssh_root_login.md`, `sshd_config/permit_root_login.md` -
  "root password" sits close to SSH's own root-login content in
  embedding space). Both generations wrote genuinely secure SSH tasks
  (`PermitRootLogin no`, `PasswordAuthentication no`) while their
  "Applied misconfigurations" section claimed the opposite - describing
  the retrieved snippet, not their own actual tasks. `verify-vulnerabilities`
  correctly rejected every claim as `NOT VERIFIABLE` and never booted
  (nothing checkable) - the mechanism working as designed, not failing.
- **Attempt 3** (reworded spec): fixed the SSH-retrieval collision - no
  more contradictory SSH claims - but produced a role using
  `community.mysql.mysql_user` (`login_password: password123`, `host:
  '%'`) instead of `ansible.builtin.lineinfile`. Genuinely weak,
  genuinely self-consistent - but `verify-vulnerabilities` only ever
  checks `lineinfile` tasks (a deliberate week-6 scope decision), so
  nothing here was checkable either, for a structural reason rather than
  a generation problem.

**Decision (with the user): record this as this evaluation round's
answer for the database class**, rather than keep retrying or build a
live-MySQL-connection verification mechanism (real, separately-scoped
future work, not a quick fix). The role from attempt 3
(`20260901-202403-exposed database`) is still real and still usable for
a manual screenshot below - it just never went through the automated
verify/storyline/export chain the other six scenarios did.

### Manual verification (optional - for a screenshot of the real, if unverified-by-the-tool, misconfiguration)

```powershell
cd "generated\20260901-202403-exposed database"
vagrant up --provider=hyperv
```

Note the VM's IP, then from the host (if you have a MySQL client
installed - `mysql --version` to check):

```powershell
mysql -h <vm-ip> -u root -ppassword123
```

(that run's actual `login_password` - check `generation.md` in that run
directory to confirm before using it). Once connected:

```sql
SELECT host, user FROM mysql.user WHERE user = 'root';
```

Should show `host = '%'` - root reachable from any network address, not
just localhost.

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 5. Local privilege escalation (sudoers / SUID)

**Spec:** `Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise`
**Run:** _pending_

### build-scenario result

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge> forensicforge build-scenario "Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise" --name "local privesc"
r: 'Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise' ...                                                                                                             Retrieved 4 corpus snippet(s):
                                                                                                   - misconfigurations/world_writable_permissions.md                                                                                  - ansible_tasks/manage_ufw_firewall_rule.md
    - misconfigurations/weak_ssh_root_login.md
    - ansible_tasks/create_user_with_password.md
  Wrote run '20260902-115130-local privesc' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-115130-local privesc
    - ansible_tasks/create_user_with_password.md
  Wrote run '20260902-115130-local privesc' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-115130-local privesc

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [TRUE] `/etc/sudoers.d/world_writable_entry` is `0666`: This makes the file world-writable, allowing any local user to modify it, which could lead to privilege escalation.
         TRUE on the live VM, and Ansible's output confirms this run's role caused it
  [TRUE] `/usr/local/suid_binary` is set with `04755`: This sets an SUID bit on the binary, allowing a low-privileged user who executes it to run with the permissions of the file owner (root), leading to potential privilege escalation.
         TRUE on the live VM, and Ansible's output confirms this run's role caused it

Building a forensic storyline from what actually verified ...

Intrusion via a privilege-escalation path left open in the system's own permission configuration
  Allen, Duarte and Miller, a small furniture restorer, uses this machine to run their day-to-day office server. Jacqueline Gonzalez looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a privilege-escalation path left open in the system's own permission configuration - specifically, '0666' (task: 'Create a world-writable file in /etc/sudoers.d') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    None
  artefacts_verified: True

=== Scenario ready ===
Intrusion via a privilege-escalation path left open in the system's own permission configuration
Allen, Duarte and Miller, a small furniture restorer, uses this machine to run their day-to-day office server. Jacqueline Gonzalez looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server with a world-writable entry in /etc/sudoers.d and a misconfigured SUID binary, for a privilege escalation exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a privilege-escalation path left open in the system's own permission configuration - specifically, '0666' (task: 'Create a world-writable file in /etc/sudoers.d') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-115130-local privesc\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-115130-local privesc\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.

Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-115130-local privesc\report.json
```


### Manual verification

```powershell
cd generated\<run-id>
vagrant up --provider=hyperv
vagrant ssh
```

Inside the VM, as the plain `vagrant` user (not root):

```bash
ls -la /etc/sudoers.d/
sudo -l
find / -perm -4000 -type f 2>/dev/null
```

Check that run's `roles/training_vm/tasks/main.yml` (on the host, before
or after this) for exactly which sudoers entry / SUID binary this
generation actually created, then attempt to use it as a low-privileged
user would to escalate - the specific exploitation step depends on what
was actually generated, so read the task before deciding how to test it.

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 6. Unpatched OpenSSL

**Spec:** `Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise`
**Runs (gap, attempts 1-2):** `20260902-121218-unpatched openssl`, `20260902-121737-unpatched openssl`
**Corpus fix:** added `knowledge/ansible_tasks/pin_outdated_package.md`, re-tested 3x (`generate`-only, no boot needed to confirm content quality) - see docs/METHODOLOGY.md ("The unpatched-OpenSSL class: a genuine corpus gap, confirmed twice - then closed") for the full arc.
**Run (post-fix, ready for a live `build-scenario`):** _pending - retry the command below_

### Result: a genuine corpus gap, found, confirmed twice, and closed - not a bug

Both attempts (raw output below) produced the **identical** generic
role - `Install OpenSSH server` / `Ensure sshd is enabled and running`,
nothing about packages, versions, or updates - while the "Applied
misconfigurations" section described tasks that were never actually
written. Attempt 2's claim text was unusually candid about it: it named
`` `name: openssl` (not shown in the snippet) `` - the model citing a
parameter value that appears nowhere in its own generated YAML.

See docs/METHODOLOGY.md ("The unpatched-OpenSSL class: a genuine corpus
gap, confirmed twice") for the full diagnosis - in short:
`knowledge/misconfigurations/unpatched_outdated_packages.md` is the only
misconfiguration doc in the corpus with no paired directive-reference
doc and no obvious single Ansible module to express it with, so the LLM
had nothing concrete to imitate and fell back to paraphrasing the
concept as if it had been applied. Tried twice, deliberately, before
concluding this - both attempts failed identically, which is itself the
evidence this is structural (a corpus-content gap) rather than one bad
roll a third retry would likely fix.

### build-scenario result (both attempts, raw)

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge> forensicforge build-scenario "Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise" --name "unpatched openssl"
Generating a VM for: 'Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/unpatched_outdated_packages.md
    - ansible_tasks/pin_outdated_package.md
    - misconfigurations/exposed_database_no_auth.md
    - ansible_tasks/install_openssh_server.md
  Wrote run '20260902-125357-unpatched openssl' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-125357-unpatched openssl

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [SKIP] `selection: hold` in the `dpkg_selections` task for `openssl`: This keeps the OpenSSL package at its current version without updating it, exposing the system to known vulnerabilities.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task writes a line, and no ansible.builtin.file/copy task sets a mode:, that appears anywhere in this claim's text
  [TRUE] `` `APT::Periodic::Unattended-Upgrade "0";` `` in the `lineinfile` task for `/etc/apt/apt.conf.d/20auto-upgrades`: This disables automatic security updates, making the server vulnerable to newly discovered exploits.
         TRUE on the live VM, and Ansible's output confirms this run's role caused it

Building a forensic storyline from what actually verified ...

Intrusion via a misconfiguration this run's own generation claimed to apply
  Holden, Lara and Mosley, a small veterinary clinic, uses this machine to run their day-to-day office server. Joseph Gomez looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a misconfiguration this run's own generation claimed to apply - specifically, 'APT::Periodic::Unattended-Upgrade "0";' (task: 'Disable automatic security updates') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True

=== Scenario ready ===
Intrusion via a misconfiguration this run's own generation claimed to apply
Holden, Lara and Mosley, a small veterinary clinic, uses this machine to run their day-to-day office server. Joseph Gomez looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server intentionally left with an outdated, unpatched OpenSSL version and automatic security updates disabled, for a vulnerability-scanning exercise' was found accessed outside normal hours. This run's own generated role deliberately applied a misconfiguration this run's own generation claimed to apply - specifically, 'APT::Periodic::Unattended-Upgrade "0";' (task: 'Disable automatic security updates') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-125357-unpatched openssl\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-125357-unpatched openssl\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.

Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-125357-unpatched openssl\report.json
```
Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [SKIP] `selection: hold` in the `dpkg_selections` task for `openssl` - outside current verification scope (module coverage, not corpus content - see above)
  [TRUE] `APT::Periodic::Unattended-Upgrade "0";` in the `lineinfile` task - TRUE on the live VM, and Ansible's output confirms this run's role caused it

Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True
Portable VM image: generated/20260902-125357-unpatched openssl/image.vmdk
```

Confirms the corpus fix under a real boot, not just `provision`-only
content checks. One cosmetic issue found on this same run: the
storyline's entry-vector description fell back to the generic
"a misconfiguration this run's own generation claimed to apply" instead
of the intended "apt"/outdated-package category, added earlier this
week - a real regex bug (the category pattern required the *plural*
"unattended.?upgrades", but the real Ansible/apt directive is singular,
`Unattended-Upgrade`). Fixed (`unattended.?upgrades?`) - see
docs/METHODOLOGY.md for the regression test. The underlying
claimed-vs-verified-vs-attributed data on this run is entirely
unaffected (only the narrative's wording was wrong); a re-run isn't
required to trust the result, only to get the corrected narrative text
for a screenshot.

### Manual verification

```powershell
cd generated\<run-id>
vagrant up --provider=hyperv
vagrant ssh
```

Inside the VM:

```bash
cat /etc/apt/apt.conf.d/20auto-upgrades
dpkg --get-selections | grep openssl
```

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 7. Disabled logging / auditd (log tampering)

**Spec:** `Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering`
**Run:** `20260902-151517-disabled logging` - complete success (booted, config_verified, artefacts_verified, image exported). An earlier attempt (`20260902-124539-disabled logging`) hit transient Ubuntu-mirror flakiness on its final boot; this is the clean re-run, done after adding the apt retry-loop resilience (see docs/METHODOLOGY.md), and it completed end-to-end on the first try.

### build-scenario result

```powershell
(.venv) PS C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge> forensicforge build-scenario "Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering" --name "disabled logging"
Generating a VM for: 'Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering' ...
  Retrieved 4 corpus snippet(s):
    - misconfigurations/disabled_audit_logging.md
    - misconfigurations/exposed_database_no_auth.md
    - sshd_config/login_grace_time.md
    - misconfigurations/unencrypted_telnet_service.md
  Wrote run '20260902-151517-disabled logging' to: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-151517-disabled logging

Verifying claimed vulnerabilities (boots + destroys a VM) ...
  booted:    True
  destroyed: True
  [SKIP] `auditd` is disabled (`service auditd state: stopped enabled: no`) - from [1]. This allows an attacker to bypass initial access logging, which is crucial for forensic analysis.
         NOT VERIFIABLE - no ansible.builtin.lineinfile task writes a line, and no ansible.builtin.file/copy task sets a mode:, that appears anywhere in this claim's text
  [TRUE] Authentication logs are discarded in `/etc/rsyslog.conf` (`lineinfile path: /etc/rsyslog.conf regexp: '^auth,authpriv.*' line: 'auth,authpriv.none;*.none' state: present`) - from [1]. This removes the ability to detect and investigate unauthorized access attempts, which is essential for forensic training.
         TRUE on the live VM, and Ansible's output confirms this run's role caused it

Building a forensic storyline from what actually verified ...

Intrusion via the system's own audit logging, left disabled or misdirected
  Franco, Barnes and Garcia, a small bicycle repair shop, uses this machine to run their day-to-day office server. Travis Blackwell looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering' was found accessed outside normal hours. This run's own generated role deliberately applied the system's own audit logging, left disabled or misdirected - specifically, 'auth,authpriv.none;*.none' (task: 'Configure rsyslog to discard authentication logs') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Final boot: verifying config + planted evidence, then exporting a portable image ...
  booted:             True
  config_verified:    True
  artefacts_verified: True

=== Scenario ready ===
Intrusion via the system's own audit logging, left disabled or misdirected
Franco, Barnes and Garcia, a small bicycle repair shop, uses this machine to run their day-to-day office server. Travis Blackwell looks after IT part-time, alongside their regular role. A training VM provisioned for 'Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering' was found accessed outside normal hours. This run's own generated role deliberately applied the system's own audit logging, left disabled or misdirected - specifically, 'auth,authpriv.none;*.none' (task: 'Configure rsyslog to discard authentication logs') - verified live against the booted VM and confirmed by Ansible's own output to have been caused by this run's provisioning, not a pre-existing default. Investigators believe this is how the intrusion occurred, and are looking for evidence of what happened afterward.

Scenario summary: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-151517-disabled logging\scenario.md
Portable VM image: C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-151517-disabled logging\image.vmdk
Import the .vmdk into VirtualBox/VMware as a new VM's disk to use it.

Wrote C:\Users\ricar\Documents\Programming\PythonProjects\ForensicForge\generated\20260902-151517-disabled logging\report.json
```

Verification and storyline generation both succeeded correctly (1 of 2
claims genuinely true and attributed, the other correctly rejected as
not a real directive, matching how the `auditd disabled` claim is
handled everywhere else in this evaluation - see the note on manual
verification below). The final boot - config+artefacts verification
plus image export - completed cleanly this time, with the apt
retry-loop resilience in place (added after this exact class of
transient Ubuntu-mirror failure had already cost two earlier runs a
full live boot; see docs/METHODOLOGY.md). No retry was needed.

### Manual verification

```powershell
cd "generated\20260902-151517-disabled logging"
vagrant up --provider=hyperv
vagrant ssh
```

Inside the VM:

```bash
sudo systemctl status auditd
sudo cat /etc/rsyslog.conf | grep -i authpriv
```

Then trigger something that should normally be logged, and confirm it
isn't:

```bash
sudo -k
sudo whoami   # will prompt for a password - get it wrong once
sudo cat /var/log/auth.log | tail -20   # check whether the failed attempt shows up
```

```powershell
vagrant destroy -f
```

**Note on the command above (corrected after the run):** the version
originally written here checked `/etc/rsyslog.d/50-default.conf`,
which was a generic guess made before this specific run's generated
role was known. This run's actual task (`tasks/main.yml`) modifies
`/etc/rsyslog.conf` directly, so that's the file the manual command
now checks - matching exactly what `verify-vulnerabilities` itself
already confirmed automatically (line present, attributed to this
run's provisioning).

**Results, run `20260902-151517-disabled logging` (recorded 2026-09-02):**

```
vagrant@forensicforge-20260902-151517:~$ sudo systemctl status auditd
● auditd.service - Security Auditing Service
     Loaded: loaded (/lib/systemd/system/auditd.service; disabled; vendor preset: enabled)
     Active: inactive (dead) since Wed 2026-09-02 16:21:42 UTC; 12min ago
...
vagrant@forensicforge-20260902-151517:~$ sudo cat /etc/rsyslog.conf | grep -i authpriv
auth,authpriv.none;*.none
vagrant@forensicforge-20260902-151517:~$ sudo -k
vagrant@forensicforge-20260902-151517:~$ sudo whoami
root
vagrant@forensicforge-20260902-151517:~$ sudo cat /var/log/auth.log | tail -20
Sep  2 16:21:41 ubuntu2004 sudo:  vagrant : ... COMMAND=... AnsiballZ_apt.py
Sep  2 16:21:41 ubuntu2004 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
Sep  2 16:21:41 ubuntu2004 sudo: pam_unix(sudo:session): session closed for user root
Sep  2 16:21:42 ubuntu2004 sudo:  vagrant : ... COMMAND=... AnsiballZ_systemd.py
Sep  2 16:21:42 ubuntu2004 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
Sep  2 16:21:42 ubuntu2004 sudo: pam_unix(sudo:session): session closed for user root
Sep  2 16:21:42 ubuntu2004 sudo:  vagrant : ... COMMAND=... AnsiballZ_lineinfile.py
Sep  2 16:21:42 ubuntu2004 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
Sep  2 16:21:42 ubuntu2004 sudo: pam_unix(sudo:session): session closed for user root
Sep  2 16:21:42 ubuntu2004 sudo:  vagrant : ... COMMAND=... AnsiballZ_systemd.py
Sep  2 16:21:42 ubuntu2004 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
Sep  2 16:21:42 forensicforge-20260902-151517 sudo: pam_unix(sudo:session): session closed for user root
Sep  2 16:21:42 forensicforge-20260902-151517 sudo:  vagrant : ... COMMAND=... AnsiballZ_file.py
Sep  2 16:21:42 forensicforge-20260902-151517 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
Sep  2 16:21:42 forensicforge-20260902-151517 sudo: pam_unix(sudo:session): session closed for user root
Sep  2 16:21:43 forensicforge-20260902-151517 sudo:  vagrant : ... COMMAND=... AnsiballZ_blockinfile.py
Sep  2 16:21:43 forensicforge-20260902-151517 sudo: pam_unix(sudo:session): session opened for user root by (uid=0)
# BEGIN forensicforge:/var/log/auth.log
Aug 15 02:30:00 db-03 auditd[7010]: session opened for user manuel14 from 172.21.172.103
# END forensicforge:/var/log/auth.log
```

- `sudo systemctl status auditd` -> `Active: inactive (dead)`, `disabled`.
  Manually confirms the one claim `verify-vulnerabilities` marks
  `NOT VERIFIABLE` (a `service` module state, outside the tool's
  lineinfile/mode scope) - true in practice on the live VM.
- `/etc/rsyslog.conf` contains the exact discard line the tool already
  verified (`auth,authpriv.none;*.none`), attributed to this run.
- `sudo -k` / `sudo whoami` returned `root` immediately with no
  password prompt - this Vagrant box has passwordless sudo for the
  `vagrant` user, so the intended "get it wrong once, see if the
  failure shows up" test didn't produce a failed attempt to check for.
- The planted forensic artefact (the fake `auditd` session-opened entry
  for the fictional intrusion, dated 2026-08-15) is present and intact
  at the end of the file - independently corroborates
  `artefacts_verified: True` from the automated report.
- The file *still contains* real sudo/PAM session log lines from this
  run's own Ansible provisioning, and the module-name sequence in the
  transcript pins down exactly when relative to the discard rule taking
  effect: matching this run's `tasks/main.yml` order (`apt` -> `systemd`
  [disable auditd] -> `lineinfile` [write the discard rule] -> `systemd`
  [**restart rsyslog** - the role's last task] -> `file` and
  `blockinfile` [the separate forensic-artefacts role planting the fake
  entry]), the `file` and `blockinfile` tasks both ran as root *after*
  rsyslog had already restarted with the new rule active, and both
  still produced a `pam_unix(sudo:session): session opened/closed` line
  in `/var/log/auth.log`. This isn't circumstantial - it's a direct
  before/after boundary in the same transcript: the discard rule was
  live, rsyslog had reloaded it, and auth logging continued anyway. The
  most likely cause is that `/etc/rsyslog.d/50-default.conf` still
  carries Ubuntu's own, untouched `auth,authpriv.*` selector routing to
  `/var/log/auth.log` (confirmed unmodified separately). Traditional
  rsyslog selector lines are independent, non-exclusive rules - each
  matching line's action fires regardless of what other lines targeting
  the same facility do elsewhere in the config - so a `.none` exclusion
  added in one file does not by itself suppress a separate, still-active
  `auth,authpriv.*` rule in another file.

**What this means for the evaluation:** `verify-vulnerabilities`
checks a narrower, well-defined proposition - "does the exact
directive text this run's role applied appear in the file it claims,
attributed to this run's own provisioning" - and that proposition is
genuinely true here; the tool is not wrong. But the claim's own prose
("Authentication logs are discarded") implies a real-world *effect*
that this manual check confirms does *not* fully hold, because a
second, untouched rsyslog config file keeps routing the same facility
to the same log even after the change is applied and reloaded. That's
a real, evidenced gap between "the LLM's claimed misconfiguration was
applied as literal text" and "the misconfiguration achieves its
described effect" - worth stating plainly in the dissertation as a
limitation of directive-text verification, distinct from the
`auditd`-scope limitation already documented elsewhere. It does not
change any of `verify-vulnerabilities`'s TRUE/attributed findings for
this run, which are accurate as far as they go.

**Screenshot(s):** _pending_

---

## Consolidated summary

_Filled in once all seven scenarios above are complete - see
`docs/METHODOLOGY.md`'s evaluation-round section for the version that
gets carried into the dissertation._
