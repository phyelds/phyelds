var dryRun = (process.env.RELEASE_DRY_RUN || "false").toLowerCase() === "true";
var testPypi = (process.env.RELEASE_TEST_PYPI || "false").toLowerCase() === "true";
var pypiUsername = process.env.PYPI_USERNAME;
var pypiPassword = process.env.PYPI_PASSWORD;

// The packages are released together: each requires the core (and the simulator) of its
// own release, as tested here, up to the next major one.
function prepare(name) {
    return "(cd packages/" + name + " && poetry version -- \${nextRelease.version}"
        + " && sed -i -E 's/^(phyelds|phyelds-simulator) = .*/\\1 = \"^\${nextRelease.version}\"/' pyproject.toml)";
}

var prepareCmd = [
    "poetry version -- \${nextRelease.version}",
    prepare("phyelds-simulator"),
    prepare("phyelds-mesa"),
    prepare("phyelds-webots"),
    prepare("phyelds-argos"),
    prepare("phyelds-vmas"),
].join(" && ");
var publishOptions = "--build";

if (testPypi) {
    // test-pypi repository name is defined in poetry.toml
    publishOptions += " --repository pypi-test";
}

if (dryRun) {
    publishOptions += " --dry-run";
}

var publishCmd = [
    `poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword}`,
    `(cd packages/phyelds-simulator && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword})`,
    `(cd packages/phyelds-mesa && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword})`,
    `(cd packages/phyelds-webots && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword})`,
    `(cd packages/phyelds-argos && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword})`,
    `cd packages/phyelds-vmas && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword}`,
].join(" && ");

var config = require('semantic-release-preconfigured-conventional-commits');

config.plugins.push(
    ["@semantic-release/changelog", {
        "changelogFile": "packages/phyelds-simulator/CHANGELOG.md",
    }],
    ["@semantic-release/changelog", {
        "changelogFile": "packages/phyelds-mesa/CHANGELOG.md",
    }],
    ["@semantic-release/changelog", {
        "changelogFile": "packages/phyelds-webots/CHANGELOG.md",
    }],
    ["@semantic-release/changelog", {
        "changelogFile": "packages/phyelds-argos/CHANGELOG.md",
    }],
    ["@semantic-release/changelog", {
        "changelogFile": "packages/phyelds-vmas/CHANGELOG.md",
    }],
    ["@semantic-release/exec", {
        "prepareCmd" : prepareCmd,
        "publishCmd": publishCmd,
    }]
)

if (!dryRun) {
    config.plugins.push(
        ["@semantic-release/github", {
            "assets": [
                { "path": "dist/*" },
                { "path": "packages/phyelds-simulator/dist/*" },
                { "path": "packages/phyelds-mesa/dist/*" },
                { "path": "packages/phyelds-webots/dist/*" },
                { "path": "packages/phyelds-argos/dist/*" },
                { "path": "packages/phyelds-vmas/dist/*" },
            ]
        }],
        ["@semantic-release/git", {
            "assets": [
                "CHANGELOG.md",
                "pyproject.toml",
                "packages/phyelds-simulator/CHANGELOG.md",
                "packages/phyelds-simulator/pyproject.toml",
                "packages/phyelds-mesa/CHANGELOG.md",
                "packages/phyelds-mesa/pyproject.toml",
                "packages/phyelds-webots/CHANGELOG.md",
                "packages/phyelds-webots/pyproject.toml",
                "packages/phyelds-argos/CHANGELOG.md",
                "packages/phyelds-argos/pyproject.toml",
                "packages/phyelds-vmas/CHANGELOG.md",
                "packages/phyelds-vmas/pyproject.toml"
            ],
            "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
        }]
    );
}

module.exports = config