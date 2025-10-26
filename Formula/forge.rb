class Forge < Formula
  include Language::Python::Virtualenv

  desc "AgentForge CLI: spawn/manage 500+ Anthropic agents with queue and scheduler"
  homepage "https://github.com/Millsondylan/forge"
  url "https://github.com/Millsondylan/forge/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "d129fbda9a8ef3abbc60cc5c0bd55aa5bde1e33b596acfe5610dfdf2bc838d0b"
  version "0.1.0"

  depends_on "python@3.11"

  def install
    venv = virtualenv_create(libexec, "python3.11")
    venv.pip_install buildpath
    (bin/"forge").write_env_script(libexec/"bin/forge", {})
  end

  test do
    assert_match "Forge CLI", shell_output("#{bin}/forge --help")
  end
end
