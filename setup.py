import pathlib
import setuptools

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setuptools.setup(
    name="audio_lessons_generator",
    version="2021.04.30.01",
    description="Audio Lessons Generator",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/CherokeeLanguage/audio-lessons-generator-python",
    author="Michael Conrad",
    author_email="m.conrad.202@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python"
    ],
    packages=setuptools.find_packages(),
    python_requires=">=3.7"
)