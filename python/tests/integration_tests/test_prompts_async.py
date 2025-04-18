from typing import Literal
from uuid import uuid4

import pytest
from langchain_core.prompts import (
    BasePromptTemplate,
    ChatPromptTemplate,
    PromptTemplate,
)
from langchain_core.runnables.base import RunnableSequence

import langsmith.schemas as ls_schemas
import langsmith.utils as ls_utils
from langsmith.async_client import (
    AsyncClient,
)


@pytest.fixture
def langsmith_client() -> AsyncClient:
    return AsyncClient(timeout_ms=(50_000, 90_000))


@pytest.fixture
def prompt_template_1() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_template("tell me a joke about {topic}")


@pytest.fixture
def prompt_template_2() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", "You are a helpful assistant."),
            ("human", "{question}"),
        ]
    )


@pytest.fixture
def prompt_template_3() -> PromptTemplate:
    return PromptTemplate.from_template("Summarize the following text: {text}")


@pytest.fixture
def prompt_with_model() -> dict:
    return {
        "id": ["langsmith", "playground", "PromptPlayground"],
        "lc": 1,
        "type": "constructor",
        "kwargs": {
            "last": {
                "id": ["langchain", "schema", "runnable", "RunnableBinding"],
                "lc": 1,
                "type": "constructor",
                "kwargs": {
                    "bound": {
                        "id": ["langchain", "chat_models", "openai", "ChatOpenAI"],
                        "lc": 1,
                        "type": "constructor",
                        "kwargs": {
                            "openai_api_key": {
                                "id": ["OPENAI_API_KEY"],
                                "lc": 1,
                                "type": "secret",
                            }
                        },
                    },
                    "kwargs": {},
                },
            },
            "first": {
                "id": ["langchain", "prompts", "chat", "ChatPromptTemplate"],
                "lc": 1,
                "type": "constructor",
                "kwargs": {
                    "messages": [
                        {
                            "id": [
                                "langchain",
                                "prompts",
                                "chat",
                                "SystemMessagePromptTemplate",
                            ],
                            "lc": 1,
                            "type": "constructor",
                            "kwargs": {
                                "prompt": {
                                    "id": [
                                        "langchain",
                                        "prompts",
                                        "prompt",
                                        "PromptTemplate",
                                    ],
                                    "lc": 1,
                                    "type": "constructor",
                                    "kwargs": {
                                        "template": "You are a chatbot.",
                                        "input_variables": [],
                                        "template_format": "f-string",
                                    },
                                }
                            },
                        },
                        {
                            "id": [
                                "langchain",
                                "prompts",
                                "chat",
                                "HumanMessagePromptTemplate",
                            ],
                            "lc": 1,
                            "type": "constructor",
                            "kwargs": {
                                "prompt": {
                                    "id": [
                                        "langchain",
                                        "prompts",
                                        "prompt",
                                        "PromptTemplate",
                                    ],
                                    "lc": 1,
                                    "type": "constructor",
                                    "kwargs": {
                                        "template": "{question}",
                                        "input_variables": ["question"],
                                        "template_format": "f-string",
                                    },
                                }
                            },
                        },
                    ],
                    "input_variables": ["question"],
                },
            },
        },
    }


@pytest.fixture
def chat_prompt_template():
    return ChatPromptTemplate.from_messages(
        [
            ("system", "You are a chatbot"),
            ("user", "{question}"),
        ]
    )


async def test_current_tenant_is_owner(langsmith_client: AsyncClient):
    settings = await langsmith_client._get_settings()
    assert await langsmith_client._current_tenant_is_owner(
        settings.tenant_handle or "-"
    )
    assert await langsmith_client._current_tenant_is_owner("-")
    assert not await langsmith_client._current_tenant_is_owner("non_existent_owner")


async def test_list_prompts(langsmith_client: AsyncClient):
    response = await langsmith_client.list_prompts(limit=10, offset=0)
    assert isinstance(response, ls_schemas.ListPromptsResponse)
    assert len(response.repos) <= 10


async def test_get_prompt(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    url = await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)
    assert isinstance(url, str)
    assert await langsmith_client._prompt_exists(prompt_name)

    prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.repo_handle == prompt_name

    await langsmith_client.delete_prompt(prompt_name)


async def test_prompt_exists(
    langsmith_client: AsyncClient, prompt_template_2: ChatPromptTemplate
):
    non_existent_prompt = f"non_existent_{uuid4().hex[:8]}"
    assert not await langsmith_client._prompt_exists(non_existent_prompt)

    existent_prompt = f"existent_{uuid4().hex[:8]}"
    assert await langsmith_client.push_prompt(existent_prompt, object=prompt_template_2)

    await langsmith_client.delete_prompt(existent_prompt)


async def test_update_prompt(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    updated_data = await langsmith_client.update_prompt(
        prompt_name,
        description="Updated description",
        is_public=True,
        tags=["test", "update"],
    )
    assert isinstance(updated_data, dict)

    updated_prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(updated_prompt, ls_schemas.Prompt)
    assert updated_prompt.description == "Updated description"
    assert updated_prompt.is_public
    assert set(updated_prompt.tags) == set(["test", "update"])

    await langsmith_client.delete_prompt(prompt_name)


async def test_delete_prompt(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    assert await langsmith_client._prompt_exists(prompt_name)
    await langsmith_client.delete_prompt(prompt_name)
    assert not await langsmith_client._prompt_exists(prompt_name)


async def test_pull_prompt_object(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    manifest = await langsmith_client.pull_prompt_commit(prompt_name)
    assert isinstance(manifest, ls_schemas.PromptCommit)
    assert manifest.repo == prompt_name

    await langsmith_client.delete_prompt(prompt_name)


async def test_pull_prompt(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    # test pulling with just prompt name
    pulled_prompt = await langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)
    assert (
        pulled_prompt.metadata and pulled_prompt.metadata["lc_hub_repo"] == prompt_name
    )

    # test pulling with private owner (-) and name
    pulled_prompt_2 = await langsmith_client.pull_prompt(f"-/{prompt_name}")
    assert pulled_prompt == pulled_prompt_2

    # test pulling with tenant handle and name
    tenant_handle = (await langsmith_client._get_settings()).tenant_handle
    pulled_prompt_3 = await langsmith_client.pull_prompt(
        f"{tenant_handle}/{prompt_name}"
    )
    assert pulled_prompt.metadata and pulled_prompt_3.metadata
    assert (
        pulled_prompt.metadata["lc_hub_commit_hash"]
        == pulled_prompt_3.metadata["lc_hub_commit_hash"]
    )
    assert pulled_prompt_3.metadata["lc_hub_owner"] == tenant_handle

    # test pulling with handle, name and commit hash
    tenant_handle = (await langsmith_client._get_settings()).tenant_handle
    pulled_prompt_4 = await langsmith_client.pull_prompt(
        f"{tenant_handle}/{prompt_name}:latest"
    )
    assert pulled_prompt_3 == pulled_prompt_4

    # test pulling without handle, with commit hash
    assert pulled_prompt_4.metadata
    pulled_prompt_5 = await langsmith_client.pull_prompt(
        f"{prompt_name}:{pulled_prompt_4.metadata['lc_hub_commit_hash']}"
    )
    assert pulled_prompt_5.metadata
    assert (
        pulled_prompt_4.metadata["lc_hub_commit_hash"]
        == pulled_prompt_5.metadata["lc_hub_commit_hash"]
    )

    await langsmith_client.delete_prompt(prompt_name)


async def test_push_and_pull_prompt(
    langsmith_client: AsyncClient, prompt_template_2: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"

    push_result = await langsmith_client.push_prompt(
        prompt_name, object=prompt_template_2
    )
    assert isinstance(push_result, str)

    pulled_prompt = await langsmith_client.pull_prompt(prompt_name)
    assert isinstance(pulled_prompt, ChatPromptTemplate)

    await langsmith_client.delete_prompt(prompt_name)

    # should fail
    with pytest.raises(ls_utils.LangSmithUserError):
        await langsmith_client.push_prompt(
            f"random_handle/{prompt_name}", object=prompt_template_2
        )


async def test_pull_prompt_include_model(
    langsmith_client: AsyncClient, prompt_with_model: dict
):
    prompt_name = f"test_prompt_with_model_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_with_model)

    pulled_prompt = await langsmith_client.pull_prompt(prompt_name, include_model=True)
    assert isinstance(pulled_prompt, RunnableSequence)
    if getattr(pulled_prompt, "first", None):
        first = getattr(pulled_prompt, "first")
        assert isinstance(first, BasePromptTemplate)
        assert first.metadata and first.metadata["lc_hub_repo"] == prompt_name
    else:
        assert False, "pulled_prompt.first should exist, incorrect prompt format"

    await langsmith_client.delete_prompt(prompt_name)


async def test_like_unlike_prompt(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    await langsmith_client.like_prompt(prompt_name)
    prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_likes == 1

    await langsmith_client.unlike_prompt(prompt_name)
    prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_likes == 0

    await langsmith_client.delete_prompt(prompt_name)


async def test_get_latest_commit_hash(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_prompt_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    commit_hash = await langsmith_client._get_latest_commit_hash(f"-/{prompt_name}")
    assert isinstance(commit_hash, str)
    assert len(commit_hash) > 0

    await langsmith_client.delete_prompt(prompt_name)


async def test_create_prompt(langsmith_client: AsyncClient):
    prompt_name = f"test_create_prompt_{uuid4().hex[:8]}"
    created_prompt = await langsmith_client.create_prompt(
        prompt_name,
        description="Test description",
        readme="Test readme",
        tags=["test", "create"],
        is_public=False,
    )
    assert isinstance(created_prompt, ls_schemas.Prompt)
    assert created_prompt.repo_handle == prompt_name
    assert created_prompt.description == "Test description"
    assert created_prompt.readme == "Test readme"
    assert set(created_prompt.tags) == set(["test", "create"])
    assert not created_prompt.is_public

    await langsmith_client.delete_prompt(prompt_name)


async def test_create_commit(
    langsmith_client: AsyncClient,
    prompt_template_2: ChatPromptTemplate,
    prompt_template_3: PromptTemplate,
):
    prompt_name = f"test_create_commit_{uuid4().hex[:8]}"
    try:
        # this should fail because the prompt does not exist
        commit_url = await langsmith_client.create_commit(
            prompt_name, object=prompt_template_2
        )
        pytest.fail("Expected LangSmithNotFoundError was not raised")
    except ls_utils.LangSmithNotFoundError as e:
        assert str(e) == "Prompt does not exist, you must create it first."
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")

    await langsmith_client.push_prompt(prompt_name, object=prompt_template_3)
    commit_url = await langsmith_client.create_commit(
        prompt_name, object=prompt_template_2
    )
    assert isinstance(commit_url, str)
    assert prompt_name in commit_url

    prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.num_commits == 2

    # try submitting different types of unaccepted manifests
    try:
        # this should fail
        commit_url = await langsmith_client.create_commit(
            prompt_name, object={"hi": "hello"}
        )
    except ls_utils.LangSmithError as e:
        err = str(e)
        assert "Manifest must have an id field" in err
        assert "400 Bad Request" in err
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")

    try:
        # this should fail
        commit_url = await langsmith_client.create_commit(
            prompt_name, object={"id": ["hi"]}
        )
    except ls_utils.LangSmithError as e:
        err = str(e)
        assert "Manifest type hi is not supported" in err
        assert "400 Bad Request" in err
    except Exception as e:
        pytest.fail(f"Unexpected exception raised: {e}")

    await langsmith_client.delete_prompt(prompt_name)


async def test_push_prompt(
    langsmith_client: AsyncClient,
    prompt_template_3: PromptTemplate,
    prompt_template_2: ChatPromptTemplate,
):
    prompt_name = f"test_push_new_{uuid4().hex[:8]}"
    url = await langsmith_client.push_prompt(
        prompt_name,
        object=prompt_template_3,
        is_public=True,
        description="New prompt",
        tags=["new", "test"],
    )

    assert isinstance(url, str)
    assert prompt_name in url

    prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(prompt, ls_schemas.Prompt)
    assert prompt.is_public
    assert prompt.description == "New prompt"
    assert "new" in prompt.tags
    assert "test" in prompt.tags
    assert prompt.num_commits == 1

    # test updating prompt metadata but not manifest
    url = await langsmith_client.push_prompt(
        prompt_name,
        is_public=False,
        description="Updated prompt",
    )

    updated_prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(updated_prompt, ls_schemas.Prompt)
    assert updated_prompt.description == "Updated prompt"
    assert not updated_prompt.is_public
    assert updated_prompt.num_commits == 1

    # test updating prompt manifest but not metadata
    url = await langsmith_client.push_prompt(
        prompt_name,
        object=prompt_template_2,
    )
    assert isinstance(url, str)

    await langsmith_client.delete_prompt(prompt_name)


@pytest.mark.parametrize("is_public,expected_count", [(True, 1), (False, 1)])
async def test_list_prompts_filter(
    langsmith_client: AsyncClient,
    prompt_template_1: ChatPromptTemplate,
    is_public: bool,
    expected_count: int,
):
    prompt_name = f"test_list_filter_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(
        prompt_name, object=prompt_template_1, is_public=is_public
    )

    response = await langsmith_client.list_prompts(
        is_public=is_public, query=prompt_name
    )

    assert response.total == expected_count
    if expected_count > 0:
        assert response.repos[0].repo_handle == prompt_name

    await langsmith_client.delete_prompt(prompt_name)


async def test_update_prompt_archive(
    langsmith_client: AsyncClient, prompt_template_1: ChatPromptTemplate
):
    prompt_name = f"test_archive_{uuid4().hex[:8]}"
    await langsmith_client.push_prompt(prompt_name, object=prompt_template_1)

    await langsmith_client.update_prompt(prompt_name, is_archived=True)
    archived_prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(archived_prompt, ls_schemas.Prompt)
    assert archived_prompt.is_archived

    await langsmith_client.update_prompt(prompt_name, is_archived=False)
    unarchived_prompt = await langsmith_client.get_prompt(prompt_name)
    assert isinstance(unarchived_prompt, ls_schemas.Prompt)
    assert not unarchived_prompt.is_archived

    await langsmith_client.delete_prompt(prompt_name)


@pytest.mark.parametrize(
    "sort_field, sort_direction",
    [
        (ls_schemas.PromptSortField.updated_at, "desc"),
    ],
)
async def test_list_prompts_sorting(
    langsmith_client: AsyncClient,
    prompt_template_1: ChatPromptTemplate,
    sort_field: ls_schemas.PromptSortField,
    sort_direction: Literal["asc", "desc"],
):
    prompt_names = [f"test_sort_{i}_{uuid4().hex[:8]}" for i in range(3)]
    for name in prompt_names:
        await langsmith_client.push_prompt(name, object=prompt_template_1)

    response = await langsmith_client.list_prompts(
        sort_field=sort_field, sort_direction=sort_direction, limit=10
    )

    assert len(response.repos) >= 3
    sorted_names = [
        repo.repo_handle for repo in response.repos if repo.repo_handle in prompt_names
    ]
    assert sorted_names == sorted(sorted_names, reverse=(sort_direction == "desc"))

    for name in prompt_names:
        await langsmith_client.delete_prompt(name)
