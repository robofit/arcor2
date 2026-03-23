from packaging.version import InvalidVersion, Version

from pants.backend.python.target_types import PythonProvidesField
from pants.backend.python.util_rules.package_dists import SetupKwargs, SetupKwargsRequest
from pants.engine.fs import GlobMatchErrorBehavior, PathGlobs
from pants.engine.intrinsics import get_digest_contents
from pants.engine.rules import collect_rules, implicitly, rule
from pants.engine.target import Target
from pants.engine.unions import UnionRule


class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True


def rules():
    return [
        *collect_rules(),
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]


async def _read_required_file(spec_path: str, filename: str) -> str:
    digest_contents = await get_digest_contents(
        **implicitly(
            PathGlobs(
                [f"{spec_path}/{filename}"],
                description_of_origin="`setup_py()` plugin",
                glob_match_error_behavior=GlobMatchErrorBehavior.error,
            )
        )
    )
    return digest_contents[0].content.decode().strip()


@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    version = await _read_required_file(request.target.address.spec_path, "VERSION")

    package_name = request.target[PythonProvidesField].value.kwargs["name"]

    try:
        Version(version)
    except InvalidVersion as exc:
        raise ValueError(f"Version {version} of {package_name} is not valid.") from exc

    long_description = await _read_required_file(request.target.address.spec_path, "README.md")

    changelog = await _read_required_file(request.target.address.spec_path, "CHANGELOG.md")

    return SetupKwargs(
        {
            **request.explicit_kwargs,
            "version": version,
            "long_description": f"{long_description}\n{changelog}",
            "long_description_content_type": "text/markdown",
        },
        address=request.target.address,
    )
