from setuptools import setup, find_packages

setup(
    name="duplicate-folder-analyzer",
    version="0.1",
    packages=find_packages(),
    # Phase 1 (analysis core) has no runtime dependencies (standard library
    # only). Phase 2 (HTML integration) will add beautifulsoup4.
    # Test-only dependencies live in tests/requirements.txt.
    install_requires=[],
    extras_require={
        "test": ["pytest>=7.4.3"],
    },
)