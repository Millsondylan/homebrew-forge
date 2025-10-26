class Forge < Formula
  include Language::Python::Virtualenv

  desc "AgentForge CLI: spawn/manage 500+ Anthropic agents with queue and scheduler"
  homepage "https://github.com/Millsondylan/forge"
  url "https://github.com/Millsondylan/forge/archive/refs/heads/main.tar.gz"
  sha256 :no_check
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
