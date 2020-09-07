from pants.backend.python.goals.setup_py import SetupKwargsRequest
from pants.engine.target import Target
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule
from pants.backend.python.goals.setup_py import SetupKwargs
from pants.engine.rules import Get, rule
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs


class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True


def rules():
    return [
        *collect_rules(),
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]


@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:

    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [f"{request.target.address.spec_path}/VERSION"],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    version = digest_contents[0].content.decode().strip()

    return SetupKwargs(
        {**request.explicit_kwargs, "version": version},
        address=request.target.address
    )
