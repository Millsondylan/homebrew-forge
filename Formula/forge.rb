class Forge < Formula
  include Language::Python::Virtualenv

  desc "AgentForge CLI with automated planning and session management"
  homepage "https://github.com/Millsondylan/forge"
  url "https://github.com/Millsondylan/homebrew-forge/releases/download/v0.4.0/agentforge_cli-0.4.0.tar.gz"
  sha256 "9da85e4ebf9743075d066f2c5af0b04aa628fb61eb1532edd506b9bf00413923"
  version "0.4.0"

  depends_on "python@3.11"

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.8.tar.gz"
    sha256 "ed53c9d8990d83c2a27deae68e4ee337473f6330c040a31d4225c9574d16096a"
  end

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/cd/e5/af35f7ea75cf72f2cd079c95ee16797de7cd71f29ea7c68ae5ce7be1eda0/PyYAML-6.0.1.tar.gz"
    sha256 "bfdf460b1736c775f2ba9f6a92bca30bc2095067b8a9d77876d1fad6cc3b4a43"
  end

  resource "keyring" do
    url "https://files.pythonhosted.org/packages/source/k/keyring/keyring-25.6.0.tar.gz"
    sha256 "0b39998aa941431eb3d9b0d4b2460bc773b9df6fed7621c2dfb291a7e0187a66"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.32.3.tar.gz"
    sha256 "55365417734eb18255590a9ff9eb97e9e1da868d4ccd6402399eaf68af20a760"
  end

  resource "croniter" do
    url "https://files.pythonhosted.org/packages/source/c/croniter/croniter-6.0.0.tar.gz"
    sha256 "37c504b313956114a983ece2c2b07790b1f1094fe9d81cc94739214748255577"
  end

  resource "cffi" do
    url "https://files.pythonhosted.org/packages/source/c/cffi/cffi-1.17.1.tar.gz"
    sha256 "1c39c6016c32bc48dd54561950ebd6836e1670f2ae46128f67cf49e789c52824"
  end

  resource "pycparser" do
    url "https://files.pythonhosted.org/packages/source/p/pycparser/pycparser-2.22.tar.gz"
    sha256 "491c8be9c040f5390f5bf44a5b07752bd07f56edf992381b05c701439eec10f6"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/63/09/c1bc53dab74b1816a00d8d030de5bf98f724c52c1635e07681d312f20be8/charset-normalizer-3.3.2.tar.gz"
    sha256 "f30c3cb33b24454a82faecaf01b19c18562b1e89558fb6c56de4d9118a032fd5"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/source/i/idna/idna-3.7.tar.gz"
    sha256 "028ff3aadf0609c1fd278d8ea3089299412a7a8b9bd005dd08b9f8285bcb5cfc"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/source/u/urllib3/urllib3-2.2.2.tar.gz"
    sha256 "dd505485549a7a552833da5e6063639d0d177c04f23bc3864e41e5dc5f612168"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/source/c/certifi/certifi-2025.10.5.tar.gz"
    sha256 "47c09d31ccf2acf0be3f701ea53595ee7e0b8fa08801c6624be771df09ae7b43"
  end

  resource "python-dateutil" do
    url "https://files.pythonhosted.org/packages/source/p/python-dateutil/python-dateutil-2.9.0.post0.tar.gz"
    sha256 "37dd54208da7e1cd875388217d5e00ebd4179249f90fb72437e91a35459a0ad3"
  end

  resource "six" do
    url "https://files.pythonhosted.org/packages/source/s/six/six-1.16.0.tar.gz"
    sha256 "1e61c37477a1626458e36f7b1d82aa5c9b094fa4802892072e49de9c60c4c926"
  end

  resource "pytz" do
    url "https://files.pythonhosted.org/packages/source/p/pytz/pytz-2025.2.tar.gz"
    sha256 "360b9e3dbb49a209c21ad61809c7fb453643e048b38924c765813546746e81c3"
  end


  def install
    # Install all resources except cryptography using standard method
    virtualenv_install_with_resources

    # Install cryptography separately allowing binary wheel (avoids Rust requirement)
    system libexec/"bin/python", "-m", "pip", "install", "cryptography>=43.0.1"
  end

  test do
    ENV["HOME"] = testpath
    system "#{bin}/forge", "init"
    system "#{bin}/forge", "queue", "add", "smoke test task"
    output = shell_output("#{bin}/forge queue list")
    assert_match "smoke test task", output
  end
end
