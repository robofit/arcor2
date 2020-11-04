from packaging.version import parse, LegacyVersion

from pants.backend.python.target_types import PythonProvidesField
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

    version_digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [f"{request.target.address.spec_path}/VERSION"],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    version = version_digest_contents[0].content.decode().strip()

    package_name = request.target[PythonProvidesField].value.name

    local_version = parse(version)
    if isinstance(local_version, LegacyVersion):
        raise ValueError(f"Version {local_version} of {package_name} is not valid.")

    desc_digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [f"{request.target.address.spec_path}/README.md"],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    long_description = desc_digest_contents[0].content.decode().strip()

    changelog_digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [f"{request.target.address.spec_path}/CHANGELOG.md"],
            description_of_origin="`setup_py()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    changelog = changelog_digest_contents[0].content.decode().strip()

    return SetupKwargs(
        {
            **request.explicit_kwargs,
            "version": version,
            "long_description": f"{long_description}\n{changelog}",
            "long_description_content_type": "text/markdown"
         },
        address=request.target.address
    )
