from os.path import join
from setuptools import setup, find_packages


long_description = open("README.md").read() + open("CHANGES.md").read()


def get_version():
    with open(join("tink_fields", "__init__.py")) as f:
        for line in f:
            if line.startswith("__version__ ="):
                return line.split("=")[1].strip().strip("\"'")


setup(
    name="django-tink-fields",
    version=get_version(),
    description="Tink-based encrypted model fields for Django",
    long_description=long_description,
    long_description_content_type="text/x-markdown",
    author="Isaac Elbaz",
    author_email="script3r@gmail.com",
    url="https://github.com/script3r/django-tink-fields/",
    packages=find_packages(),
    install_requires=["Django>=3.2.13", "tink>=1.6.1"],
    classifiers=[
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Framework :: Django",
    ],
    zip_safe=False,
)
