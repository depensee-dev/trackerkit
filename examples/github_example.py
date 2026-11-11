import asyncio
import os

from _env import load_env

from trackerkit import GitHubAuthConfig, TaskQuery, TrackerClient, TrackerClientError


async def main() -> None:
    """Read repositories, issues, and relations without modifying GitHub data."""

    load_env()
    token = os.getenv("GITHUB_TOKEN", "")
    repository_name = os.getenv("GITHUB_REPOSITORY", "")
    if not token or token == "your-github-token":
        raise SystemExit("Set GITHUB_TOKEN in trackerkit/.env before running the example.")
    if not repository_name or repository_name == "owner/repository":
        raise SystemExit(
            "Set GITHUB_REPOSITORY=owner/repository in trackerkit/.env. The example is read-only."
        )

    auth_config = GitHubAuthConfig(
        access_token=token,
        base_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
        api_version=os.getenv("GITHUB_API_VERSION", "2026-03-10"),
    )
    async with TrackerClient(
        provider="github",
        auth_data=auth_config.model_dump(),
        connection_timeout=10,
    ) as client:
        await client.ensure_connection()
        print("github: connected")

        workspaces = await client.list_workspaces()
        print(f"github: workspaces: {[workspace.key for workspace in workspaces]}")
        projects = await client.list_projects()
        project = next(
            (
                item
                for item in projects
                if item.key and item.key.casefold() == repository_name.casefold()
            ),
            None,
        )
        if project is None:
            raise SystemExit(
                f"Repository {repository_name!r} is not visible to the configured token."
            )
        print(f"github: repository: {project.key} (id={project.id})")
        print(f"github: issue count: {await client.count_tasks(TaskQuery(project_id=project.id))}")

        tasks = await client.list_tasks(TaskQuery(project_id=project.id))
        print(f"github: loaded {len(tasks)} issues")
        for task in tasks:
            fetched = await client.get_task(task.id)
            assert fetched.id == task.id
            status = task.status.id if task.status else "unknown"
            print(f"- {task.key}: {task.title} [{status}]")
            relations = await client.list_relations(task.id)
            for relation in relations:
                print(
                    f"  {relation.relation_type.value}: "
                    f"{relation.source_task_id} -> {relation.target_task_id}"
                )
            print(f"  relations: {len(relations)}")
        print("github: read-only validation done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TrackerClientError as error:
        print(error)
