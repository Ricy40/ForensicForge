from forensicforge.imaging import image_export


def test_export_scenario_image_deletes_the_intermediate_vhdx_after_conversion(tmp_path, monkeypatch):
    """Regression test: keeping both the exported VHDX and the converted
    VMDK meant ~17GB per run (confirmed against a real one: ~11GB VHDX +
    ~6GB VMDK) - a real, avoidable disk-space problem for anyone running
    more than a couple of scenarios back to back. The VHDX must be
    deleted once the VMDK it was converted into exists, not kept."""
    vhdx_path = tmp_path / "image.vhdx"
    vhdx_path.write_bytes(b"fake vhdx content")
    vmdk_path = tmp_path / "image.vmdk"

    monkeypatch.setattr(image_export, "export_vhdx", lambda vm_name, run_dir: vhdx_path)

    def fake_convert(path):
        vmdk_path.write_bytes(b"fake vmdk content")
        return vmdk_path

    monkeypatch.setattr(image_export, "convert_to_vmdk", fake_convert)

    result = image_export.export_scenario_image(tmp_path, "some-vm")

    assert result == vmdk_path
    assert vmdk_path.exists()
    assert not vhdx_path.exists()


def test_export_scenario_image_keeps_the_vhdx_if_conversion_fails(tmp_path, monkeypatch):
    """If qemu-img fails, the VHDX is the only copy of the disk at that
    point - it must not be deleted."""
    vhdx_path = tmp_path / "image.vhdx"
    vhdx_path.write_bytes(b"fake vhdx content")

    monkeypatch.setattr(image_export, "export_vhdx", lambda vm_name, run_dir: vhdx_path)

    def failing_convert(path):
        raise image_export.ImageExportError("qemu-img failed")

    monkeypatch.setattr(image_export, "convert_to_vmdk", failing_convert)

    try:
        image_export.export_scenario_image(tmp_path, "some-vm")
        assert False, "expected ImageExportError"
    except image_export.ImageExportError:
        pass

    assert vhdx_path.exists()
