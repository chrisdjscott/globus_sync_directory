from setuptools import setup, find_packages

setup(
    name="globus_sync_directory",
    version="0.2.1",
    description="Sync directories with Globus",
    url="https://github.com/chrisdjscott/globus_sync_directory",
    author="Chris Scott",
    author_email="chris.scott@nesi.org.nz",
    license="MIT",
    packages=find_packages(),
    install_requires=["globus_sdk>=3"],
    entry_points={
        "console_scripts": ["sync_directory=globus_sync_directory.__main__:main"]
    },
)
