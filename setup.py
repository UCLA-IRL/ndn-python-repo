#!/usr/bin/env python3

from setuptools import setup, find_packages


__version__ = "0.2a5"

setup(
    name='ndn-python-repo',
    version=__version__,
    description='An NDN Repo implementation using Python',
    url='https://github.com/JonnyKong/ndn-python-repo',
    author='Zhaoning Kong',
    author_email='jonnykong@cs.ucla.edu',
    download_url='https://pypi.python.org/pypi/ndn-python-repo',
    project_urls={
        "Bug Tracker": "https://github.com/JonnyKong/ndn-python-repo/issues",
        "Source Code": "https://github.com/JonnyKong/ndn-python-repo",
    },
    license='Apache License 2.0',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',

        'Topic :: Database',
        'Topic :: Internet',
        'Topic :: System :: Networking',

        'License :: OSI Approved :: Apache Software License',

        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    keywords='NDN',

    packages=find_packages(exclude=['tests']),

    install_requires=[
        "python-ndn >= 0.2b2.post1",
        "PyYAML >= 5.1.2",
    ],
    extras_require={
        'test': [ 'pytest', 'pytest-cov'],
        'leveldb': ['plyvel'],
        'mongodb': ['pymongo']
    },
    python_requires=">=3.6",

    entry_points={
        'console_scripts': [
            'ndn-python-repo = ndn_python_repo.cmd.main:main',
            'ndn-python-repo-install = ndn_python_repo.cmd.install:main',
            'ndn-python-repo-port = ndn_python_repo.cmd.port:main'
        ],
    },

    data_files=[
        # ('/usr/local/etc/ndn', ['ndn_python_repo/ndn-python-repo.conf']),
        # ('/etc/systemd/system/', ['ndn_python_repo/ndn-python-repo.service']),
    ],

    package_data={
        '': ['*.conf.sample', '*.service'],
    },
    include_package_data=True,
)
