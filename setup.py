from distutils.core import setup

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


setuptools.setup(
    name="zaailabcorelib",
    version="0.1.8.1",
    author="ailabteam",
    author_email="thanhtri2502@gmail.com",
    include_package_data=True,
    description="A Useful tools inside Zalo AILab Team",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/phamthanhtri/zaailabcorelib",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    tests_require=["pytest",
                    "mock"],
    test_suite="pytest",
)
