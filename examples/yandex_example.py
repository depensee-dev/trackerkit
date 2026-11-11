import asyncio
import os
import random
import string

from _base import wait_for_enter
from _env import load_env

from trackerkit import (
    CreateProjectInput,
    CreateRelationInput,
    CreateTaskInput,
    ProviderCapabilityError,
    RelationType,
    TrackerClient,
    TrackerClientError,
    UpdateProjectInput,
    UpdateTaskInput,
    YandexTrackerAuthConfig,
)


async def main() -> None:
    """Run the Yandex Tracker example flow with explicit auth config."""

    load_env()
    cloud_org_id = os.getenv("YANDEX_CLOUD_ORG_ID")
    org_id = os.getenv("YANDEX_ORG_ID")

    # Auth config makes the expected parameters explicit for the example.
    auth_config = YandexTrackerAuthConfig(
        token=os.getenv("YANDEX_TOKEN"),
        cloud_org_id=cloud_org_id,
        org_id=None if cloud_org_id else org_id,
    )

    client = TrackerClient(
        provider="yandex_tracker",
        auth_data=auth_config.model_dump(exclude_none=True),
    )

    # 1. Check connection before any CRUD calls.
    await client.ensure_connection()
    print("yandex_tracker: connected")

    # 2. Read workspaces available for the current token.
    workspaces = await client.list_workspaces()
    print(workspaces)

    projects = await client.list_projects()
    print("yandex_tracker: available projects")
    for available_project in projects:
        print(
            f"- id={available_project.id} key={available_project.key} name={available_project.name}"
        )

    # 3. Always create a temporary queue-backed project for the example flow.
    # This keeps test data isolated and allows deleting the whole queue after
    # the run instead of leaving tasks in a shared existing queue.
    created_project = False
    project_key = "TRKIT" + "".join(random.choices(string.ascii_uppercase, k=3))
    try:
        project = await client.create_project(
            CreateProjectInput(
                name=f"TrackerKit Demo Project {project_key[-3:]}",
                key=project_key,
                description="Temporary example project created from trackerkit.",
            )
        )
        created_project = True
    except ProviderCapabilityError as error:
        print(error)
        print(
            "Yandex example now requires permission to create a temporary queue/project "
            "so the whole example can be cleaned up safely."
        )
        return
    print(project)

    wait_for_enter("Project created. Check it in Yandex Tracker before update.")

    # Update the created project.
    project = await client.update_project(
        project.id,
        UpdateProjectInput(description="Updated temporary Yandex example project."),
    )
    print(project)

    wait_for_enter("Project updated. Check it in Yandex Tracker before task creation.")

    created_relations = []
    try:
        # 4. Create one root task and three target tasks for each relation type.
        created_tasks = []
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
                        f"Example Yandex Tracker task {index} created for relation CRUD validation."
                    ),
                    project_id=project.key or project.id,
                )
            )
            created_tasks.append(task)
            print(task)

        await client.get_task(created_tasks[0].id)
        wait_for_enter("Tasks created. Check them in Yandex Tracker before task update.")

        created_tasks[0] = await client.update_task(
            created_tasks[0].id,
            UpdateTaskInput(description="Updated Yandex relation example root task."),
        )
        print(created_tasks[0])

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
            print(f"yandex_tracker: created {relation_type.value} relation")
            print(relation)

        print("yandex_tracker: relations for root task")
        print(await client.list_relations(root_task.id))
        for target_task, relation_type in relation_specs:
            print(
                f"yandex_tracker: relations for {relation_type.value} target "
                f"{target_task.key or target_task.id}"
            )
            print(await client.list_relations(target_task.id))

        wait_for_enter("Three relations created. Check them in Yandex Tracker before cleanup.")
    finally:
        # Yandex Tracker does not support direct issue deletion reliably in this flow.
        # Instead, remove links and delete the whole temporary queue/project.
        if created_project:
            for relation in reversed(created_relations):
                if relation.id is None:
                    continue
                try:
                    await client.delete_relation(relation.id)
                except TrackerClientError as error:
                    print(f"Could not delete relation {relation.id}: {error}")
            wait_for_enter(
                "Relations removed. Tasks still exist in the temporary queue. Check them before project delete."
            )
            await client.delete_project(project.id)
            wait_for_enter("Temporary project deleted. Check it in Yandex Tracker after delete.")
    print("yandex_tracker: done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TrackerClientError as error:
        print(error)
