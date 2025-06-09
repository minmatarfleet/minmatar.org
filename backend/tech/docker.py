import docker
from datetime import datetime, timedelta
from typing import List
from operator import attrgetter


def docker_client():
    return docker.DockerClient(base_url="unix://var/run/docker.sock")


def container_names():
    return [
        container.name
        for container in docker_client().containers.list(all=True, limit=50)
    ]


class DockerLogQuery:
    """A query for content in Docker logs"""

    container_names: str
    search_for: str | None
    exclude: List[str]
    start_time: datetime
    end_time: datetime
    abort_time: datetime
    include_ended: bool | None

    def __init__(self, containers, start_time, end_time, search_for=None):
        self.container_names = containers
        self.start_time = start_time
        self.end_time = end_time
        self.search_for = search_for
        self.exclude = []
        self.abort_time = None

    def abort_after(self, delta: timedelta):
        self.abort_time = datetime.now() + delta

    def aborted(self) -> bool:
        if not self.abort_time:
            return False
        if datetime.now() >= self.abort_time:
            return True
        return False


class DockerLogEntry:
    """An entry from Docker container logs."""

    container: str
    timestamp: str
    text: str

    def __init__(self, container: str, timestamp: str, text: str):
        self.container = container
        self.timestamp = timestamp
        self.text = text

    def __str__(self):
        return f"{self.container:<20} {self.text}"


def sort_chronologically(logs: List[DockerLogEntry]):
    logs.sort(key=attrgetter("timestamp"))


def parse_docker_logs(
    container_name: str, log_text: str, query: DockerLogQuery = None
) -> List[DockerLogEntry]:
    entries = []
    for line in log_text.splitlines():
        line = line.strip()
        if len(line) == 0:
            continue
        if query and query.search_for:
            if not query.search_for.upper() in line.upper():
                continue
        entries.append(DockerLogEntry(container_name, line[0:30], line[31:]))
        if query and query.aborted():
            break
    return entries


class DockerContainer:
    """A connection to a Docker container"""

    def __init__(self, container_name: str = None):
        self.container_name = container_name
        self.client = docker_client()
        self.container = self.client.containers.get(self.container_name)

    def logs(self, query: DockerLogQuery) -> str:
        raw_content = self.container.logs(
            since=query.start_time,
            until=query.end_time,
            timestamps=True,
        )
        decoded = raw_content.decode("utf-8")
        return f"{decoded}"  # f-string to handle newlines

    def log_entries(self, query: DockerLogQuery) -> List[DockerLogEntry]:
        log_text = self.logs(query)
        return parse_docker_logs(self.container_name, log_text, query)
