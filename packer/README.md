# Packer base image (built, not yet wired in)

`ubuntu-base.pkr.hcl` builds a minimal Ubuntu 20.04 Server box via
VirtualBox + cloud-init autoinstall, and outputs it as a `.box` file via
the `vagrant` post-processor - the same box format `vagrant box add` and
a Vagrantfile's `config.vm.box` consume.

**Status:** this template has not been run yet and is not what the
generated Vagrantfiles currently boot from - see the "Packer vs. stock
box" section of [`../docs/METHODOLOGY.md`](../docs/METHODOLOGY.md) for
why. Treat it as a starting point, not a verified-working build.

Before running `packer build ubuntu-base.pkr.hcl`:

- A Packer 1.16.0 binary is available at
  `../packer_1.16.0_windows_amd64/packer.exe` (not on PATH - call it by
  path, or add that directory to PATH). Its plugins are not installed yet:
  `packer plugins install github.com/hashicorp/virtualbox` and
  `github.com/hashicorp/vagrant`.
- Double check `iso_url` still points at a live Ubuntu 20.04 point release -
  old point releases get pulled from the mirrors periodically.
- The autoinstall password hash in `http/user-data` is a real, verified
  SHA-512 hash of the literal string `vagrant` (generated with
  `openssl passwd -6`), matching the `vagrant`/`vagrant` convention every
  stock Vagrant box uses. It is not a real secret; regenerate it if you
  want a different placeholder password.

Once built, register and use it with:

```bash
vagrant box add forensicforge/ubuntu-base packer/builds/forensicforge-ubuntu-base.box
```

then point a generated Vagrantfile's `config.vm.box` at
`forensicforge/ubuntu-base` instead of the stock box.
