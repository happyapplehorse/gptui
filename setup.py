import setuptools


setuptools.setup(
    packages=setuptools.find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "gptui": [
            ".default_config.yml",
            "config.yml",
            "help.md",
            "**/*.txt",
            "**/*.tcss",
        ],
    },
)
