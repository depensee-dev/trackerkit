import asyncio
import os
from datetime import UTC, datetime

from _base import wait_for_enter
from _env import load_env

from trackerkit import (
    CreateRelationInput,
    CreateTaskInput,
    GitHubAuthConfig,
    RelationType,
    TaskPriority,
    TaskQuery,
    TaskState,
    TaskWorkType,
    TrackerClient,
    TrackerClientError,
    UpdateTaskInput,
)


async def main() -> None:
    """Run the GitHub example flow with explicit auth config."""

    load_env()
    token = os.getenv("GITHUB_TOKEN", "")
    repository_name = os.getenv("GITHUB_REPOSITORY", "")
    if not token or token == "your-github-token":
        raise SystemExit("Set GITHUB_TOKEN in trackerkit/.env before running the example.")
    if not repository_name or repository_name == "owner/repository":
        raise SystemExit("Set GITHUB_REPOSITORY=owner/repository in trackerkit/.env.")

    # Auth config makes the expected parameters explicit for the example.
    auth_config = GitHubAuthConfig(
        access_token=token,
        base_url=os.getenv("GITHUB_API_URL", "https://api.github.com"),
        api_version=os.getenv("GITHUB_API_VERSION", "2026-03-10"),
    )

    client = TrackerClient(
        provider="github",
        auth_data=auth_config.model_dump(exclude_none=True),
        connection_timeout=20,
    )

    try:
        # 1. Check connection before any CRUD calls.
        await client.ensure_connection()
        print("github: connected")

        # 2. Read workspaces available for the current token.
        workspaces = await client.list_workspaces()
        print(workspaces)

        available_projects = await client.list_projects()
        print("github: available projects")
        for available_project in available_projects:
            print(
                f"- id={available_project.id} key={available_project.key} "
                f"name={available_project.name}"
            )

        # 3. Repository create/update/delete is unsupported. Use the repository
        # named by GITHUB_REPOSITORY, the same role as an existing Jira project.
        project = next(
            (
                item
                for item in available_projects
                if item.key and item.key.casefold() == repository_name.casefold()
            ),
            None,
        )
        if project is None:
            print(f"Repository {repository_name!r} is not visible to the configured token.")
            return

        print(project)
        await client.get_project(project.id)
        wait_for_enter("Using existing GitHub project. Check it before task creation.")

        # 4. Create one root task and three target tasks for each relation type.
        project_id = project.id
        tasks = await client.list_tasks(TaskQuery(project_id=project_id))
        print(tasks)

        created_tasks = []
        created_relations = []
        try:
            for index, title in enumerate(
                (
                    "Prepare release notes",
                    "Review release notes",
                    "Publish release summary",
                    "Prepare release checklist",
                ),
                start=1,
            ):
                task = await client.create_task(
                    CreateTaskInput(
                        title=title,
                        description=(
                            f"Example GitHub task {index} created for relation CRUD validation."
                        ),
                        project_id=project_id,
                        state=TaskState.OPEN if index == 1 else None,
                        priority=TaskPriority.HIGH if index == 1 else None,
                        work_type=TaskWorkType.BUG if index == 1 else None,
                        start_date=datetime(2026, 11, 20, tzinfo=UTC) if index == 1 else None,
                        due_date=datetime(2026, 11, 27, tzinfo=UTC) if index == 1 else None,
                    )
                )
                created_tasks.append(task)
                print(task)

            created_tasks[0] = await client.get_task(created_tasks[0].id)
            print("github: root task fields")
            print(created_tasks[0])
            wait_for_enter("Root task fields read. Check them in GitHub before the update.")

            update = {
                "title": "Prepare release notes (updated)",
                "description": "Updated GitHub relation example root task.",
                "state": TaskState.DONE,
                "priority": TaskPriority.LOW,
                "work_type": TaskWorkType.TASK,
                "start_date": datetime(2026, 11, 21, tzinfo=UTC),
                "due_date": datetime(2026, 11, 28, tzinfo=UTC),
            }
            if created_tasks[0].reporter is not None:
                update["assignee_id"] = created_tasks[0].reporter.id
            await client.update_task(created_tasks[0].id, UpdateTaskInput(**update))
            created_tasks[0] = await client.get_task(created_tasks[0].id)
            print("github: root task fields after update")
            print(created_tasks[0])
            wait_for_enter(
                "Root task fields updated and read again. Check them in GitHub before relation creation."
            )

            root_task, blocked_task, related_task, child_task = created_tasks
            relation_specs = (
                (blocked_task, RelationType.BLOCKS),
                (related_task, RelationType.RELATES),
                (child_task, RelationType.CONTAINS),
            )

            for target_task, relation_type in relation_specs:
                relation = await client.create_relation(
                    CreateRelationInput(
                        source_task_id=root_task.id,
                        target_task_id=target_task.id,
                        relation_type=relation_type,
                    )
                )
                created_relations.append(relation)
                print(f"github: created {relation_type.value} relation")
                print(relation)

            print("github: relations for root task")
            print(await client.list_relations(root_task.id))
            for target_task, relation_type in relation_specs:
                print(
                    f"github: relations for {relation_type.value} target "
                    f"{target_task.key or target_task.id}"
                )
                print(await client.list_relations(target_task.id))

            wait_for_enter("Three relations created. Check them in GitHub before cleanup.")
        finally:
            for relation in reversed(created_relations):
                if relation.id is None:
                    continue
                try:
                    await client.delete_relation(relation.id)
                except TrackerClientError as error:
                    print(f"Could not delete relation {relation.id}: {error}")

            wait_for_enter("Relations deleted where supported. Check GitHub before task delete.")

            for task in reversed(created_tasks):
                try:
                    await client.delete_task(task.id)
                except TrackerClientError as error:
                    print(f"Could not delete task {task.id}: {error}")
            wait_for_enter("Tasks deleted. Check them in GitHub after delete.")
        print("github: done")
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TrackerClientError as error:
        print(error)
