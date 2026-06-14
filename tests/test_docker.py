import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(shutil.which("docker") is None, reason="docker is not available")


def test_docker_compose_config_is_valid():
    result = subprocess.run(["docker", "compose", "config", "--quiet"], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_docker_compose_defines_bot_and_db_services():
    result = subprocess.run(["docker", "compose", "config", "--services"], capture_output=True, text=True, check=True)

    services = result.stdout.split()

    assert "bot" in services
    assert "db" in services
