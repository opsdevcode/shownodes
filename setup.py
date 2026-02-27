from setuptools import setup

setup(
    name="shownodes",
    version="0.4.0",
    description="Better kubectl get nodes for kubernetes",
    long_description=open("README.md").read(),
    url="",
    author="Jonathan Eunice",
    author_email="jonathan@3playmedia.com",
    packages=["shownodes"],
    package_data={"shownodes": ["data/instance-prices.json"]},
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points="""
        [console_scripts]
        shownodes=shownodes:cli
    """,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
