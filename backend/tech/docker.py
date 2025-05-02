import docker
from datetime import datetime


def docker_client():
    return docker.DockerClient(base_url="unix://var/run/docker.sock")


def docker_containers():
    return docker_client().containers.list()


class DockerContainer:
    """A connection to a Docker container"""

    def __init__(self, container_name: str = None):
        self.container_name = container_name
        self.client = docker_client()
        self.container = self.client.containers.get(self.container_name)

    def logs(self, start_time: datetime, end_time: datetime) -> str:
        raw_content = self.container.logs(
            since=start_time,
            until=end_time,
            timestamps=True,
        )
        decoded = raw_content.decode("utf-8")
        return f"{decoded}"  # f-string to handle newlines
