from setuptools import setup, find_packages

setup(
    name="projectos",
    version="0.1.0",
    description="Multi-Project AI Agent Command Center",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pytest>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "projectos=projectos.__main__:main",
        ],
    },
)
