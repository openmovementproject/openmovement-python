# python -m pip install -e "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"
from setuptools import setup

setup(
    name='openmovement',
    url='https://github.com/digitalinteraction/openmovement-python/',
    author='Dan Jackson',
    packages=['openmovement'],
    install_requires=['numpy', 'pandas'],
    version='0.1',
    license='BSD',
    description='Open Movement processing code',
    #scripts=['bin/build-omconvert.sh'],
    long_description=open('README.md').read(),
)
