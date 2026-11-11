import asyncio
import os

from _base import wait_for_enter
from _env import load_env

from trackerkit import (
    CreateProjectInput,
    CreateRelationInput,
    CreateTaskInput,
    JiraAuthConfig,
    ProviderCapabilityError,
    RelationMappingConfig,
    RelationType,
    TaskQuery,
    TrackerClient,
    TrackerClientError,
    UpdateProjectInput,
    UpdateTaskInput,
)


async def main() -> None:
    """Run the Jira example flow with explicit auth config."""

    load_env()

    # Auth config makes the expected parameters explicit for the example.
    auth_config = JiraAuthConfig(
        base_url=os.getenv("JIRA_BASE_URL"),
        access_token=os.getenv("JIRA_TOKEN"),
    )

    client = TrackerClient(
        provider="jira",
        auth_data=auth_config.model_dump(exclude_none=True),
        # Examples can opt into env-based mapping. Production code should usually
        # construct RelationMappingConfig explicitly from service settings.
        relation_mapping=RelationMappingConfig.from_env(),
    )

    # 1. Check connection before any CRUD calls.
    await client.ensure_connection()
    print("jira: connected")

    # 2. Read workspaces available for the current token.
    workspaces = await client.list_workspaces()
    print(workspaces)

    available_projects = await client.list_projects()
    print("jira: available projects")
    for available_project in available_projects:
        print(
            f"- id={available_project.id} key={available_project.key} name={available_project.name}"
        )

    # 3. Create, read, update, and delete a project when the token has enough
    # permissions. Otherwise, fall back to the first existing project so the
    # task flow can still be verified on restricted Jira instances.
    created_project = False
    try:
        project = await client.create_project(
            CreateProjectInput(
                name="Platform",
                key="PLATFORM",
                description="Platform team project",
            )
        )
        created_project = True
    except ProviderCapabilityError as error:
        print(error)
        if not available_projects:
            print("No existing Jira projects available for fallback task flow.")
            return
        project = available_projects[0]
        print(f"Fallback to existing Jira project: {project.key or project.id}")

    print(project)
    await client.get_project(project.id)

    if created_project:
        wait_for_enter("Project created. Check it in Jira before update.")

        project = await client.update_project(
            project.id,
            UpdateProjectInput(description="Updated description"),
        )
        print(project)

        wait_for_enter("Project updated. Check it in Jira before task creation.")
    else:
        wait_for_enter("Using existing Jira project. Check it before task creation.")

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
                        f"Example Jira task {index} created for relation CRUD validation."
                    ),
                    project_id=project_id,
                )
            )
            created_tasks.append(task)
            print(task)

        await client.get_task(created_tasks[0].id)
        wait_for_enter("Tasks created. Check them in Jira before task update.")

        created_tasks[0] = await client.update_task(
            created_tasks[0].id,
            UpdateTaskInput(description="Updated Jira relation example root task."),
        )
        print(created_tasks[0])

        wait_for_enter("Task updated. Check it in Jira before relation creation.")

        root_task, blocked_task, related_task, child_task = created_tasks
        relation_specs = (
            (blocked_task, RelationType.BLOCKS),
            (related_task, RelationType.RELATES),
            (child_task, RelationType.CONTAINS),
        )

        jira_transport = client._client._transport
        for target_task, relation_type in relation_specs:
            relation = await client.create_relation(
                CreateRelationInput(
                    source_task_id=root_task.id,
                    target_task_id=target_task.id,
                    relation_type=relation_type,
                )
            )
            created_relations.append(relation)
            print(f"jira: created {relation_type.value} relation")
            print(relation)
            if relation.id is not None and relation.id.startswith("jira-contains:"):
                print("jira: contains relation created through structural hierarchy")
            else:
                print("jira: raw create_issue_link response")
                print(jira_transport.get_last_issue_link_debug())

        print("jira: relations for root task")
        print(await client.list_relations(root_task.id))
        for target_task, relation_type in relation_specs:
            print(
                f"jira: relations for {relation_type.value} target "
                f"{target_task.key or target_task.id}"
            )
            print(await client.list_relations(target_task.id))

        wait_for_enter("Three relations created. Check them in Jira before cleanup.")
    finally:
        for relation in reversed(created_relations):
            if relation.id is None:
                continue
            try:
                await client.delete_relation(relation.id)
            except TrackerClientError as error:
                print(f"Could not delete relation {relation.id}: {error}")

        wait_for_enter("Relations deleted where supported. Check Jira before task delete.")

        for task in reversed(created_tasks):
            try:
                await client.delete_task(task.id)
            except TrackerClientError as error:
                print(f"Could not delete task {task.id}: {error}")
        wait_for_enter("Tasks deleted. Check them in Jira after delete.")

        if created_project:
            wait_for_enter("Check the project in Jira before project delete.")
            await client.delete_project(project.id)
            wait_for_enter("Project deleted. Check it in Jira after delete.")
    print("jira: done")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except TrackerClientError as error:
        print(error)
