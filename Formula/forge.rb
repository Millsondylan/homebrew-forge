class Forge < Formula
  include Language::Python::Virtualenv

  desc "AgentForge CLI: spawn/manage 500+ Anthropic agents with queue and scheduler"
  homepage "https://github.com/Millsondylan/forge"
  url "https://github.com/Millsondylan/homebrew-forge/releases/download/v0.2.0/agentforge-cli-0.2.0.tar.gz"
  sha256 "cefff913e30d8b3adb07e56c2b9828643d8692545e39cd209b9ebf5dc97231f9"
  version "0.2.0"

  depends_on "python@3.11"

  resource "click" do
    url "https://files.pythonhosted.org/packages/46/61/de6cd827efad202d7057d93e0fed9294b96952e188f7384832791c7b2254/click-8.3.0.tar.gz"
    sha256 "e7b8232224eba16f4ebe410c25ced9f7875cb5f3263ffc93cc3e8da705e229c4"
  end

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/05/8e/961c0007c59b8dd7729d542c61a4d537767a59645b82a0b521206e1e25c2/pyyaml-6.0.3.tar.gz"
    sha256 "d76623373421df22fb4cf8817020cbb7ef15c725b9d5e45f17e189bfc384190f"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    ENV["HOME"] = testpath
    system "#{bin}/forge", "init"
    system "#{bin}/forge", "queue", "add", "smoke test task"
    output = shell_output("#{bin}/forge queue list")
    assert_match "smoke test task", output
  end
end
