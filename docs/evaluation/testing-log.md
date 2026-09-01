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
**Run:** _pending_

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
cd generated\<run-id>
vagrant up --provider=hyperv
```

Note the IP Vagrant prints during boot (`==> default: Waiting for the
machine to report its IP address... IP: x.x.x.x`) - useful for testing
from the host directly.

```powershell
vagrant ssh
```

Inside the VM:

```bash
sudo cat /etc/ssh/sshd_config | grep -E 'Port|PermitRootLogin|PasswordAuthentication|X11Forwarding'
```

From the host, in a second terminal (tests the weak config as an
external attacker would - a real screenshot-worthy moment):

```powershell
ssh -p 2222 root@<vm-ip>
```

It should prompt for a password rather than refusing outright - confirms
`PermitRootLogin yes` + `PasswordAuthentication yes` are both live.

Clean up:

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

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
cd generated\<run-id>
vagrant up --provider=hyperv
```

Note the VM's IP from the boot output, then:

```powershell
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

Log in with username `anonymous` and any password (e.g. your email) -
should succeed and let you `ls`/`put` a file, confirming anonymous
upload is genuinely open. Check `generation.md` or `scenario.md` in the
run directory for whatever admin credential this specific generation
claimed to weaken, if you also want to test that claim directly.

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

_pending_

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
**Run:** _pending_

### build-scenario result

_pending_

### Manual verification

```powershell
cd generated\<run-id>
vagrant up --provider=hyperv
vagrant ssh
```

Inside the VM:

```bash
openssl version -a
apt list --installed 2>/dev/null | grep -i openssl
cat /etc/apt/apt.conf.d/20auto-upgrades
systemctl status unattended-upgrades 2>&1 | head -5
```

```powershell
vagrant destroy -f
```

**Screenshot(s):** _pending_

---

## 7. Disabled logging / auditd (log tampering)

**Spec:** `Ubuntu server with auditd disabled and rsyslog configured to discard authentication logs, for a digital forensics exercise investigating log tampering`
**Run:** _pending_

### build-scenario result

_pending_

### Manual verification

```powershell
cd generated\<run-id>
vagrant up --provider=hyperv
vagrant ssh
```

Inside the VM:

```bash
sudo systemctl status auditd
sudo cat /etc/rsyslog.d/50-default.conf | grep -i authpriv
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

**Screenshot(s):** _pending_

---

## Consolidated summary

_Filled in once all seven scenarios above are complete - see
`docs/METHODOLOGY.md`'s evaluation-round section for the version that
gets carried into the dissertation._
