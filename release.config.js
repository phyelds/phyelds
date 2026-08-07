var dryRun = (process.env.RELEASE_DRY_RUN || "false").toLowerCase() === "true";
var testPypi = (process.env.RELEASE_TEST_PYPI || "false").toLowerCase() === "true";
var pypiUsername = process.env.PYPI_USERNAME;
var pypiPassword = process.env.PYPI_PASSWORD;

var prepareCmd = [
    "poetry version -- \${nextRelease.version}",
    "cd packages/phyelds-vmas && poetry version -- \${nextRelease.version}",
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
    `cd packages/phyelds-vmas && poetry publish ${publishOptions} --username ${pypiUsername} --password ${pypiPassword}`,
].join(" && ");

var config = require('semantic-release-preconfigured-conventional-commits');

config.plugins.push(
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
                { "path": "packages/phyelds-vmas/dist/*" },
            ]
        }],
        ["@semantic-release/git", {
            "assets": [
                "CHANGELOG.md",
                "pyproject.toml",
                "packages/phyelds-vmas/CHANGELOG.md",
                "packages/phyelds-vmas/pyproject.toml"
            ],
            "message": "chore(release): ${nextRelease.version} [skip ci]\n\n${nextRelease.notes}"
        }]
    );
}

module.exports = config