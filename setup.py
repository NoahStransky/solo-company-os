from setuptools import setup, find_packages

setup(
    name="projectos",
    version="0.1.0",
    description="Multi-project control plane for initialized solo projects",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pytest>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "projectos=projectos.__main__:main",
            "solo-os=projectos.__main__:main",
        ],
    },
)
