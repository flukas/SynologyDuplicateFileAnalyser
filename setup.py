from setuptools import setup, find_packages

setup(
    name="duplicate-folder-analyzer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        'pytest>=7.4.3',
    ],
)